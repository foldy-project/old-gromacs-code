#!/bin/bash
set -euo pipefail
echo "Running tests, timeout is ${TIMEOUT}, concurrency is ${CONCURRENCY}"

# -timeout has to be long enough for all subtests
go test -v -timeout 2h