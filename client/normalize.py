from Bio.PDB.Residue import Residue
from Bio.PDB.Chain import Chain
from Bio.PDB.Atom import Atom


def get_atoms_from_desc(residue: Residue, description: list):
    atoms = []
    for i, (element, id) in enumerate(description):
        if not id in residue.child_dict:
            raise ValueError('atom "{}" not found'.format(id))
        atom = residue.child_dict[id]
        if atom.element != element:
            raise ValueError(
                'expected element "{}" from atom {}, got element "{}"'.format(element, i, atom.element))
        atoms.append(atom)
    return atoms


class NormalizedResidue:
    def __init__(self, residue: Residue, description: list):
        self.residue = Residue(residue.id, residue.resname, residue.segid)
        atoms = get_atoms_from_desc(residue, description)
        for atom in atoms:
            self.residue.add(atom.copy())


class Ala(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB')]
        super(Ala, self).__init__(residue, description)


class Arg(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('C', 'CD'), ('N', 'NE'), ('C', 'CZ'),
                       ('N', 'NH1'), ('N', 'NH2')]
        super(Arg, self).__init__(residue, description)


class Asn(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('O', 'OD1'), ('N', 'ND2')]
        super(Asn, self).__init__(residue, description)


class Asp(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('O', 'OD1'), ('O', 'OD2')]
        super(Asp, self).__init__(residue, description)


class Cys(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('S', 'SG')]
        super(Cys, self).__init__(residue, description)


class Gln(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('C', 'CD'), ('O', 'OE1'), ('N', 'NE2')]
        super(Gln, self).__init__(residue, description)


class Glu(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('C', 'CD'), ('O', 'OE1'), ('O', 'OE2')]
        super(Glu, self).__init__(residue, description)


class Gly(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'), ('O', 'O')]
        super(Gly, self).__init__(residue, description)


class His(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('N', 'ND1'), ('C', 'CD2'), ('C', 'CE1'),
                       ('N', 'NE2')]
        super(His, self).__init__(residue, description)


class Ile(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG1'),
                       ('C', 'CG2'), ('C', 'CD1')]
        super(Ile, self).__init__(residue, description)


class Leu(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('C', 'CD1'), ('C', 'CD2')]
        super(Leu, self).__init__(residue, description)


class Lys(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('C', 'CD'), ('C', 'CE'), ('N', 'NZ')]
        super(Lys, self).__init__(residue, description)


class Met(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('S', 'SD'), ('C', 'CE')]
        super(Met, self).__init__(residue, description)


class NH2(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N')]
        super(NH2, self).__init__(residue, description)


class Phe(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('C', 'CD1'), ('C', 'CD2'), ('C', 'CE1'),
                       ('C', 'CE2'), ('C', 'CZ')]
        super(Phe, self).__init__(residue, description)


class Pro(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('C', 'CD')]
        super(Pro, self).__init__(residue, description)


class Ser(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('O', 'OG')]
        super(Ser, self).__init__(residue, description)


class Thr(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('O', 'OG1'),
                       ('C', 'CG2')]
        super(Thr, self).__init__(residue, description)


class Trp(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('C', 'CD1'), ('C', 'CD2'), ('N', 'NE1'),
                       ('C', 'CE2'), ('C', 'CE3'), ('C', 'CZ2'),
                       ('C', 'CZ3'), ('C', 'CH2')]
        super(Trp, self).__init__(residue, description)


class Tyr(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG'),
                       ('C', 'CD1'), ('C', 'CD2'), ('C', 'CE1'),
                       ('C', 'CE2'), ('C', 'CZ'), ('O', 'OH')]
        super(Tyr, self).__init__(residue, description)


class Val(NormalizedResidue):
    def __init__(self, residue: Residue):
        description = [('N', 'N'), ('C', 'CA'), ('C', 'C'),
                       ('O', 'O'), ('C', 'CB'), ('C', 'CG1'),
                       ('C', 'CG2')]
        super(Val, self).__init__(residue, description)


_classes = {
    'PRO': Pro,
    'MET': Met,
    'ASP': Asp,
    'VAL': Val,
    'SER': Ser,
    'HIS': His,
    # 'NH2': NH2,
    'GLU': Glu,
    'GLN': Gln,
    'ASN': Asn,
    'GLY': Gly,
    'ILE': Ile,
    'LYS': Lys,
    'TRP': Trp,
    'TYR': Tyr,
    'THR': Thr,
    'ARG': Arg,
    'PHE': Phe,
    'CYS': Cys,
    'LEU': Leu,
    'ALA': Ala,
}


class UnknownResidueError(ValueError):
    def __init__(self, resname: str):
        super(UnknownResidueError, self).__init__('unknown resname "{}"'.format(resname))

def get_residue_class(resname: str) -> object:
    if not resname in _classes:
        raise UnknownResidueError(resname)
    return _classes[resname]


def normalize_residue(residue: Residue) -> Residue:
    ty = get_residue_class(residue.resname)
    obj = ty(residue)
    return obj.residue


def normalize_chain(chain: Chain, ignore_residues: set) -> Chain:
    new_chain = Chain(chain.id)
    for residue in chain:
        if residue.resname in ignore_residues:
            continue
        try:
            new_chain.add(normalize_residue(residue))
        except UnknownResidueError:
            print('Ignoring residue {}'.format(residue.resname))
    return new_chain


if __name__ == '__main__':
    from simulate import normalize_structure
    ignore_residues = set([
        'HOH',
    ])
    normalize_structure('pdb1aki.ent', pdb_id='1aki', model_id=0,
                        chain_id='A', ignore_residues=ignore_residues)
