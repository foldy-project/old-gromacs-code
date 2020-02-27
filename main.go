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
	PDBID string `json:"pdb_id"`
	Steps int    `json:"steps"`
}

type server struct {
	image                string
	prefix               string
	clientset            *kubernetes.Clientset
	namespace            string
	foldyOperatorAddress string
	requests             map[string]chan<- interface{}
	requestsL            sync.Mutex
	timeout              time.Duration
	handler              *http.ServeMux
	redis                *redis.Client
	exit                 chan<- error
	maxUploadSize        int64
}

func homeDir() string {
	if h := os.Getenv("HOME"); h != "" {
		return h
	}
	return os.Getenv("USERPROFILE") // windows
}

func (s *server) createExperimentPodObject(config *RunConfig, correlationID string) (*v1.Pod, error) {
	return &v1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      fmt.Sprintf("%s-%s-%s", s.prefix, config.PDBID, correlationID[:8]),
			Namespace: s.namespace,
			Labels: map[string]string{
				"app": fmt.Sprintf("%s-%s", s.prefix, config.PDBID),
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
						"--correlation_id",
						correlationID,
						"--steps",
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
	//defer func() {
	//	// Clean up pod at the end
	//	if err := s.clientset.CoreV1().Pods(s.namespace).Delete(
	//		context.TODO(),
	//		pod.Name,
	//		&metav1.DeleteOptions{},
	//	); err != nil {
	//		log.Printf("Warning: failed to delete pod: %v", err)
	//	}
	//	log.Printf("Deleted pod %s", pod.Name)
	//}()
	log.Printf("Pod created.")
	req := make(chan interface{}, 1)
	problem := make(chan error, 1)
	stop := make(chan int, 1)
	defer func() {
		stop <- 0
		close(stop)
	}()
	go func() {
		defer close(problem)
		probeInterval := time.Second * 3
		for {
			select {
			case <-stop:
				return
			case <-time.After(probeInterval):
				// Get the pod status
				info, err := s.clientset.CoreV1().Pods(s.namespace).Get(
					context.TODO(),
					pod.Name,
					metav1.GetOptions{},
				)
				if err != nil {
					problem <- fmt.Errorf("encountered error while creating pod: %v", err)
					return
				}
				log.Printf("Pod phase: %v", info.Status.Phase)
				switch info.Status.Phase {
				case "Pending":
					continue
				case "Running":
					continue
				case "Succeeded":
					panic("unreachable brach detected")
				default:
					problem <- fmt.Errorf("encountered unexpected phase '%s'", info.Status.Phase)
					return
				}
			}
		}
	}()
	s.requestsL.Lock()
	s.requests[correlationID] = req
	s.requestsL.Unlock()
	select {
	case err := <-problem:
		return nil, err
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
		namespace:            "default",
		image:                "thavlik/foldy:latest",
		prefix:               "foldy-sim",
		foldyOperatorAddress: "foldy-operator:8090",
		clientset:            clientset,
		requests:             make(map[string]chan<- interface{}),
		timeout:              time.Minute * 15,
		handler:              handler,
		redis:                client,
		exit:                 exit,
		maxUploadSize:        1024 * 1024 * 512, // 512Mi
	}
	go s.listenForPubSub(pubsub.Channel(), exit)
	s.buildRoutes()
	return s, nil
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
				correlationID := msg.Payload
				s.requestsL.Lock()
				req, ok := s.requests[correlationID]
				if !ok {
					s.requestsL.Unlock()
					continue
				}
				delete(s.requests, correlationID)
				s.requestsL.Unlock()
				key := rkResult(correlationID)
				p := s.redis.Pipeline()
				getCmd := p.Get(key)
				p.Del(key)
				if _, err := p.Exec(); err != nil {
					log.Printf("Error retrieving result: %v", err)
					req <- fmt.Errorf("redis: %v", err)
					close(req)
					continue
				}
				data, _ := getCmd.Result()
				req <- []byte(data)
				close(req)
				log.Printf("%s fulfilled locally", correlationID)
			}
		}
	}
}

func rkResult(correlationID string) string {
	return fmt.Sprintf("r:%s:i", correlationID)
}

func getPDBIDFromRequest(r *http.Request) (string, error) {
	newValues, err := url.ParseQuery(r.URL.RawQuery)
	if err != nil {
		return "", fmt.Errorf("failed to parse query: %v", err)
	}
	pdbIDs, ok := newValues["pdb_id"]
	if !ok || len(pdbIDs) == 0 {
		return "", fmt.Errorf("missing pdb_id")
	}
	return pdbIDs[0], nil
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

func (s *server) fullfillLocal(correlationID string, data []byte) error {
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

func (s *server) fullfillRemote(correlationID string, data []byte) error {
	p := s.redis.Pipeline()
	// Cache the result in redis
	p.Set(rkResult(correlationID), data, time.Minute*15)
	// Inform cluster of success
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
			if err := r.ParseMultipartForm(s.maxUploadSize); err != nil {
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
			if err := s.fullfillLocal(correlationID, data); err == errRequestNotFound {
				if err := s.fullfillRemote(correlationID, data); err != nil {
					return fmt.Errorf("fulfillRemote: %v", err)
				}
				log.Printf("%s fulfilled remotely", correlationID)
			} else if err != nil {
				return fmt.Errorf("fulfillLocal: %v", err)
			} else {
				log.Printf("%s fulfilled locally", correlationID)
			}
			return nil
		}(); err != nil {
			log.Printf("%v: %v", r.RequestURI, err)
			w.WriteHeader(http.StatusInternalServerError)
		}
	}
}

func (s *server) handleRun() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := func() error {
			body, err := ioutil.ReadAll(r.Body)
			if err != nil {
				return fmt.Errorf("body: %v", err)
			}
			log.Printf("body=%s", string(body))
			config := &RunConfig{}
			if err := json.Unmarshal(body, config); err != nil {
				return fmt.Errorf("unmarshal: %v", err)
			}
			log.Printf("Received run request, pdb=%s", config.PDBID)
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
			w.WriteHeader(http.StatusInternalServerError)
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
				return errRequestNotFound
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

func entry() error {
	s, err := newServer()
	if err != nil {
		return fmt.Errorf("constructor: %v", err)
	}
	s.listen()
	return nil
}

func main() {
	if err := entry(); err != nil {
		log.Fatal(err)
	}
}
