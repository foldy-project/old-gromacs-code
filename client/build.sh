#!/bin/bash
set -euo pipefail
kubectl delete job --all

image=thavlik/foldy-client
tag=latest
docker build -t $image:$tag .
docker push $image:$tag

kubectl apply -f normalize.yaml
watch "kubectl get pod"