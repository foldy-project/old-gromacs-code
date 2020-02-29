#!/bin/bash
set -euo pipefail
cd $(dirname "$0")
id=$1
begin=$2
end=$3
echo 0 | gmx trjconv -f "${id}_traj.xtc" -o "${id}_minim_${begin}.pdb" -b $begin -e $end -tu fs -s "${id}_em.tpr"
