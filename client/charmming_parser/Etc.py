#!/usr/bin/env python
# Filename: lib.Etc.py

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


import math
import string
import os

RAD2DEG = 180/math.pi
DEG2RAD = math.pi/180

ALPHAnum = string.uppercase + string.digits

def get_ver(pdb_file):
    """Takes a pdb file, and returns a string indicating if it is 'web' or 'charmm'
    pdb format."""
    buffer = [ line for line in open(pdb_file) if line.startswith('ATOM') or line.startswith('HETATM') ]
    for line in buffer:
        if (line[21:22] == ' ') and line[72:73] in ALPHAnum:
            return 'charmm'
        elif (line[21:22] in ALPHAnum) and (line[12:14].strip() == line[66:].strip()):
            return 'web'
    raise TypeError

def isNuc(res_name):
    """Takes a string and returns a bool.  True if the string represents a
    nucleic acid, false otherwise."""
    if res_name in ['A','G','T','C','U','ADE','THY','GUA','CYT','URA','DA','DG','DT','DC','DU']:
        return True
    else:
        return False

def is_dna(res_name):
    """Takes a string and returns a bool.  True if the string represents a
    dna nucleic acid, false otherwise."""
    if res_name in ['DA','DG','DT','DC']:
        return True
    else:
        return False

def is_rna(res_name):
    """Takes a string and returns a bool.  True if the string represents a
    rna nucleic acid, false otherwise."""
    if res_name in ['A','G','C','U']:
        return True
    else:
        return False

def isPro(res_name):
    """Takes a string and returns a bool.  True if the string represents a
    nucleoside, false otherwise."""
    if res_name[-3:] in ['ALA','CYS','ASP','GLU','PHE','GLY','HIS','ILE','LYS',\
             'LEU','MET','ASN','PYL','PRO','GLN','ARG','SER','THR','SEC','VAL',\
             'TRP','TYR','HSD']:
        return True
    else:
        return False

def isGood(res_name):
    """Takes a string and returns a bool.  True if the string represents a
    CHARMM friendly hetero-atom, false otherwise."""
    if res_name in ['HOH','TIP3','ZN2','SOD','CES','CLA','CAL','POT','ZN',\
            'FE','NA','CA','MG','CS','K','CL']:
        return True
    else:
        return False

def is_backbone(atom_type):
    """Takes a 4 character string representing an atom_type and returns a bool.
    True if the atom_type represents a back_bone atom in a protein, false otherwise."""
    if atom_type in [' N  ',' CA ',' C  ',' O  ',' OT1']:
        return True
    else:
        return False

aa_vdw = {'ALA':2.51958406732374,
          'CYS':2.73823091624513,
          'ASP':2.79030096923572,
          'GLU':2.96332591119925,
          'PHE':3.18235414984794,
          'GLY':2.25450393833984,
          'HIS':3.04273820988499,
          'HSD':3.04273820988499,
          'HSE':3.04273820988499,
          'HSP':3.04273820988499,
          'ILE':3.09345983013354,
          'LYS':3.18235414984794,
          'LEU':3.09345983013354,
          'MET':3.09345983013354,
          'ASN':2.84049696898525,
          'PRO':2.78004241717965,
          'GLN':3.00796101305807,
          'ARG':3.28138980397453,
          'SER':2.59265585208464,
          'THR':2.81059478021734,
          'VAL':2.92662460060742,
          'TRP':3.38869998431408,
          'TYR':3.22881842919248
          }

def get_aa_vdw(res_name):
    """ Return Van der Waals radius of Amino Acid sidechain (Units ?= Ang)"""
    res_name = str(res_name).upper()
    if res_name in aa_vdw:
        return aa_vdw[res_name]
    else:
        return None

aa_mass = {'ALA': 71.079,
           'CYS':103.145,
           'ASP':115.089,
           'GLU':129.116,
           'PHE':147.117,
           'GLY': 57.052,
           'HIS':137.141,
           'HSD':137.141,
           'HSE':137.141,
           'HSP':137.141,
           'ILE':113.160,
           'LYS':128.17 ,
           'LEU':113.160,
           'MET':131.199,
           'ASN':114.104,
           'PRO': 97.117,
           'GLN':128.131,
           'ARG':156.188,
           'SER': 87.078,
           'THR':101.105,
           'VAL': 99.133,
           'TRP':186.213,
           'TYR':163.176
           }

def get_aa_mass(res_name):
    """ Return mass of an Amino Acid (AMU)"""
    res_name = str(res_name).upper()
    if res_name in aa_mass:
        return aa_mass[res_name]
    else:
        return None

atomMass = {   'H':  1.0079,'HE':  4.0026,'LI':  6.941 ,'BE':  9.0122, 'B': 10.811 , 'C': 12.0107,
 'N': 14.0067, 'O': 15.9994, 'F': 18.9984,'NE': 20.1797,'NA': 22.9897,'MG': 24.3050,
'AL': 26.9815,'SI': 28.0855, 'P': 30.9738, 'S': 32.065 ,'CL': 35.453 ,'AR': 39.948 ,
 'K': 39.098 ,'CA': 40.078 ,'SC': 44.9559,'TI': 47.867 , 'V': 50.9415,'CR': 51.9961,
'MN': 54.9380,'FE': 55.845 ,'CO': 58.9332,'NI': 58.6934,'CU': 63.546 ,'ZN': 65.38  ,
'GA': 69.723 ,'GE': 72.64  ,'AS': 74.9216,'SE': 78.96  ,'BR': 79.904 ,'KR': 83.798 ,
'RB': 85.4678,'SR': 87.62  , 'Y': 88.9059,'ZR': 91.224 ,'NB': 92.9064,'MO': 95.94  ,
'TC': 98.    ,'RU':101.07  ,'RH':102.9055,'PD':106.42  ,'AG':107.8682,'CD':112.411 ,
'IN':114.818 ,'SN':118.710 ,'SB':121.760 ,'TE':127.60  , 'I':126.9045,'XE':131.293 ,
'CS':132.905 ,'BA':137.327 ,'LA':138.9055,'CE':140.116 ,'PR':140.9077,'ND':144.24  ,
'PM':145.    ,'SM':150.36  ,'EU':151.964 ,'GD':157.25  ,'TB':158.9253,'DY':162.500 ,
'HO':164.9303,'ER':167.259 ,'TM':168.9342,'YB':173.04  ,'LU':174.967 ,'HF':178.49  ,
'TA':180.9479, 'W':183.84  ,'RE':186.207 ,'OS':190.23  ,'IR':192.217 ,'PT':195.078 ,
'AU':196.9666,'HG':200.59  ,'TL':204.3833,'PB':207.2   ,'BI':208.9804,'PO':209.    ,'AT':210.    ,
'RN':222.    ,'FR':223.    ,'RA':226.    ,'AC':227.    ,'TH':232.0381,'PA':231.0359,
 'U':238.0289,'NP':237.    ,'PU':244.    ,'AM':243.    ,'CM':247.    ,'BK':247.    ,
'CF':251.    }

def get_atom_mass(element):
    """Return mass of an element (AMU)"""
    element = str(element).upper()
    if element in atom_mass:
        return atom_mass[element]
    else:
        return None

def dihedral_mod(dihedral,units='deg'):
    """Takes an angle and adds or subtracts 2PI until the resulting angle is
    between -PI and PI."""
    if units == 'deg':
        Pi = math.pi * RAD2DEG
    elif units in ['rad','au']:
        Pi = math.pi
    while abs(dihedral) > Pi:
        if dihedral < -1 * Pi:
            dihedral += 2 * Pi
        elif dihedral > Pi:
            dihedral -= 2 * Pi
    return dihedral

def get_res_names(iterator):
    """Takes an iterator and returns a list of unique residues present within it.
    Optionally you can define what the line begins with that has such information,
    and which field it should reside in.  The defaults work for .pdb files.
    """
    residues = [ line.split()[3] for line in stripBare(iterator) if ( line.startswith('ATOM') or line.startswith('HETATM') ) ]       # Parse residues 
    return list(set(residues))

def flatten(l, ltypes=(list, tuple)):
    """Takes a nested list of arbitrary depth, and returns a flattened one."""
    ltype = type(l)
    l = list(l)
    i = 0
    while i < len(l):
        while isinstance(l[i], ltypes):
            if not l[i]:
                l.pop(i)
                i -= 1
                break
            else:
                l[i:i + 1] = l[i]
        i += 1
    return ltype(l)

def stripComments(iterator,CC='#'):
    """Takes an iterator of strings and strips single line comments out."""
    return [ line.split(CC)[0] for line in iterator ]

def stripBare(iterator,CC='#'):
    """Takes an iterator of strings, strips out comments, blank lines, forces lower case and left justifies."""
    buffer = [ line for line in iterator if ( not line.lstrip().startswith(CC) and line.strip() ) ]
    return [ line.split(CC)[0].lstrip().rstrip().upper() for line in buffer ]

def parseDomainFile(iterator):
    """Takes a file handle and returns domain assignments."""
    return [ line.split('=')[1].strip().split('-') for line in stripBare(iterator) if line.startswith('DOMAIN') ]

def parseDomainString(string):
    """Takes a domain definition string and returns domain assignments."""
    buffer = []
    lastRes = '1'
    for taco in string.split(':'):
        buffer.append([lastRes,taco])
        lastRes = str(int(taco) + 1)
    return buffer

def expandPath(string):
    if '~' in string:
        return os.path.expanduser(string)
    else:
        return os.path.abspath(string)

