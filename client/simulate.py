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
flags.DEFINE_string("foldy_operator_host", 'foldy-operator',
                    "foldy operator host")
flags.DEFINE_integer("foldy_operator_port", 8090, "foldy operator port")
flags.DEFINE_float(
    "emtol", 10.0,
    "stop minimization when the maximum force below this many kJ")
flags.DEFINE_float("emstep", 0.01, "minimization step size")
flags.DEFINE_integer("nsteps", 1000, "simulation steps")
flags.DEFINE_float("dt", 0.0002, "simulation time step")


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


def normalize_structure(input_path: str,
                        pdb_id: str,
                        model_id: int,
                        chain_id: str,
                        ignore_residues: set):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", PDBConstructionWarning)
        parser = PDBParser()
        structure = parser.get_structure(pdb_id, input_path)
        if not model_id in structure.child_dict:
            raise ValueError(
                'model "{}" not found in "{}", options are {}'.format(model_id, pdb_id, list(structure.child_dict.keys())))
        model = structure.child_dict[model_id]
        if not chain_id in model.child_dict:
            raise ValueError(
                'chain "{}" not found in "{}" model "{}", options are {}'.format(chain_id, pdb_id, model_id, list(model.child_dict.keys())))
        chain = model.child_dict[chain_id]

        new_chain = normalize_chain(chain, ignore_residues=ignore_residues)
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


def prepare_input_data(pdb_id: str,
                       model_id: str,
                       chain_id: str,
                       ignore_residues: set) -> str:
    s3 = boto3.resource('s3',
                        region_name=FLAGS.region,
                        endpoint_url=FLAGS.endpoint)
    bucket = s3.Bucket(name=FLAGS.bucket)
    path = '/tmp/pdb{}.ent.gz'.format(pdb_id)
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
    return normalize_structure('/tmp/pdb{}.ent'.format(pdb_id),
                               pdb_id=pdb_id,
                               model_id=model_id,
                               chain_id=chain_id,
                               ignore_residues=ignore_residues)


def run_cmd(args, expect_exitcode=0):
    proc = subprocess.run(args, stdout=PIPE, stderr=PIPE)
    if expect_exitcode != None and proc.returncode != expect_exitcode:
        msg = 'expected exit code {} from `{}`, got exit code {}: {}'.format(
            expect_exitcode, args, proc.returncode, str(proc.stdout))
        if proc.stderr:
            msg += ' ' + str(proc.stderr)
        raise ValueError(msg)


def run_simulation(pdb_id: str, input_pdb: str, emtol: float, emstep: float,
                   nsteps: int, dt: float):
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
        str(dt)
    ])
    return 0


def trjconv(pdb_id: str, nsteps: int):
    for i in range(nsteps):
        proc = subprocess.run(
            ['./trjconv.sh', pdb_id,
                str(i), str(i + 1)],
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


def upload(pdb_id: str, correlation_id: str):
    run_cmd(['./upload.sh', pdb_id, correlation_id])
    print('Results uploaded')


def calc_deltas(structures: List[Structure]):
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
                                       ignore_residues=ignore_residues)
        print('Running simulation...')
        run_simulation(pdb_id=pdb_id,
                       input_pdb=input_pdb,
                       emtol=FLAGS.emtol,
                       emstep=FLAGS.emstep,
                       nsteps=FLAGS.nsteps,
                       dt=FLAGS.dt)
        print('Extracting frames...')
        trjconv(pdb_id, FLAGS.nsteps)
        #deltas = calc_deltas(structures)
        print('Uploading results...')
        upload(pdb_id, correlation_id)
    except:
        _, value, _ = sys.exc_info()
        report_error(str(value))
        raise
    return 0


if __name__ == '__main__':
    app.run(main)
