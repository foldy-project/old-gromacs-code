package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	v1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/clientcmd"
)

func TestKubernetesClient(t *testing.T) {
	namespace := "default"
	var kubeconfig *string
	if home := homeDir(); home != "" {
		kubeconfig = flag.String("kubeconfig", filepath.Join(home, ".kube", "config"), "(optional) absolute path to the kubeconfig file")
	} else {
		kubeconfig = flag.String("kubeconfig", "", "absolute path to the kubeconfig file")
	}
	config, err := clientcmd.BuildConfigFromFlags("", *kubeconfig)
	require.NoError(t, err)
	clientset, err := kubernetes.NewForConfig(config)
	require.NoError(t, err)
	appLabel := "test-k8s"
	pod := &v1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "test-k8s-pod",
			Namespace: namespace,
			Labels: map[string]string{
				"app": appLabel,
			},
		},
		Spec: v1.PodSpec{
			RestartPolicy: v1.RestartPolicyNever,
			Containers: []v1.Container{
				v1.Container{
					ImagePullPolicy: v1.PullIfNotPresent,
					Name:            "echo",
					Image:           "alpine:latest",
					Command: []string{
						"echo",
						"HelloWorld",
					},
					Resources: v1.ResourceRequirements{
						Limits: map[v1.ResourceName]resource.Quantity{
							"cpu":    resource.MustParse("50m"),
							"memory": resource.MustParse("64Mi"),
						},
					},
				},
			},
		},
	}
	_, err = clientset.CoreV1().Pods(namespace).Create(
		context.TODO(),
		pod,
		metav1.CreateOptions{},
	)
	require.NoError(t, err)
	for {
		resp, err := clientset.CoreV1().Pods(namespace).List(
			context.TODO(),
			metav1.ListOptions{
				LabelSelector: fmt.Sprintf("app=%s", appLabel),
			},
		)
		require.NoError(t, err)
		assert.Equal(t, 1, len(resp.Items))
		for _, pod := range resp.Items {
			log.Printf("%v %v", pod.Name, pod.Status.Phase)
			//switch pod.Status.Phase {
			//case "Succeeded":
			//case "Error":
			//default:
			//}
		}
		<-time.After(time.Second * 5)
	}
}
