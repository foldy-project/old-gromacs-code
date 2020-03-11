#!/bin/bash
set -euo pipefail
image=thavlik/foldy-operator-test
tag=latest
cd $(dirname "$0")
SSH_PRIVATE_KEY=$(cat ~/.ssh/id_rsa)
docker build \
    -t $image:$tag \
    --build-arg SSH_PRIVATE_KEY="$SSH_PRIVATE_KEY" \
    --squash $@ .
docker push $image:$tag
