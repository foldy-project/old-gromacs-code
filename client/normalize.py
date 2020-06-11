from Bio.PDB.Residue import Residue
from Bio.PDB.Chain import Chain
from Bio.PDB.Atom import Atom
from Bio.PDB.Structure import Structure
from Bio.PDB.Model import Model
from Bio.PDB.PDBParser import PDBParser
from Bio.PDB.PDBExceptions import PDBConstructionWarning
from Bio.PDB import PDBIO
import warnings
from absl import app, flags
import subprocess
from util import cleanup
import os
from errors import ChainLengthError


def get_unpacked_list(self):
    """
    Returns all atoms from the residue, in case of disordered,
    keep only first alt loc and remove the alt-loc tag
    Source: https://github.com/biopython/biopython/issues/455#issuecomment-291501909
    """
    atom_list = self.get_list()
    undisordered_atom_list = []
    for atom in atom_list:
        if atom.is_disordered():
            atom.altloc = " "
            undisordered_atom_list.append(atom)
        else:
            undisordered_atom_list.append(atom)
    return undisordered_atom_list


Residue.get_unpacked_list = get_unpacked_list


def get_atoms_from_desc(residue: Residue, description: list):
    atoms = []
    for i, (element, id) in enumerate(description):
        if not id in residue.child_dict:
            raise ValueError('atom "{}" not found in residue {}<{}>'.format(
                id, residue.resname, residue.id))
        atom = residue.child_dict[id]
        if atom.element != element:
            raise ValueError(
                'expected element "{}" from atom {}, got element "{}" in residue {}<{}>'.format(element, i, atom.element, residue.resname, residue.id))
        atoms.append(atom)
    return atoms


class NormalizedResidue:
    def __init__(self, residue: Residue, description: list):
        self.residue = residue.copy()
        #self.residue = Residue(residue.id, residue.resname, residue.segid)
        # [self.residue.add(atom)
        # for atom in get_atoms_from_desc(residue, description)]


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
        super(UnknownResidueError, self).__init__(
            'unknown resname "{}"'.format(resname))


def get_residue_class(resname: str) -> object:
    if not resname in _classes:
        raise UnknownResidueError(resname)
    return _classes[resname]


def normalize_residue(residue: Residue) -> Residue:
    ty = get_residue_class(residue.resname)
    obj = ty(residue)
    return obj.residue


def normalize_chain(chain: Chain) -> Chain:
    new_chain = Chain(chain.id)
    for residue in chain:
        try:
            new_chain.add(normalize_residue(residue))
        except UnknownResidueError:
            pass
    return new_chain


_resname_abbrev = {
    'PRO': 'P',
    'MET': 'M',
    'ASP': 'D',
    'VAL': 'V',
    'SER': 'S',
    'HIS': 'H',
    'GLU': 'E',
    'GLN': 'Q',
    'ASN': 'N',
    'GLY': 'G',
    'ILE': 'I',
    'LYS': 'K',
    'TRP': 'W',
    'TYR': 'Y',
    'THR': 'T',
    'ARG': 'R',
    'PHE': 'F',
    'CYS': 'C',
    'LEU': 'L',
    'ALA': 'A',
}


class UnknownResnameError(ValueError):
    def __init__(self, resname: str):
        super(UnknownResnameError, self).__init__(
            'unknown resname "{}"'.format(resname))


def resname_to_abbrev(resname: str) -> str:
    if not resname in _resname_abbrev:
        raise UnknownResnameError(resname)
    return _resname_abbrev[resname]


def normalize_structure_charmming(input_path: str,
                                  pdb_id: str,
                                  model_id: int,
                                  chain_id: str,
                                  primary: str,
                                  mask: str,
                                  save=True,
                                  verbose=True):
    try:
        proc = subprocess.run(
            ['./normalize.sh', pdb_id, input_path], capture_output=True)
        print(proc.stdout.decode('unicode_escape'))
        if proc.returncode != 0:
            msg = 'expected exit code 0 from charmming_parser, got exit code {}: {}'.format(
                proc.returncode, proc.stdout.decode('unicode_escape'))
            if proc.stderr:
                msg += ' ' + proc.stderr.decode('unicode_escape')
            raise ValueError(msg)
        files = [file for file in os.listdir('.')
                 if file.startswith('new_') and f'-{chain_id.lower()}-' in file and '-pro' in file]
        print(files)
        structure_path = f'{pdb_id}_{model_id}_{chain_id}.pdb'
        os.rename(files[0], structure_path)
        if save:
            return structure_path
        else:
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("ignore", PDBConstructionWarning)
                return PDBParser().get_structure(pdb_id, structure_path)
    except:
        raise
    finally:
        cleanup('new_')


def print_chains(structure: Structure):
    for model in structure:
        print(f'{model.id}')
        for chain in model:
            raw = []
            for residue in chain:
                try:
                    raw.append(resname_to_abbrev(residue.resname))
                except UnknownResnameError:
                    pass
            raw = ''.join(raw)
            print(f'\t{chain} {len(raw)} {raw}')


def normalize_structure(input_path: str,
                        pdb_id: str,
                        model_id: int,
                        chain_id: str,
                        primary: str,
                        mask: str,
                        save=True,
                        verbose=True):
    assert primary
    assert mask
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", PDBConstructionWarning)
        parser = PDBParser()
        structure = parser.get_structure(pdb_id, input_path)
        if not model_id in structure.child_dict:
            try_model_id = model_id-1
            model = None
            while try_model_id >= 0:
                if try_model_id in structure.child_dict:
                    model = structure.child_dict[try_model_id]
                    if verbose:
                        print('Supposing model {} is {}...'.format(
                            model_id-1, model_id))
                try_model_id -= 1
            if not model:
                raise ValueError(
                    'model "{}" not found in "{}", options are {}'.format(model_id, pdb_id, list(structure.child_dict.keys())))
        else:
            model = structure.child_dict[model_id]
        if not chain_id in model.child_dict:
            raise ValueError(
                'chain "{}" not found in "{}" model "{}", options are {}'.format(chain_id, pdb_id, model_id, list(model.child_dict.keys())))
        chain = model.child_dict[chain_id]

        new_chain = normalize_chain(chain)

        raw = []
        for residue in chain:
            try:
                raw.append(resname_to_abbrev(residue.resname))
            except UnknownResnameError:
                # if verbose:
                #    print('Skipping residue "{}"'.format(residue.resname))
                pass
        raw = ''.join(raw)

        # verify that the sequence is what we expect
        normalized = []
        for residue in new_chain:
            try:
                normalized.append(resname_to_abbrev(residue.resname))
            except UnknownResnameError:
                # if verbose:
                #    print('Skipping residue "{}"'.format(residue.resname))
                pass
        normalized = ''.join(normalized)

        # extract the known primary sequence using the mask
        masked_primary = []
        for r, m in zip(primary, mask):
            if m == '-':
                continue
            assert m == '+'
            masked_primary.append(r)
        masked_primary = ''.join(masked_primary)

        # ensure the sequence lengths match
        if len(normalized) != len(masked_primary):
            raise ChainLengthError(len(normalized), len(masked_primary))

        # ensure residue identities match
        for i, (got, expected) in enumerate(zip(normalized, masked_primary)):
            if got != expected:
                raise ValueError(
                    'mismatch residue at position {} (got {}, expected {})'.format(i, got, expected))

        new_model = Model(model.id)
        new_model.add(new_chain)
        new_structure = Structure(structure.id)
        new_structure.add(new_model)

        if save:
            out_path = input_path + '.norm'
            io = PDBIO()
            io.set_structure(new_structure)
            io.save(out_path)
            return out_path
        else:
            return new_structure


def main(_argv):
    FLAGS = flags.FLAGS
    import subprocess
    import os
    import boto3
    import botocore
    import sys
    from Bio.PDB import PDBList
    from simulate import PDBNotFoundException, prepare_input_data, run_simulation, BadTopologyError, IncompleteRingError, SettleWaterError, UnknownSimulationError, GromacsError
    from proteinnet import read_record
    import shutil

    def log_error(category: str, pdb_id: str, stderr: str):
        dir = f'/data/errors/{category}'
        try:
            os.mkdir(dir)
        except FileExistsError:
            pass
        with open(f'{dir}/{pdb_id}.txt', 'w') as f:
            f.write(stderr)
            
    #pdb_id = '2l0e'
    #model_id = 1
    #chain_id = 'A'
    #primary = 'AKKKDNLLFGSIISAVDPVAVLAVFEEIHKKKA'
    #mask = '-+++++++++++++++++++++++++++++++-'
    # try:
    #    structure_paths = run_simulation(pdb_id=pdb_id,
    #                                     model_id=model_id,
    #                                     chain_id=chain_id,
    #                                     primary=primary,
    #                                     mask=mask,
    #                                     emstep=FLAGS.emstep,
    #                                     nsteps=5,
    #                                     dt=FLAGS.dt,
    #                                     seed=FLAGS.seed)
    #    [os.unlink(path) for path in structure_paths]
    #    print('Normalized {}'.format(pdb_id))
    # except:
    #    _, value, _ = sys.exc_info()
    #    print('Error normalizing {}: {}'.format(pdb_id, value))
    # sys.stdout.flush()

    input_path = os.getenv('PROTEINNET_PATH')
    if not input_path:
        raise ValueError('missing PROTEINNET_PATH environment variable')
    input_path = os.path.join(input_path, 'training_50')
    print('Reading data from {}'.format(input_path))
    success = 0
    total = 0

    if FLAGS.output:
        print('Saving output to {}'.format(FLAGS.output))
        try:
            os.remove(FLAGS.output)
        except:
            pass
        output = open(FLAGS.output, 'w')
    else:
        print('Warning: not saving output')
        output = None

    shutil.rmtree('/data/errors', ignore_errors=True)
    os.mkdir('/data/errors')

    try:
        with open(input_path, 'r') as input_file:
            while True:
                sys.stdout.flush()
                record = read_record(input_file, 20)
                if record is not None:
                    id = record["id"]
                    primary = record['primary']
                    mask = record['mask']
                    primary_len = len(primary)
                    assert primary_len == len(mask)
                    parts = id.split('_')
                    if len(parts) != 3:
                        # https://github.com/aqlaboratory/proteinnet/issues/1#issuecomment-375270286
                        continue
                    pdb_id = parts[0].lower()
                    model_id = int(parts[1])
                    chain_id = parts[2]
                    try:
                        total += 1
                        print(f'Normalizing {pdb_id}')
                        structure_paths = run_simulation(pdb_id=pdb_id,
                                                         model_id=model_id,
                                                         chain_id=chain_id,
                                                         primary=primary,
                                                         mask=mask,
                                                         emstep=FLAGS.emstep,
                                                         nsteps=10,
                                                         dt=FLAGS.dt,
                                                         seed=FLAGS.seed)
                        [os.unlink(path) for path in structure_paths]
                        success += 1
                        success_rate = success / total
                        print(f'Normalized {pdb_id} ({success_rate*100}% success)\n')
                        if output:
                            output.write('{},{},{},{},{}\n'.format(
                                pdb_id, model_id, chain_id, primary, mask))
                            output.flush()
                    except ChainLengthError as e:
                        print(f'Error normalizing {pdb_id}: {e}')
                        log_error('chain_length', pdb_id, e.message)
                    except GromacsError as e:
                        print(f'Error normalizing {pdb_id}: {e}')
                        log_error(e.category, pdb_id, e.stderr)
                    except PDBNotFoundException as e:
                        print(f'Error normalizing {pdb_id}: {e}')
                        log_error('pdb_not_found', pdb_id, str(e))
                    except KeyboardInterrupt:
                        raise
                    except:
                        _, value, _ = sys.exc_info()
                        print(f'Encountered unhandled error while normalizing {pdb_id}: {type(value)} {value}')
                        log_error('unhandled', pdb_id, str(value))
    finally:
        if output:
            output.close()


if __name__ == '__main__':
    flags.DEFINE_string("output", None, 'output file path', short_name='o')
    app.run(main)
