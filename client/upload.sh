#!/bin/bash
set -euo pipefail
cd $(dirname "$0")
id=$1
correlation_id=$2
echo "FOLDY_OPERATOR is ${FOLDY_OPERATOR}, pdb_id=$id, correlation_id=$correlation_id"

###########################################################
# Create output folder
###########################################################
mkdir output
ls
mv ${id}_minim_* output
mv output ${id}_minim

###########################################################
# Compress and upload
###########################################################
tar -czvf ${id}_minim.tar.gz ${id}_minim
curl -F data=@${id}_minim.tar.gz ${FOLDY_OPERATOR}/complete?correlation_id=${correlation_id}