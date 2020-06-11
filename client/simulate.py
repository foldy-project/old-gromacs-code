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
import re
import http.client
import json
import shutil
import subprocess
from Bio.PDB.PDBParser import PDBParser
from Bio.PDB.PDBExceptions import PDBConstructionWarning
from Bio.PDB import PDBIO
from Bio.PDB.Structure import Structure, Entity
from Bio.PDB.Model import Model
from Bio.PDB.Residue import Residue
from Bio.PDB.Chain import Chain
from Bio.PDB.Atom import Atom
from normalize import normalize_structure, normalize_structure_charmming, ChainLengthError
from util import cleanup
from errors import ChainLengthError

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


tmpdir = '/tmp'


def prepare_input_data(pdb_id: str,
                       model_id: str,
                       chain_id: str,
                       primary: str,
                       mask: str,
                       verbose=False) -> str:
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
    pdb_path = os.path.join(tmpdir, 'pdb{}.ent'.format(pdb_id))
    try:
        return normalize_structure(pdb_path,
                                   pdb_id=pdb_id,
                                   model_id=model_id,
                                   chain_id=chain_id,
                                   primary=primary,
                                   mask=mask,
                                   save=True,
                                   verbose=verbose)
    finally:
        os.unlink(pdb_path)


def run_cmd(args, expect_exitcode=0):
    proc = subprocess.run(args, capture_output=True)
    if expect_exitcode != None and proc.returncode != expect_exitcode:
        msg = 'expected exit code {} from `{}`, got exit code {}: {}'.format(
            expect_exitcode, args, proc.returncode, proc.stdout.decode('unicode_escape'))
        if proc.stderr:
            msg += ' ' + proc.stderr.decode('unicode_escape')
        raise ValueError(msg)


class GromacsError(Exception):
    def __init__(self, category: str, stderr: str, match: re.Match):
        message = stderr[match.start():match.end()].replace(
            '\n', ' ').strip() if match else stderr
        super(GromacsError, self).__init__(self, message)
        self.stderr = stderr
        self.category = category
        self.message = message


class BadTopologyError(GromacsError):
    """ Indicates there are residues with missing atoms.
    TODO: use machine learning to heal this error
    """
    def __init__(self, stderr: str, match: re.Match):
        super(BadTopologyError, self).__init__('bad_topology', stderr, match)


class IncompleteRingError(GromacsError):
    """ Indicates that a histidine is missing ring atoms.
    TODO: use machine learning to heal this error
    """
    def __init__(self, stderr: str, match: re.Match):
        super(IncompleteRingError, self).__init__(
            'incomplete_ring', stderr, match)


class SettleWaterError(GromacsError):
    """ One or more water molecules can not be settled. Check for bad contacts and/or reduce the timestep if appropriate
    """
    def __init__(self, stderr: str, match: re.Match):
        super(SettleWaterError, self).__init__('settle_water', stderr, match)


class UnknownSimulationError(GromacsError):
    def __init__(self, stderr: str):
        super(UnknownSimulationError, self).__init__('unknown', stderr, None)


_gromacs_errors = [
    (
        r'Residue ([0-9]+) named ([A-Z]+) of a molecule in the input file was mapped\nto an entry in the topology database, but the atom .+ used in\nthat entry is not found in the input file.',
        BadTopologyError,
    ),
    (
        r'\nIncomplete ring in .+\n',
        IncompleteRingError,
    ),
    (
        r'One or more water molecules can not be settled\.\nCheck for bad contacts and\/or reduce the timestep if appropriate\.\n',
        SettleWaterError,
    ),
]


def run_simulation(pdb_id: str,
                   model_id: int,
                   chain_id: str,
                   primary: str,
                   mask: str,
                   emstep: float,
                   nsteps: int,
                   dt: float,
                   seed: int,
                   verbose=False):
    # TODO
    # it is unclear why this number needs to be ~5x
    # larger in order to generate enough frame data.
    # This needs investigating, but for now I don't
    # really care about wasting a bit of compute.
    sim_nsteps = nsteps * 5
    try:
        input_pdb = prepare_input_data(pdb_id=pdb_id,
                                       model_id=model_id,
                                       chain_id=chain_id,
                                       primary=primary,
                                       mask=mask,
                                       verbose=verbose)
        proc = subprocess.run([
            './run-simulation.sh',
            input_pdb,
            str(emstep),
            str(sim_nsteps),
            str(dt),
            str(seed),
        ], capture_output=True)
        # print(proc.stdout.decode('unicode_escape'))
        if proc.returncode != 0:
            # Decode GROMACS stderr into a custom Exception
            stderr = proc.stderr.decode('unicode_escape')
            for pattern, exception in _gromacs_errors:
                match = re.search(pattern, stderr, re.M | re.I)
                if match:
                    raise exception(stderr, match)
            raise UnknownSimulationError(stderr)

        # go ahead and free simulation resources early
        cleanup('tmp_')
        # convert frames
        #print('Converting frames...')
        frames = trjconv(input_xtc='out_traj.xtc',
                         input_tpr='out_em.tpr',
                         nsteps=nsteps)
        return frames
    finally:
        cleanup('tmp_')
        cleanup('out_')


def trjconv(input_xtc: str,
            input_tpr: str,
            nsteps: int) -> List[str]:
    structure_paths = []
    try:
        for i in range(nsteps):
            proc = subprocess.run(['./trjconv.sh',
                                   input_xtc,
                                   input_tpr,
                                   str(i),
                                   ],
                                  capture_output=True)
            if proc.returncode != 0:
                #print('trjconv {}'.format(i))
                # print(proc.stdout.decode('unicode_escape'))
                print(proc.stderr.decode('unicode_escape'))
                raise ValueError('error converting frame {}'.format(i))
            path = '{}.pdb'.format(i)
            assert os.path.isfile(path)
            structure_paths.append(path)
    except:
        [os.unlink(path) for path in structure_paths]
        raise
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
                                       primary=FLAGS.primary,
                                       mask=FLAGS.mask)
        print('Running simulation...')
        # structure_paths = run_simulation(pdb_id=pdb_id,
        #                                 input_pdb=input_pdb,
        #                                 emstep=FLAGS.emstep,
        #                                 nsteps=FLAGS.nsteps,
        #                                 dt=FLAGS.dt,
        #                                 seed=FLAGS.seed)
        print('Extracting frames...')
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
