#!/bin/bash
set -euo pipefail
echo "Running tests, timeout is ${TIMEOUT}, concurrency is ${CONCURRENCY}"

# -timeout has to be long enough for all subtests
time go test -v -timeout 24h $@
