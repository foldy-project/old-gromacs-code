; minim.mdp - used as input into grompp to generate em.tpr
; Parameters describing what to do, when to stop and what to save
integrator  = md            ; Algorithm (steep = steepest descent minimization)
nsteps      = ${nsteps}     ; Maximum number of (minimization) steps to perform
dt		    = ${dt}         ; deltatime in picoseconds (default 0.002 ps = 2 fs)

; Parameters describing how to find the neighbors of each atom and how to calculate the interactions
nstlist         = 1         ; Frequency to update the neighbor list and long range forces
cutoff-scheme   = Verlet    ; Buffered neighbor searching
ns_type         = grid      ; Method to determine neighbor list (simple, grid)
coulombtype     = PME       ; Treatment of long range electrostatic interactions
rcoulomb        = 1.0       ; Short-range electrostatic cut-off
rvdw            = 1.0       ; Short-range Van der Waals cut-off
pbc             = xyz       ; Periodic Boundary Conditions in all 3 dimensions

; Output control
nstxout                 = 1       ; save coordinates every frame
nstvout                 = 1       ; save velocities every frame
nstenergy               = 1       ; save energies every frame
nstlog                  = 1       ; update log file every frame
nstxout-compressed  = 1      ; save compressed coordinates every step
                                ; nstxout-compressed replaces nstxtcout
compressed-x-grps   = System    ; replaces xtc-grps