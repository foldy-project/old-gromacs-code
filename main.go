package main

import (
	"context"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"os"
	"sync"
	"time"

	"github.com/google/uuid"
	v1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)

type server struct {
	image                string
	prefix               string
	clientset            *kubernetes.Clientset
	namespace            string
	foldyOperatorAddress string
	requests             map[string]chan<- interface{}
	requestsL            sync.Mutex
	timeout              time.Duration
}

func homeDir() string {
	if h := os.Getenv("HOME"); h != "" {
		return h
	}
	return os.Getenv("USERPROFILE") // windows
}

func (s *server) createExperimentPodObject(pdbID string, correlationID string) (*v1.Pod, error) {
	return &v1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      fmt.Sprintf("%s-%s-%s", s.prefix, pdbID, correlationID[:4]),
			Namespace: s.namespace,
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
						"./entrypoint.sh",
						pdbID,
						correlationID,
					},
					VolumeMounts: []v1.VolumeMount{
						v1.VolumeMount{
							Name:      "aws-cred",
							MountPath: "/root/.aws",
						},
					},
					Resources: v1.ResourceRequirements{
						Limits: map[v1.ResourceName]resource.Quantity{
							"cpu":    resource.MustParse("2000m"),
							"memory": resource.MustParse("4Gi"),
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

func (s *server) runExperiment(pdbID string) ([]byte, error) {
	correlationID := uuid.New().String()
	log.Printf("Running experiment %s, correlationID=%s", pdbID, correlationID)
	pod, err := s.createExperimentPodObject(pdbID, correlationID)
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
		}
		log.Printf("Deleted pod %s", pod.Name)
	}()
	log.Printf("Pod created.")
	ch := make(chan interface{}, 1)
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
				default:
					problem <- fmt.Errorf("encountered unexpected phase '%s'", info.Status.Phase)
					return
				}
			}
		}
	}()
	s.requestsL.Lock()
	s.requests[correlationID] = ch
	s.requestsL.Unlock()
	select {
	case err := <-problem:
		return nil, fmt.Errorf("pod: %v", err)
	case result := <-ch:
		if err, ok := result.(error); ok && err != nil {
			return nil, fmt.Errorf("rpc: %v", err)
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
	//pod, err := clientset.CoreV1().Pods("default").Get(context.TODO(), "simulate-1aki-wn9x8", metav1.GetOptions{})
	//if err != nil {
	//	return nil, fmt.Errorf("pod: %v", err)
	//}
	//log.Printf("%#v", pod)
	//pods, err := clientset.CoreV1().Pods("default").List(context.TODO(), metav1.ListOptions{})
	//if err != nil {
	//	return nil, fmt.Errorf("pods: %v", err)
	//}
	//log.Printf("%#v", pods)
	return &server{
		namespace:            "default",
		image:                "thavlik/foldy:latest",
		prefix:               "foldy-sim",
		foldyOperatorAddress: "foldy-operator:8090",
		clientset:            clientset,
		requests:             make(map[string]chan<- interface{}),
		timeout:              time.Minute * 15,
	}, nil
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

func (s *server) listen() {
	http.HandleFunc("/complete", func(w http.ResponseWriter, r *http.Request) {
		if err := func() error {
			correlationID, err := getCorrelationIDFromRequest(r)
			if err != nil {
				return err
			}
			log.Printf("Received completion request, correlationID=%s", correlationID)
			data, err := ioutil.ReadAll(r.Body)
			if err != nil {
				return fmt.Errorf("body: %v", err)
			}
			s.requestsL.Lock()
			ch, ok := s.requests[correlationID]
			if !ok {
				return fmt.Errorf("channel %s not found", correlationID)
			}
			delete(s.requests, correlationID)
			s.requestsL.Unlock()
			ch <- data
			close(ch)
			log.Printf("%s fulfilled", correlationID)
			return nil
		}(); err != nil {
			log.Printf("handler: %v", err)
		}
	})
	http.HandleFunc("/run", func(w http.ResponseWriter, r *http.Request) {
		if err := func() error {
			pdbID, err := getPDBIDFromRequest(r)
			if err != nil {
				return err
			}
			log.Printf("Received run request, pdb=%s", pdbID)
			body, err := s.runExperiment(pdbID)
			if err != nil {
				return fmt.Errorf("failed to run experiment: %v", err)
			}
			w.Header().Set("Content-Type", "application/x-tar")
			w.Write(body)
			return nil
		}(); err != nil {
			log.Printf("handler: %v", err)
		}
	})
	go func() {
		log.Printf("Listening on 8090")
		if err := http.ListenAndServe(":8090", nil); err != nil {
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
