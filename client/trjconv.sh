#!/bin/bash
set -euo pipefail
cd $(dirname "$0")
input_xtc=$1
input_tpr=$2
frame=$3
echo 0 | gmx trjconv -f $input_xtc -o "${frame}.pdb" -b $frame -e $frame -tu fs -s $input_tpr
