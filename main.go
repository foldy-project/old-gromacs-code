package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/go-redis/redis/v7"
	"github.com/google/uuid"
	v1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)

// RunConfig ...
type RunConfig struct {
	PDBID   string `json:"pdb_id"`
	Steps   int    `json:"steps"`
	ModelID int    `json:"model_id"`
	ChainID string `json:"chain_id"`
	Primary string `json:"primary"`
	Mask    string `json:"mask"`
	Seed    int    `json:"seed"`
}

type server struct {
	image                 string
	appLabel              string
	clientset             *kubernetes.Clientset
	namespace             string
	foldyOperatorAddress  string
	requests              map[string]chan<- interface{}
	requestsL             sync.Mutex
	timeout               time.Duration
	handler               *http.ServeMux
	redis                 *redis.Client
	exit                  chan<- error
	multipartUploadMemory int64
	pruneResultTimeout    time.Duration
}

func homeDir() string {
	if h := os.Getenv("HOME"); h != "" {
		return h
	}
	return os.Getenv("USERPROFILE") // windows
}

func (s *server) createExperimentPodObject(
	config *RunConfig,
	correlationID string,
) (*v1.Pod, error) {
	return &v1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      fmt.Sprintf("%s-%s-%s", s.appLabel, config.PDBID, correlationID[:8]),
			Namespace: s.namespace,
			Labels: map[string]string{
				"app": s.appLabel,
			},
		},
		Spec: v1.PodSpec{
			RestartPolicy: v1.RestartPolicyNever,
			Volumes: []v1.Volume{
				v1.Volume{
					Name: "aws-cred",
					VolumeSource: v1.VolumeSource{
						Secret: &v1.SecretVolumeSource{
							SecretName: "aws-cred",
						},
					},
				},
			},
			Containers: []v1.Container{
				v1.Container{
					ImagePullPolicy: v1.PullAlways,
					Name:            "simulation",
					Image:           s.image,
					Command: []string{
						"python3",
						"./simulate.py",
						"--pdb_id",
						config.PDBID,
						"--model_id",
						fmt.Sprintf("%d", config.ModelID),
						"--chain_id",
						config.ChainID,
						"--primary",
						config.Primary,
						"--mask",
						config.Mask,
						"--correlation_id",
						correlationID,
						"--nsteps",
						fmt.Sprintf("%d", config.Steps),
					},
					VolumeMounts: []v1.VolumeMount{
						v1.VolumeMount{
							Name:      "aws-cred",
							MountPath: "/root/.aws",
						},
					},
					Resources: v1.ResourceRequirements{
						Limits: map[v1.ResourceName]resource.Quantity{
							"cpu":    resource.MustParse("1000m"),
							"memory": resource.MustParse("2Gi"),
						},
					},
					Env: []v1.EnvVar{
						v1.EnvVar{
							Name:  "FOLDY_OPERATOR",
							Value: s.foldyOperatorAddress,
						},
					},
				},
			},
		},
	}, nil
}

func (s *server) runExperiment(config *RunConfig) ([]byte, error) {
	correlationID := uuid.New().String()
	log.Printf("Running experiment %s, correlationID=%s", config.PDBID, correlationID)
	pod, err := s.createExperimentPodObject(config, correlationID)
	if err != nil {
		return nil, fmt.Errorf("failed to create pod: %v", err)
	}
	log.Printf("Pod object created. Creating pod...")
	if _, err := s.clientset.CoreV1().Pods(s.namespace).Create(
		context.TODO(),
		pod,
		metav1.CreateOptions{},
	); err != nil {
		return nil, fmt.Errorf("create pod: %v", err)
	}
	defer func() {
		// Clean up pod at the end
		if err := s.clientset.CoreV1().Pods(s.namespace).Delete(
			context.TODO(),
			pod.Name,
			&metav1.DeleteOptions{},
		); err != nil {
			log.Printf("Warning: failed to delete pod: %v", err)
		} else {
			log.Printf("Deleted pod %s", pod.Name)
		}
	}()
	log.Printf("Pod created.")
	req := make(chan interface{}, 1)
	s.requestsL.Lock()
	s.requests[correlationID] = req
	s.requestsL.Unlock()
	select {
	case result := <-req:
		if err, ok := result.(error); ok && err != nil {
			return nil, err
		}
		if body, ok := result.([]byte); ok {
			return body, nil
		}
		return nil, fmt.Errorf("malformed response from channel %T(%v)", result, result)
	case <-time.After(s.timeout):
		return nil, fmt.Errorf("timed out after %v", s.timeout)
	}
}

func newServer() (*server, error) {
	//var kubeconfig *string
	//if home := homeDir(); home != "" {
	//	kubeconfig = flag.String("kubeconfig", filepath.Join(home, ".kube", "config"), "(optional) absolute path to the kubeconfig file")
	//} else {
	//	kubeconfig = flag.String("kubeconfig", "", "absolute path to the kubeconfig file")
	//}
	//config, err := clientcmd.BuildConfigFromFlags("", *kubeconfig)
	//if err != nil {
	//	panic(err.Error())
	//}
	config, err := rest.InClusterConfig()
	if err != nil {
		panic(err.Error())
	}
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("clientset: %v", err)
	}
	handler := http.NewServeMux()

	var redisURI string
	var ok bool
	if redisURI, ok = os.LookupEnv("REDIS_URI"); !ok {
		redisURI = "localhost:6379"
	}
	client := redis.NewClient(&redis.Options{
		Addr:     redisURI,
		Password: "", // no password set
		DB:       0,  // use default DB
	})
	if _, err := client.Ping().Result(); err != nil {
		return nil, fmt.Errorf("redis: %v", err)
	}

	pubsub := client.Subscribe("foldy")
	// Wait for confirmation that subscription is created before publishing anything.
	if _, err := pubsub.Receive(); err != nil {
		return nil, fmt.Errorf("pubsub: %v", err)
	}
	exit := make(chan error, 1)
	s := &server{
		namespace:             "default",
		image:                 "thavlik/foldy-client:latest",
		appLabel:              "foldy-sim",
		foldyOperatorAddress:  "foldy-operator:8090",
		clientset:             clientset,
		requests:              make(map[string]chan<- interface{}),
		timeout:               time.Minute * 240,
		handler:               handler,
		redis:                 client,
		exit:                  exit,
		multipartUploadMemory: 1024 * 1024, // 1mb
		pruneResultTimeout:    time.Minute,
	}
	go s.listenForPubSub(pubsub.Channel(), exit)
	s.buildRoutes()
	return s, nil
}

func (s *server) handleBroadcastPayload(correlationID string) error {
	s.requestsL.Lock()
	req, ok := s.requests[correlationID]
	if !ok {
		s.requestsL.Unlock()
		return errRequestNotFound
	}
	delete(s.requests, correlationID)
	s.requestsL.Unlock()
	defer close(req)

	key := rkResult(correlationID)
	p := s.redis.Pipeline()
	getCmd := p.Get(key)
	p.Del(key)
	if _, err := p.Exec(); err != nil {
		log.Printf("Error retrieving result: %v", err)
		req <- fmt.Errorf("redis: %v", err)
		return fmt.Errorf("redis: %v", err)
	}
	data, _ := getCmd.Result()
	payload := &BroadcastPayload{}
	if err := json.Unmarshal(
		[]byte(data),
		payload,
	); err != nil {
		req <- fmt.Errorf("unmarshal: %v", err)
		return fmt.Errorf("unmarshal: %v", err)
	}
	if payload.Success {
		req <- []byte(payload.Data)
		log.Printf("%s fulfilled from remote", correlationID)
	} else {
		req <- fmt.Errorf(payload.ErrorMsg)
		log.Printf("%s remote error: %v", correlationID, payload.ErrorMsg)
	}
	return nil
}

func (s *server) listenForPubSub(
	ch <-chan *redis.Message,
	exit <-chan error,
) {
	for {
		select {
		case <-exit:
			return
		case msg := <-ch:
			if msg.Channel == "foldy" {
				if err := s.handleBroadcastPayload(
					msg.Payload,
				); err != nil && err != errRequestNotFound {
					log.Printf("error handling broadcast payloade: %v", err)
				}
			}
		}
	}
}

func rkResult(correlationID string) string {
	return fmt.Sprintf("r:%s:i", correlationID)
}

func getCorrelationIDFromRequest(r *http.Request) (string, error) {
	newValues, err := url.ParseQuery(r.URL.RawQuery)
	if err != nil {
		return "", fmt.Errorf("failed to parse query: %v", err)
	}
	correlationIDs, ok := newValues["correlation_id"]
	if !ok || len(correlationIDs) == 0 {
		return "", fmt.Errorf("missing correlation_id")
	}
	return correlationIDs[0], nil
}

var errRequestNotFound = fmt.Errorf("request not found")

func (s *server) fullfillLocalSuccess(correlationID string, data []byte) error {
	s.requestsL.Lock()
	defer s.requestsL.Unlock()
	req, ok := s.requests[correlationID]
	if !ok {
		return errRequestNotFound
	}
	delete(s.requests, correlationID)
	req <- data
	close(req)
	return nil
}

// BroadcastPayload ...
type BroadcastPayload struct {
	Data     []byte `json:"data"`
	Success  bool   `json:"success"`
	ErrorMsg string `json:"error_msg"`
}

func (s *server) fullfillRemoteError(correlationID string, errorMsg string) error {
	p := s.redis.Pipeline()
	body, err := json.Marshal(&BroadcastPayload{
		ErrorMsg: errorMsg,
	})
	if err != nil {
		return fmt.Errorf("marshal: %v", err)
	}
	p.Set(rkResult(correlationID), body, s.pruneResultTimeout)
	p.Publish("foldy", correlationID)
	if _, err := p.Exec(); err != nil {
		return fmt.Errorf("redis: %v", err)
	}
	return nil
}

func (s *server) fullfillRemoteSuccess(correlationID string, data []byte) error {
	p := s.redis.Pipeline()
	body, err := json.Marshal(&BroadcastPayload{
		Data:    data,
		Success: true,
	})
	if err != nil {
		return fmt.Errorf("marshal: %v", err)
	}
	p.Set(rkResult(correlationID), body, s.pruneResultTimeout)
	p.Publish("foldy", correlationID)
	if _, err := p.Exec(); err != nil {
		return fmt.Errorf("redis: %v", err)
	}
	return nil
}

func (s *server) handleComplete() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := func() error {
			correlationID, err := getCorrelationIDFromRequest(r)
			if err != nil {
				return err
			}
			log.Printf("Received completion request, correlationID=%s", correlationID)
			if err := r.ParseMultipartForm(s.multipartUploadMemory); err != nil {
				return fmt.Errorf("multipart form: %v", err)
			}
			file, _, err := r.FormFile("data")
			if err != nil {
				return fmt.Errorf("form file: %v", err)
			}
			defer file.Close()
			data, err := ioutil.ReadAll(file)
			if err != nil {
				return fmt.Errorf("failed to read file: %v", err)
			}

			go func() {
				// Return as much memory to the OS as possible.
				// https://medium.com/samsara-engineering/running-go-on-low-memory-devices-536e1ca2fe8f
				//defer debug.FreeOSMemory()

				// Do not wait to return a response
				if err := s.fullfillLocalSuccess(correlationID, data); err == errRequestNotFound {
					if err := s.fullfillRemoteSuccess(correlationID, data); err != nil {
						log.Printf("fulfillRemote: %v", err)
					}
					log.Printf("%s fulfilled remotely", correlationID)
				} else if err != nil {
					log.Printf("fulfillLocal: %v", err)
				} else {
					log.Printf("%s fulfilled locally", correlationID)
				}
			}()

			return nil
		}(); err != nil {
			log.Printf("%v: %v", r.RequestURI, err)
			w.WriteHeader(http.StatusInternalServerError)
		}
	}
}

func (s *server) handleRun() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		statusCode := http.StatusInternalServerError
		if err := func() error {
			body, err := ioutil.ReadAll(r.Body)
			if err != nil {
				statusCode = http.StatusBadRequest
				return fmt.Errorf("body: %v", err)
			}
			config := &RunConfig{}
			if err := json.Unmarshal(body, config); err != nil {
				statusCode = http.StatusBadRequest
				return fmt.Errorf("unmarshal: %v", err)
			}
			// Normalize ID as lowercase
			config.PDBID = strings.ToLower(config.PDBID)
			if config.Steps < 2 {
				// Run a simulation for less than two steps?
				statusCode = http.StatusBadRequest
				return fmt.Errorf("expected >1 steps, got %d", config.Steps)
			}
			if config.ChainID == "" {
				statusCode = http.StatusBadRequest
				return fmt.Errorf("missing chain_id")
			}
			if config.Seed < -1 {
				statusCode = http.StatusBadRequest
				return fmt.Errorf("invalid seed")
			} else if config.Seed == 0 {
				// Default seed to -1, which is random
				config.Seed = -1
			}
			log.Printf("Received run request, pdb=%s, seed=%d", config.PDBID, config.Seed)
			body, err = s.runExperiment(config)
			if err != nil {
				return err
			}
			filename := fmt.Sprintf("%s_minim.tar.gz", config.PDBID)
			w.Header().Set("Content-Disposition", "attachment; filename="+filename)
			w.Header().Set("Content-Length", fmt.Sprintf("%d", len(body)))
			w.Header().Set("Content-Type", "application/gzip")
			w.Write(body)
			return nil
		}(); err != nil {
			log.Printf("%v: %v", r.RequestURI, err)
			w.WriteHeader(statusCode)
			w.Write([]byte(err.Error()))
		}
	}
}

func (s *server) handleError() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := func() error {
			body, err := ioutil.ReadAll(r.Body)
			if err != nil {
				return fmt.Errorf("read body: %v", err)
			}
			doc := make(map[string]interface{})
			if err := json.Unmarshal(body, &doc); err != nil {
				return fmt.Errorf("json: %v", err)
			}
			msg, ok := doc["msg"].(string)
			if !ok {
				return fmt.Errorf("missing msg")
			}
			correlationID, ok := doc["correlation_id"].(string)
			if !ok {
				return fmt.Errorf("missing correlationID")
			}
			log.Printf("/error %s", msg)
			s.requestsL.Lock()
			req, ok := s.requests[correlationID]
			if !ok {
				s.requestsL.Unlock()
				if err := s.fullfillRemoteError(
					correlationID,
					msg,
				); err != nil {
					return fmt.Errorf("fulfillRemote: %v", err)
				}
				return nil
			}
			delete(s.requests, correlationID)
			s.requestsL.Unlock()
			req <- fmt.Errorf(msg)
			close(req)
			return nil
		}(); err != nil {
			log.Printf("%v: %v", r.RequestURI, err)
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(err.Error()))
		}
	}
}

func (s *server) buildRoutes() {
	s.handler.HandleFunc("/complete", s.handleComplete())
	s.handler.HandleFunc("/run", s.handleRun())
	s.handler.HandleFunc("/error", s.handleError())
}

func (s *server) listen() {
	go func() {
		log.Printf("Listening on 8090")
		if err := http.ListenAndServe(":8090", s.handler); err != nil {
			panic(fmt.Sprintf("ListenAndServe: %v", err))
		}
	}()
	<-make(chan error)
}

func (s *server) prunePods() error {
	resp, err := s.clientset.CoreV1().Pods(s.namespace).List(
		context.TODO(),
		metav1.ListOptions{
			LabelSelector: fmt.Sprintf("app=%s", s.appLabel),
		},
	)
	if err != nil {
		return fmt.Errorf("list pods: %v", err)
	}
	for _, pod := range resp.Items {
		switch pod.Status.Phase {
		case "Succeeded":
		case "Error":
		default:
		}
	}
	return nil
}

func entry() error {
	s, err := newServer()
	if err != nil {
		return fmt.Errorf("constructor: %v", err)
	}
	if err := s.prunePods(); err != nil {
		log.Printf("Warning: failed to prune pods: %v", err)
	}
	s.listen()
	return nil
}

func main() {
	if err := entry(); err != nil {
		log.Fatal(err)
	}
}
