#!/bin/bash
set -euo pipefail
echo "Running tests, timeout is ${TIMEOUT}, concurrency is ${CONCURRENCY}"

mys3() {
    aws --endpoint=https://sfo2.digitaloceanspaces.com s3 $@
}

# -timeout has to be long enough for all subtests
time go test -v -timeout 200h

# upload definitely-good.txt
mys3 cp /data/definitely-good.txt s3://pdb/definitely-good.txt

