#!/bin/bash
set -euo pipefail
image=thavlik/foldy-operator-test
tag=latest
cd $(dirname "$0")
docker build -t $image:$tag $@ .
docker push $image:$tag
