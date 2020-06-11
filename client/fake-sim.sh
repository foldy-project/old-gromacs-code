#!/bin/bash
set -euo pipefail
cd $(dirname "$0")
input_path=$1
export emstep=0.01
export nsteps=10000
export dt=0.0002
export seed=-1

# generate mdp
envsubst < minim-modified.mdp.tpl > "tmp_minim-modified.mdp"
cat "tmp_minim-modified.mdp"

grep -v HOH $input_path > "tmp_clean.pdb"
gmx pdb2gmx -ignh -f "tmp_clean.pdb" -o "tmp_processed.gro" -p "tmp_topol.top" -water spce -ff amber03
gmx editconf -f "tmp_processed.gro" -o "tmp_newbox.gro" -c -d 1.0 -bt cubic
gmx solvate -cp "tmp_newbox.gro" -cs spc216.gro -o "tmp_solv.gro" -p "tmp_topol.top"
gmx grompp -f ions.mdp -c "tmp_solv.gro" -p "tmp_topol.top" -o "tmp_ions.tpr"
echo 13 | gmx genion -seed $seed -s "tmp_ions.tpr" -o "tmp_solv_ions.gro" -p "tmp_topol.top" -pname NA -nname CL -neutral # Group 13 (SOL)
gmx grompp -f "tmp_minim-modified.mdp" -c "tmp_solv_ions.gro" -p "tmp_topol.top" -o "out_em.tpr"
echo "Running simulation..."
gmx mdrun -v -deffnm em -x "out_traj.xtc" -s "out_em.tpr"
echo "Simulation complete"
du --block-size=M -a | grep out_traj.xtc
