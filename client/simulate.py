import boto3
import tempfile
import gzip
import sys
import time
from typing import List
import os
from absl import flags, app
import botocore
import warnings
import http.client
import json
import shutil
import subprocess
from subprocess import PIPE
from Bio.PDB.PDBParser import PDBParser
from Bio.PDB.PDBExceptions import PDBConstructionWarning
from Bio.PDB import PDBIO
from Bio.PDB.Structure import Structure, Entity
from Bio.PDB.Model import Model
from Bio.PDB.Residue import Residue
from Bio.PDB.Chain import Chain
from Bio.PDB.Atom import Atom
from normalize import normalize_chain

script_dir = os.path.dirname(sys.argv[0])

FLAGS = flags.FLAGS

flags.DEFINE_string("region", 'us-east-1', "S3 region")
flags.DEFINE_string("bucket", 'pdb', 'S3 bucket name')
flags.DEFINE_string("endpoint", 'https://sfo2.digitaloceanspaces.com',
                    "S3 endpoint")
flags.DEFINE_string("pdb_id", None, "pdb structure ID")
flags.DEFINE_integer("model_id", None, "model ID")
flags.DEFINE_string("chain_id", None, "chain ID")
flags.DEFINE_string("correlation_id", None, "correlation ID")
flags.DEFINE_string(
    "primary", None, "input primary sequence (sanity check, optional)")
flags.DEFINE_string("mask", None, "input mask (sanity check, optional)")
flags.DEFINE_string("foldy_operator_host", 'foldy-operator',
                    "foldy operator host")
flags.DEFINE_integer("foldy_operator_port", 8090, "foldy operator port")
flags.DEFINE_float(
    "emtol", 10.0,
    "stop minimization when the maximum force below this many kJ")
flags.DEFINE_float("emstep", 0.01, "minimization step size")
flags.DEFINE_integer("nsteps", 1000, "simulation steps")
flags.DEFINE_float("dt", 0.0002, "simulation time step")
flags.DEFINE_integer("seed", -1, "Langevin dynamics seed")
flags.DEFINE_boolean("no_report", False, "skip error report")


class PDBNotFoundException(Exception):
    def __init__(self, pdb_id):
        super(PDBNotFoundException, self).__init__()
        self.pdb_id = pdb_id

    def __str__(self):
        return 'pdb \'{}\' not found'.format(self.pdb_id)


def report_error(msg: str):
    print('Reporting error: {}'.format(msg))
    conn = http.client.HTTPConnection(FLAGS.foldy_operator_host,
                                      FLAGS.foldy_operator_port,
                                      timeout=10)
    json_data = json.dumps({
        'msg': msg,
        'correlation_id': FLAGS.correlation_id,
    })
    headers = {'Content-type': 'application/json'}
    conn.request('POST', '/error', json_data, headers)
    response = conn.getresponse()
    if response.code != 200:
        raise ValueError('error report: expected code 200, got {}'.format(
            response.code))


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
        super(UnknownResnameError, self).__init__('unknown resname "{}"'.format(resname))

def resname_to_abbrev(resname: str) -> str:
    if not resname in _resname_abbrev:
        raise UnknownResnameError(resname)
    return _resname_abbrev[resname]


def normalize_structure(input_path: str,
                        pdb_id: str,
                        model_id: int,
                        chain_id: str,
                        ignore_residues: set,
                        primary=None,
                        mask=None):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", PDBConstructionWarning)
        parser = PDBParser()
        structure = parser.get_structure(pdb_id, input_path)
        if not model_id in structure.child_dict:
            if primary and model_id-1 in structure.child_dict:
                # later on we'll ensure primary sequence is correct
                model = structure.child_dict[model_id-1]
                print('Supposing model {} is {}...'.format(model_id-1, model_id))
            else:
                raise ValueError(
                    'model "{}" not found in "{}", options are {}'.format(model_id, pdb_id, list(structure.child_dict.keys())))
        else:
            model = structure.child_dict[model_id]
        if not chain_id in model.child_dict:
            raise ValueError(
                'chain "{}" not found in "{}" model "{}", options are {}'.format(chain_id, pdb_id, model_id, list(model.child_dict.keys())))
        chain = model.child_dict[chain_id]

        new_chain = normalize_chain(chain,
                                    ignore_residues=ignore_residues)

        if primary:
            assert mask

            # verify that the sequence is what we expect
            abbrev = []
            for residue in new_chain:
                try:
                    abbrev.append(resname_to_abbrev(residue.resname))
                except UnknownResnameError:
                    print('Skipping residue "{}"'.format(residue.resname))
                    pass
            
            # extract the known primary sequence using the mask
            known_primary = []
            for r, m in zip(primary, mask):
                if m != '+':
                    continue
                known_primary.append(r)

            # ensure the sequence lengths match
            if len(abbrev) != len(known_primary):
                raise ValueError('length of normalized chain ({}) not match supplied primary sequence ({})'.format(
                    len(abbrev), len(known_primary)))
            # ensure residue identities match
            for i, (got, expected) in enumerate(zip(abbrev, known_primary)):
                if got != expected:
                    raise ValueError('mismatch residue at position {} (got {}, expected {})'.format(i, got, expected))

        new_model = Model(model.id)
        new_model.add(new_chain)
        new_structure = Structure(structure.id)
        new_structure.add(new_model)

        out_path = input_path + '.norm'
        io = PDBIO()
        io.set_structure(new_structure)
        io.save(out_path)
        print('Normalized {} to {}'.format(pdb_id, out_path))
        return out_path

tmpdir = '/tmp'

def prepare_input_data(pdb_id: str,
                       model_id: str,
                       chain_id: str,
                       ignore_residues: set,
                       primary=None,
                       mask=None) -> str:
    s3 = boto3.resource('s3',
                        region_name=FLAGS.region,
                        endpoint_url=FLAGS.endpoint)
    bucket = s3.Bucket(name=FLAGS.bucket)
    path = os.path.join(tmpdir, 'pdb{}.ent.gz'.format(pdb_id))
    try:
        object = bucket.Object('pdb{}.ent.gz'.format(pdb_id))
        with open(path, 'wb') as f:
            object.download_fileobj(f)
    except botocore.exceptions.ClientError:
        _, value, _ = sys.exc_info()
        if value.response['Error']['Code'] == '404':
            raise PDBNotFoundException(pdb_id)
        raise
    run_cmd(['gzip', '-df', path])
    return normalize_structure(os.path.join(tmpdir, 'pdb{}.ent'.format(pdb_id)),
                               pdb_id=pdb_id,
                               model_id=model_id,
                               chain_id=chain_id,
                               ignore_residues=ignore_residues,
                               primary=primary,
                               mask=mask)


def run_cmd(args, expect_exitcode=0):
    proc = subprocess.run(args, stdout=PIPE, stderr=PIPE)
    if expect_exitcode != None and proc.returncode != expect_exitcode:
        msg = 'expected exit code {} from `{}`, got exit code {}: {}'.format(
            expect_exitcode, args, proc.returncode, str(proc.stdout))
        if proc.stderr:
            msg += ' ' + str(proc.stderr)
        raise ValueError(msg)


def run_simulation(pdb_id: str,
                   input_pdb: str,
                   emtol: float,
                   emstep: float,
                   nsteps: int,
                   dt: float,
                   seed: int):
    # TODO
    # it is unclear why this number needs to be ~5x
    # larger in order to generate enough frame data.
    # This needs investigating, but for now I don't
    # really care about wasting a bit of compute.
    nsteps *= 5

    run_cmd([
        './run-simulation.sh',
        pdb_id,
        input_pdb,
        str(emtol),
        str(emstep),
        str(nsteps),
        str(dt),
        str(seed),
    ])
    return 0


def trjconv(pdb_id: str, nsteps: int) -> List[str]:
    structure_paths = []
    for i in range(nsteps):
        proc = subprocess.run(
            ['./trjconv.sh', pdb_id,
                str(i), str(i)],
            stdout=PIPE,
            stderr=PIPE)
        if proc.returncode != 0:
            print('trjconv {}'.format(i))
            print(str(proc.stdout))
            print(str(proc.stderr))
            raise ValueError('error converting frame #{}: {} {}'.format(
                i, str(proc.stdout), str(proc.stderr)))
        path = '{}_minim_{}.pdb'.format(pdb_id, i)
        assert os.path.isfile(path)
        structure_paths.append(path)
    return structure_paths

def upload(pdb_id: str, correlation_id: str):
    run_cmd(['./upload.sh', pdb_id, correlation_id])
    print('Results uploaded')


def calc_deltas(pdb_id: str, structures: List[str]):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", PDBConstructionWarning)
        parser = PDBParser()
        for input_path in structures:
            structure = parser.get_structure(pdb_id, input_path)
            print(input_path)
            for model in structure:
                print('\tmodel {}:'.format(model.id))
                for chain in model:
                    print('\t\tchain {}:'.format(chain))
                    for residue in chain.child_list[:10]:
                        print('\t\t\t{}', residue.resname)
    # for i, (a, b) in enumerate(zip(structures[:-1], structures[1:])):
    #    for (model_a, model_b) in zip(a, b):
    #        for (chain_a, chain_b) in zip(model_a, model_b):
    #            for (residue_a, residue_b) in zip(chain_a, chain_b):
    #                for (atom_a, atom_b) in zip(residue_a, residue_b):
    #                    if atom_a.element != atom_b.element:
    #                        raise ValueError('element mismatch ({} and {})'.format(atom_a.element, atom_b.element))
    #                    dcoord = atom_b.coord - atom_a.coord
    #                    print('{} {}'.format(atom_a.element, dcoord))
    print('Done!')
    return None


def main(_argv):
    ignore_residues = set([
        'HOH',
        'ANP',
        ' MG',
    ])
    try:
        if not FLAGS.pdb_id:
            raise ValueError('missing pdb_id')
        if not FLAGS.correlation_id:
            raise ValueError('missing correlation_id')
        pdb_id = FLAGS.pdb_id.lower()  # normalize to lowercase
        print('Simulating {} for {} steps'.format(pdb_id.upper(),
                                                  FLAGS.nsteps))
        correlation_id = FLAGS.correlation_id
        print('Preparing input data...')
        input_pdb = prepare_input_data(pdb_id=pdb_id,
                                       model_id=FLAGS.model_id,
                                       chain_id=FLAGS.chain_id,
                                       ignore_residues=ignore_residues,
                                       primary=FLAGS.primary,
                                       mask=FLAGS.mask)
        print('Running simulation...')
        run_simulation(pdb_id=pdb_id,
                       input_pdb=input_pdb,
                       emtol=FLAGS.emtol,
                       emstep=FLAGS.emstep,
                       nsteps=FLAGS.nsteps,
                       dt=FLAGS.dt,
                       seed=FLAGS.seed)
        print('Extracting frames...')
        structure_paths = trjconv(pdb_id, FLAGS.nsteps)
        calc_deltas(pdb_id, structure_paths)
        if not FLAGS.no_report:
            print('Uploading results...')
            upload(pdb_id, correlation_id)
    except:
        if not FLAGS.no_report:
            _, value, _ = sys.exc_info()
            report_error(str(value))
        raise
    return 0


if __name__ == '__main__':
    app.run(main)
