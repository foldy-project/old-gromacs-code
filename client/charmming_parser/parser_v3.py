#!/usr/bin/env python
# fcp v0.4 01/13/2010

#
#                            PUBLIC DOMAIN NOTICE
#
#  This software/database is a "United States Government Work" under the
#  terms of the United States Copyright Act.  It was written as part of
#  the authors' official duties as a United States Government employee and
#  thus cannot be copyrighted.  This software is freely available
#  to the public for use.  There is no restriction on its use or
#  reproduction.
#
#  Although all reasonable efforts have been taken to ensure the accuracy
#  and reliability of the software and data, NIH and the U.S.
#  Government do not and cannot warrant the performance or results that
#  may be obtained by using this software or data. NIH, NHLBI, and the U.S.
#  Government disclaim all warranties, express or implied, including
#  warranties of performance, merchantability or fitness for any
#  particular purpose.

"""
# Outline
# ( 0 ) Detect pdb version -- 'web' or 'charmm'
# ( 1 ) Initialize & Cull
# ( 2 ) Tag redundant atoms from each multi-model section for removal
# ( 3 ) Multi-Model clean up
# ( 4 ) Sort by scoring each atom line using the following priority
# ( 5 ) Build segments
# ( 6 ) Rename terminal oxygens in protein segments to be charmm compliant.
# ( 7 ) Differentiate between DNA and RNA
# ( 8 ) Make res_names and atom types charmm compliant
# ( 9 ) Re-Index atomNumber & resid
# (10 ) Pickle pdb_file (for old->new/new->old indicies)
# (11 ) File Dump
# (12 ) To STDOUT
"""

import sys
import string
import pickle as cPickle
import Atom
import Etc

# User defined options
in_ver='auto'       # 'auto' or 'web' or 'charmm'
out_ver='charmm'    # 'web' or 'charmm'

# Don't edit these
pdb_name = sys.argv[-2]
assert len(pdb_name) == 4
warnings=[]

# TODO optparse!
for opt_arg in sys.argv[2:-1]:
    if opt_arg.startswith('out_ver'): out_ver = opt_arg.split('=')[1]
    elif opt_arg.startswith('in_ver'): in_ver = opt_arg.split('=')[1]
    else: raise TacoError

# ( 0 ) Detect pdb version -- 'web' or 'charmm'
if in_ver == 'auto':
    in_ver = Etc.get_ver(sys.argv[-1])

# ( 0.1)Detect missing seg info
test_text = [ line for line in open(sys.argv[-1]) ]
test_line = test_text[0]
if in_ver == 'web':
    test_seg = test_line[21:22]
elif in_ver == 'charmm':
    test_seg = test_line[72:76]
if test_seg in ['',' ']:
    bad_seg = True
else:
    bad_seg = False

# ( 1 ) Initialize & Cull
if not bad_seg:
    pdb_file = [ Atom.Atom(line,in_ver) for line in open(sys.argv[-1]) if line.startswith('ATOM') or line.startswith('HETATM') ]
else:
    pdb_file = []
    nTH_seg = 0
    for line in open(sys.argv[-1]):
        if line.startswith('ATOM') or line.startswith('HETATM'):
            thisAtom = Atom.Atom(line,in_ver)
            thisAtom.segid = string.uppercase[nTH_seg]
            pdb_file.append(thisAtom)
        elif line.startswith('TER'):
            nTH_seg += 1

# ( 2 ) Tag redundant atoms from each multi-model section for removal
#  This is done via the following procedure...
#   (a) First check if a line belongs to a multi-model section
#   (b) The conditions to start a multi-model section comparison:
#       ->  The 2-state buffer must be empty
#       ->  The leading character must be an 'A'
#   (c) Store the line in a 2-state (empty or full) buffer, store the line number in index
#  Now we have something to compare the following lines in the multi-model section to (the buffer is filled)
#   (d) We need to determine if we are still in the current multi-model section, and when the section is terminated
#   (e) Check the weight of the current line vs. the weight of the buffered line
#   (f) If the buffered line has a bigger weight than the current line, tag the current line for removal
#   (g) If the buffered line has a smaller weight than the current line, tag the buffered line for removal
#      and buffer the current line
#   (h) We are in the next multi-model section, fill the buffer with the current line.
buffer = []
for line in pdb_file:
    if ( len(line.resName) == 4 and line.weight < 0.99 and line.tag == 'pro' ):             # (a)
        if ( not buffer and line.resName[:1] == 'A' ):                                      # (b)
            buffer.append(line)                                                             # (c)
            continue
        if buffer:
            if (line.resName[:1] > buffer[0].resName[:1]):                                  # (d)
                if ( buffer[0].weight >= line.weight ):                                     # (e)
                    line.tag = 'Remove'                                                     # (f)
                else:
                    buffer[0].tag = 'Remove'                                                # (g)
                    buffer = [line]
            else:
                buffer = [line]                                                             # (h)
# ( 3 ) Multi-Model clean up
#   (a) Delete atoms tagged for removal by the previous routine
#   (b) Relabel residue names from nRES -> RES (remove multi-model prefixes)
pdb_file = [ line for line in pdb_file if line.tag != 'Remove' ]
for line in pdb_file:
    if line.tag == 'pro':
        line.resName = line.resName[-3:]
# ( 4 ) Sort by scoring each atom line using the following priority
# seg_type > segid > resid > atomNumber
seg_type_score  = {'nuc':1,'pro':2,'good':3,'bad':4}
segid_score     = dict( [ (char,i+1) for i,char in enumerate(string.uppercase) ] )
def atom_score(arg):
    return (seg_type_score[arg.tag] * 1.E+11 + segid_score[arg.segid[0]] * 1.E+9 + arg.resid * 1.E+5 + arg.atomNumber)
pdb_file.sort(key=atom_score)
# ( 5 ) Build segments
seg_type = {'nuc':[],'pro':[],'good':[],'bad':[],'dna':[],'rna':[]}
this_seg = pdb_file[0]
buffer = []
for line in pdb_file:
    if line.tag == this_seg.tag and line.segid == this_seg.segid:
        buffer.append(line)
    else:
        if buffer[0].tag == 'nuc':
            seg_type['nuc'].append(buffer)
        elif buffer[0].tag == 'pro':
            seg_type['pro'].append(buffer)
        elif buffer[0].tag == 'good':
            seg_type['good'].append(buffer)
        elif buffer[0].tag == 'bad':
            seg_type['bad'].append(buffer)
        else:
            raise Death
        this_seg = line
        buffer = [line]
    if line == pdb_file[-1]:
        if buffer[0].tag == 'nuc':
            seg_type['nuc'].append(buffer)
        elif buffer[0].tag == 'pro':
            seg_type['pro'].append(buffer)
        elif buffer[0].tag == 'good':
            seg_type['good'].append(buffer)
        elif buffer[0].tag == 'bad':
            seg_type['bad'].append(buffer)
        else:
            raise Death
# ( 6 ) Rename terminal oxygens in protein segments to be charmm compliant.
for seg in seg_type['pro']:
    last_resid = seg[-1].resid
    for line in seg:
        if line.resid == last_resid and line.atomType == ' O  ':
            line.atomType = ' OT1'
        elif line.resid == last_resid and line.atomType == ' OXT':
            line.atomType = ' OT2'
# ( 7 ) Differentiate between DNA and RNA
for seg in seg_type['nuc']:
    thymine_present = False
    uracil_present = False
    for line in seg:
        if line.resName in ['T','THY','DT']:
            thymine_present = True
        elif line.resName in ['U','URA','DU']:
            uracil_present = True
#WARN#      Throw a warning when Uracil and Thymine are found in the same segment
    if thymine_present and uracil_present:
        warnings.append((-1,'URA & THY in same segment'))
    elif thymine_present:
        for line in seg:
            line.tag = 'dna'
        seg_type['dna'].append(seg)
    elif uracil_present:
        for line in seg:
            line.tag = 'rna'
        seg_type['rna'].append(seg)
seg_type['nuc'] = [ seg for seg in seg_type['nuc'] if seg[0].tag == 'nuc' ]
#WARN#      Throw a warning when a nucleic acid segment isn't identified as DNA or RNA
if seg_type['nuc']:
    warnings.append((-1,'Parser cant ID nuc segment'))
# ( 8 ) Make res_names and atom types charmm compliant
for line in pdb_file:
    line.make_compliant()
# ( 9.1)Assign resIndex
pdb_file[0].resIndex = 1
this_resid = Etc.flatten(seg_type['pro'])[0].resid
new_resIndex = 1
for line in Etc.flatten(seg_type['pro']):
    if line.resid == this_resid:
        line.resIndex = new_resIndex
    else:
        this_resid = line.resid
        new_resIndex += 1
        line.resIndex = new_resIndex

# ( 9 ) Re-Index atomNumber & resid
for key in seg_type:
    for seg in seg_type[key]:
        old_resid = seg[0].resid
        new_resid = 1
        for i,line in enumerate(seg):
            line.atomNumber = i+1
            if line.resid == old_resid:
                line.resid = new_resid
            else:
                old_resid = line.resid
                new_resid += 1
                line.resid = new_resid
# (10 ) Pickle pdb_file (for old->new/new->old indicies)
cPickle.dump(pdb_file, open(pdb_name + '.chk','w') )
# (11 ) File Dump
prep_seg_type = {'nuc':'nuc','pro':'pro','good':'goodhet','bad':'het','dna':'dna','rna':'rna'}
prep_atom_tag = {'nuc':'ATOM','pro':'ATOM','good':'ATOM','bad':'HETATM','dna':'ATOM','rna':'ATOM'}
stdout_list = []
for key in seg_type:
    for seg in seg_type[key]:
        output_name = 'new_' + pdb_name + '-' + seg[0].segid + '-' + prep_seg_type[seg[0].tag] + '.pdb'
        output_name = output_name.lower()
        to_stdout   = seg[0].segid + '-' + prep_seg_type[seg[0].tag]
        stdout_list.append ( to_stdout.lower().strip() )
        write_to    = open(output_name,'w')
        output_tag  = prep_atom_tag[seg[0].tag]
        for line in seg:
            line.tag = output_tag
            write_to.write(line.Print(out_ver))
        write_to.write('TER\n')
        write_to.close()
        print('Wrote output to %s' % output_name)
# (12 ) To STDOUT
print('natom=%d' % len(pdb_file))
print('nwarn=%d' % len(warnings))
if warnings:
    print("warnings=", str(warnings).strip())
print("seg=", str(stdout_list))

"""Debug Printing (just move this section within the file)"""
#for key in seg_type:
#    for seg in seg_type[key]:
#        for line in seg:
#            print line,
#for line in pdb_file:
#    print str(line),
#    print line.line,
#raise TacoError
"""Debug Printing (just move this section within the file)"""


