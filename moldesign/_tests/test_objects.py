"""
This module is mostly _fixtures_ - functions that create various objects for downstream testing.

There are a few tests here too, mostly to make sure the objects are created correctly in the first
place.
"""

import collections
import random
import itertools

import pytest
import numpy as np

import moldesign as mdt
from moldesign import units as u

from .helpers import get_data_path

registered_types = {}


def typedfixture(*types, **kwargs):
    """This is a decorator that lets us associate fixtures with one or more arbitrary types.
    We'll later use this type to determine what tests to run on the result"""

    def fixture_wrapper(func):
        for t in types:
            registered_types.setdefault(t, []).append(func.__name__)
        return pytest.fixture(**kwargs)(func)

    return fixture_wrapper


######################################
# Test the basic data structures

TESTDICT = collections.OrderedDict((('a', 'b'),
                                    ('c', 3),
                                    ('d', 'e'),
                                    ('a', 1),
                                    (3, 35)))


@typedfixture('object')
def dotdict():
    dd = mdt.utils.classes.DotDict(TESTDICT)
    return dd


@typedfixture('object')
def ordered_dotdict():
    dd = mdt.utils.classes.OrderedDotDict(TESTDICT)
    return dd


@pytest.mark.parametrize('objkey', 'dotdict ordered_dotdict'.split())
def test_dotdict(objkey, request):
    dd = request.getfuncargvalue(objkey)

    # basic lookups and functions
    assert len(dd) == len(TESTDICT)
    assert dd.a == TESTDICT['a']
    assert dd.d == TESTDICT['d']
    assert set(dd.keys()) == set(TESTDICT.keys())
    assert set(dd.values()) == set(TESTDICT.values())

    # __contains__ methods
    for item in TESTDICT:
        assert item in dd

    # item deletion
    del dd.d
    assert 'd' not in dd
    assert len(dd) == len(TESTDICT) - 1
    del dd[3]
    assert 3 not in dd

    # equivalence of items and attrs
    dd['k'] = 12345
    assert getattr(dd, 'k') == 12345
    setattr(dd, 'newkey', -42)
    assert dd['newkey'] == -42


def test_ordered_dotdict(ordered_dotdict):
    assert ordered_dotdict.keys() == TESTDICT.keys()
    assert ordered_dotdict.values() == TESTDICT.values()
    assert ordered_dotdict.items() == TESTDICT.items()

    for iterator_method in '__iter__ iterkeys itervalues iteritems'.split():
        odd_iter = getattr(ordered_dotdict, iterator_method)()
        test_iter = getattr(TESTDICT, iterator_method)()
        for gotval, testval in itertools.izip_longest(odd_iter, test_iter, fillvalue=None):
            assert gotval == testval, 'Iterator %s failed' % iterator_method


def test_h2_positions(h2):
    atom1, atom2 = h2.atoms
    assert (atom1.position == np.array([0.5, 0.0, 0.0]) * u.angstrom).all()
    assert atom2.x == -0.5 * u.angstrom
    assert atom1.distance(atom2) == 1.0 * u.angstrom



# Some objects with units
@typedfixture('object')
def list_of_units():
    return [1.0 * u.angstrom, 1.0 * u.nm, 1.0 * u.a0]


@typedfixture('object', 'equality')
def simple_unit_array():
    return np.array([1.0, -2.0, 3.5]) * u.angstrom


@typedfixture('object', 'equality')
def unit_number():
    return 391.23948 * u.ureg.kg * u.ang / u.alpha


######################################
# Test underlying elements
@typedfixture('submolecule')
def carbon_atom():
    atom1 = mdt.Atom('C')
    return atom1


def test_carbon_atom(carbon_atom):
    assert carbon_atom.symbol == 'C'
    assert carbon_atom.mass == 12.0 * u.amu


@typedfixture('submolecule')
def carbon_copy(carbon_atom):
    atoms = carbon_atom.copy()
    return atoms


######################################
# Tests around hydrogen
@typedfixture('molecule')
def h2():
    atom1 = mdt.Atom('H')
    atom1.x = 0.5 * u.angstrom
    atom2 = mdt.Atom(atnum=1)
    atom2.position = [-0.5, 0.0, 0.0] * u.angstrom
    h2 = mdt.Molecule([atom1, atom2], name='h2')
    atom1.bond_to(atom2, 1)
    return h2


@typedfixture('molecule')
def h2_harmonic():
    mol = h2()
    SPRING_CONSTANT = 1.0 * u.kcalpermol / (u.angstrom ** 2)
    model = mdt.models.HarmonicOscillator(k=SPRING_CONSTANT)
    integrator = mdt.integrators.VelocityVerlet(timestep=0.5*u.fs, frame_interval=30)
    mol.set_energy_model(model)
    mol.set_integrator(integrator)
    return mol


@typedfixture('submolecule')
def h2_trajectory(h2_harmonic):
    mol = h2_harmonic
    mol.atoms[0].x = 1.0 * u.angstrom
    mol.momenta *= 0.0
    traj = mol.run(500)
    return traj


def test_h2_trajectory(h2_trajectory):
    """
    Check if the trajectory is the sine wave that we expect
    """
    traj = h2_trajectory
    mol = traj.mol
    k = mol.energy_model.params.k
    period = 2*u.pi*np.sqrt(mol.atoms[0].mass/k)
    for frame in traj.frames:
        period_progress = (frame.time % period) / period
        if period_progress < 0.1 or period_progress > 0.9:
            # check for expected peaks of sine wave
            assert frame.positions[0, 0] > 0.1 * u.angstrom
        elif 0.4 < period_progress < 0.6:
            # check for expected troughs of sine wave
            assert frame.positions[0, 0] < -0.1 * u.angstrom


@typedfixture('molecule')
def h2_traj_tempmol(h2_trajectory):
    return h2_trajectory._tempmol


@typedfixture('molecule')
def h2_harmonic_copy(h2_harmonic):
    return mdt.Molecule(h2_harmonic)


@typedfixture('submolecule')
def copy_atoms_from_h2_harmonic(h2_harmonic):
    atoms = h2_harmonic.atoms.copy()
    return atoms

@typedfixture('molecule')
def h2_harmonic_thats_been_copied(h2_harmonic):
    temp = mdt.Molecule(h2_harmonic)
    return h2_harmonic


@typedfixture('submolecule')
def h2_harmonic_atoms(h2_harmonic):
    return h2_harmonic.atoms


######################################
# Tests around PDB ID 3AID
@typedfixture('molecule', scope='session')
def pdb3aid():
    mol = mdt.from_pdb('3AID')
    return mol


@typedfixture('submolecule')
def ligand_residue_3aid(pdb3aid):
    unknown = pdb3aid.chains['A'](type='unknown')
    assert len(unknown) == 1
    return unknown[0]


@typedfixture('submolecule')
def ligand_3aid_atoms(ligand_residue_3aid):
    return ligand_residue_3aid.atoms


@typedfixture('molecule')
def ligand3aid(ligand_residue_3aid):
    newmol = mdt.Molecule(ligand_residue_3aid)
    return newmol


@pytest.fixture
def random_atoms_from_3aid(pdb3aid):
    atoms = mdt.molecules.atomcollections.AtomList(random.sample(pdb3aid.atoms, 10))
    return atoms


def test_h2(h2):
    mol = h2
    assert mol.num_atoms == 2
    assert mol.atoms[0].symbol == mol.atoms[1].symbol == 'H'


def test_3aid(pdb3aid):
    mol = pdb3aid
    assert len(mol.chains) == 2


def test_3aid_ligand_search(pdb3aid):
    mol = pdb3aid
    unknown = mol.chains['A'](type='unknown')
    proteina = mol.chains['A'](type='protein')
    proteinb = mol.chains['B'](type='protein')
    assert len(unknown) == 1
    assert len(proteina) == len(proteinb) == 99


def test_ligand3aid(ligand3aid):
    mol = ligand3aid
    assert len(mol.chains) == 1
    assert len(mol.residues) == 1



######################################
# Tests around a piece of DNA
@typedfixture('molecule', scope='session')
def nucleic():
    # ACTG.pdb contains a molecule generated using mdt.build_dna('ACTG')
    mol = mdt.read(get_data_path('ACTG.pdb'))
    return mol


def test_nucleic_build(nucleic):
    mol = nucleic
    assert mol.num_chains == 2
    assert mol.num_residues == 8
    assert mol.chains[0] is mol.chains['A']
    assert mol.chains[1] is mol.chains['B']
    assert len(mol.chains[0].residues) == len(mol.chains[1].residues) == 4


moldesign_objects = registered_types['molecule'] + registered_types['submolecule']
all_objects = registered_types['object'] + moldesign_objects
