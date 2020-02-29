#!/bin/bash
set -euo pipefail
image=thavlik/foldy-client
tag=latest
docker build -t $image:$tag .
docker push $image:$tag
