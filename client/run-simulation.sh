#!/bin/bash
set -euo pipefail
cd $(dirname "$0")
script_dir=$(pwd)
id=$1
input_path=$2

export emtol=$3
export emstep=$4
export nsteps=$5
export dt=$6
export seed=$7

# generate mdp
envsubst < minim-modified.mdp.tpl > minim-modified.mdp

grep -v HOH $input_path > "${id}_clean.pdb"
gmx pdb2gmx -ignh -f "${id}_clean.pdb" -o "${id}_processed.gro" -p "${id}_topol.top" -water spce -ff amber03
gmx editconf -f "${id}_processed.gro" -o "${id}_newbox.gro" -c -d 1.0 -bt cubic
gmx solvate -cp "${id}_newbox.gro" -cs spc216.gro -o "${id}_solv.gro" -p "${id}_topol.top"
gmx grompp -f ${script_dir}/ions.mdp -c "${id}_solv.gro" -p "${id}_topol.top" -o "${id}_ions.tpr"
echo 13 | gmx genion -s "${id}_ions.tpr" -o "${id}_solv_ions.gro" -p "${id}_topol.top" -pname NA -nname CL -neutral # Group 13 (SOL)
gmx grompp -f ${script_dir}/minim-modified.mdp -c "${id}_solv_ions.gro" -p "${id}_topol.top" -o "${id}_em.tpr"
gmx mdrun -v -deffnm em -x "${id}_traj.xtc" -s "${id}_em.tpr"
echo "Simulation complete"