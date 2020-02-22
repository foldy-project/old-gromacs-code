#!/bin/bash
set -euo pipefail
image=thavlik/foldy-operator-test
tag=latest
kubectl delete job foldy-operator-test || true
docker build -t $image:$tag -f Dockerfile.test .
docker push $image:$tag
kubectl apply -f test.yaml
sleep 5s
POD=$(kubectl get pod -l app=foldy-operator-test -o jsonpath="{.items[-1].metadata.name}" --sort-by=.metadata.creationTimestamp)
kubectl logs -f $POD
