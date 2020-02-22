#!/bin/bash
set -euo pipefail
image=thavlik/foldy-operator
tag=latest
docker build -t $image:$tag .
docker push $image:$tag
kubectl apply -f deployment.yaml
kubectl rollout restart deployment foldy-operator