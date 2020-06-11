#!/bin/bash
set -euo pipefail
cd $(dirname "$0")
pdb_id=$1
input_path=$2
cd charmming_parser
python parser_v3.py $pdb_id $input_path
mv new_* ..