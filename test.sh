#!/bin/bash
set -euo pipefail
echo "Testing foldy-operator in-cluster..."
curl $FOLDY_OPERATOR/run?pdb_id=1aki -o 1aki_minim.tar.gz
ls -al
tar -xzvf 1aki_minim.tar.gz
