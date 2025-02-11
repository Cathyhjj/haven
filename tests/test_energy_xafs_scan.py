import pytest

from ophyd import sim
import numpy as np

from haven import align_slits, energy_scan, xafs_scan, registry, KRange


@pytest.fixture()
def mono_motor():
    return sim.SynAxis(name="mono_energy", labels={"motors", "energies"})


@pytest.fixture()
def id_gap_motor():
    return sim.SynAxis(name="id_gap_energy", labels={"motors", "energies"})


@pytest.fixture()
def exposure_motor():
    return sim.Signal(name="exposure")


@pytest.fixture()
def energies():
    return np.linspace(8300, 8500, 100)


@pytest.fixture()
def I0(sim_registry):
    # Register an ion chamber
    I0 = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chambers"},
    )
    sim_registry.register(I0)
    return I0


def test_energy_scan_basics(mono_motor, id_gap_motor, energies, RE):
    exposure_time = 1e-3
    # Set up fake detectors and motors
    I0_exposure = sim.SynAxis(
        name="I0_exposure",
        labels={
            "exposures",
        },
    )
    It_exposure = sim.SynAxis(
        name="It_exposure",
        labels={
            "exposures",
        },
    )
    I0 = sim.SynGauss(
        name="I0",
        motor=mono_motor,
        motor_field="mono_energy",
        center=np.median(energies),
        Imax=1,
        sigma=1,
        labels={"detectors"},
    )
    It = sim.SynSignal(
        func=lambda: 1.0,
        name="It",
        exposure_time=exposure_time,
    )
    # Execute the plan
    scan = energy_scan(
        energies,
        detectors=[I0, It],
        exposure=exposure_time,
        energy_positioners=[mono_motor, id_gap_motor],
        time_positioners=[I0_exposure, It_exposure],
    )
    RE(scan)
    # Check that the mono and ID gap ended up in the right position
    assert mono_motor.get().readback == np.max(energies)
    assert id_gap_motor.get().readback == np.max(energies)
    assert I0_exposure.get().readback == exposure_time
    assert It_exposure.get().readback == exposure_time


def test_raises_on_empty_positioners(RE, energies):
    with pytest.raises(ValueError):
        RE(energy_scan(energies, energy_positioners=[]))


def test_single_range(mono_motor, exposure_motor, I0):
    E0 = 10000
    expected_energies = np.arange(9990, 10001, step=1)
    expected_exposures = np.asarray([1.0])
    scan = xafs_scan(
        -10,
        1,
        1,
        0,
        E0=E0,
        energy_positioners=[mono_motor],
        time_positioners=[exposure_motor],
    )
    # Check that the mono motor is moved to the correct positions
    scan_list = list(scan)
    real_energies = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "mono_energy"
    ]
    np.testing.assert_equal(real_energies, expected_energies)
    # Check that the exposure is set correctly
    real_exposures = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "exposure"
    ]
    np.testing.assert_equal(real_exposures, expected_exposures)


def test_multi_range(mono_motor, exposure_motor, I0):
    E0 = 10000
    expected_energies = np.concatenate(
        [
            np.arange(9990, 10001, step=2),
            np.arange(10001, 10011, step=1),
        ]
    )
    expected_exposures = np.asarray([0.5, 1.0])
    scan = xafs_scan(
        -10,
        2,
        0.5,
        0,
        1,
        1.0,
        10,
        E0=E0,
        energy_positioners=[mono_motor],
        time_positioners=[exposure_motor],
    )
    # Check that the mono motor is moved to the correct positions
    scan_list = list(scan)
    real_energies = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "mono_energy"
    ]
    np.testing.assert_equal(real_energies, expected_energies)
    # Check that the exposure is set correctly
    real_exposures = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "exposure"
    ]
    np.testing.assert_equal(real_exposures, expected_exposures)


def test_exafs_k_range(mono_motor, exposure_motor, I0):
    """Ensure that passing in k_min, etc. produces an energy range
    in K-space.

    """
    E0 = 10000
    krange = KRange(E_min=10, k_max=14, k_step=0.5, k_weight=0.5, exposure=0.75)
    expected_energies = krange.energies() + E0
    expected_exposures = krange.exposures()
    scan = xafs_scan(
        E_min=10,
        k_step=0.5,
        k_max=14,
        k_exposure=0.75,
        k_weight=0.5,
        E0=E0,
        energy_positioners=[mono_motor],
        time_positioners=[exposure_motor],
    )
    # Check that the mono motor is moved to the correct positions
    scan_list = list(scan)
    real_energies = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "mono_energy"
    ]
    np.testing.assert_equal(real_energies, expected_energies)
    # Check that the exposure is set correctly
    real_exposures = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "exposure"
    ]
    np.testing.assert_equal(real_exposures, expected_exposures)


def test_named_E0(mono_motor, exposure_motor, I0):
    expected_energies = np.concatenate(
        [
            np.arange(8323, 8334, step=2),
            np.arange(8334, 8344, step=1),
        ]
    )
    expected_exposures = np.asarray([0.5, 1.0])
    scan = xafs_scan(
        -10,
        2,
        0.5,
        0,
        1,
        1.0,
        10,
        E0="Ni_K",
        energy_positioners=[mono_motor],
        time_positioners=[exposure_motor],
    )
    # Check that the mono motor is moved to the correct positions
    scan_list = list(scan)
    real_energies = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "mono_energy"
    ]
    np.testing.assert_equal(real_energies, expected_energies)
    # Check that the exposure is set correctly
    real_exposures = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "exposure"
    ]
    np.testing.assert_equal(real_exposures, expected_exposures)


def test_remove_duplicate_energies(mono_motor, exposure_motor, I0):
    plan = xafs_scan(
        -4,
        2,
        1.0,
        6,
        34,
        1.0,
        40,
        E0=8333,
        energy_positioners=[mono_motor],
        time_positioners=[exposure_motor],
    )
    msgs = list(plan)
    set_msgs = [m for m in msgs if m.command == "set" and m.obj.name == "mono_energy"]
    read_msgs = [m for m in msgs if m.command == "read" and m.obj.name == "I0"]
    energies = [m.args[0] for m in set_msgs]
    # Make sure we only read each point once
    assert len(read_msgs) == len(energies)
