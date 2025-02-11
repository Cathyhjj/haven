from unittest.mock import MagicMock

import pytest
from bluesky import plans as bp
from bluesky.callbacks import CallbackBase
from bluesky.simulators import summarize_plan
from ophyd.sim import det, motor, SynAxis, make_fake_device, instantiate_fake_device
import os

from haven import plans, baseline_decorator, baseline_wrapper, run_engine
from haven.preprocessors import shutter_suspend_wrapper, shutter_suspend_decorator
from haven.instrument.aps import EpicsBssDevice, load_aps, ApsMachine


def test_shutter_suspend_wrapper(sim_aps, sim_shutters, sim_registry):
    # Check that the run engine does not have any shutter suspenders
    # Currently this test is fragile since we might add non-shutter
    # suspenders in the future.
    RE = run_engine(use_bec=False, connect_databroker=False)
    assert len(RE.suspenders) == 1
    # Check that the shutter suspenders get added
    plan = bp.count([det])
    msgs = list(plan)
    sub_msgs = [m for m in msgs if m[0] == "install_suspender"]
    unsub_msgs = [m for m in msgs if m[0] == "remove_suspender"]
    assert len(sub_msgs) == 0
    assert len(unsub_msgs) == 0
    # Now wrap the plan in the suspend wrapper
    plan = shutter_suspend_wrapper(bp.count([det]))
    msgs = list(plan)
    sub_msgs = [m for m in msgs if m[0] == "install_suspender"]
    unsub_msgs = [m for m in msgs if m[0] == "remove_suspender"]
    assert len(sub_msgs) == 2
    assert len(unsub_msgs) == 2
    # Now wrap the plan in the suspend decorator
    plan = shutter_suspend_decorator()(bp.count)([det])
    msgs = list(plan)
    sub_msgs = [m for m in msgs if m[0] == "install_suspender"]
    unsub_msgs = [m for m in msgs if m[0] == "remove_suspender"]
    assert len(sub_msgs) == 2
    assert len(unsub_msgs) == 2


def test_baseline_wrapper(sim_registry, sim_aps, event_loop):
    # Create a test device
    motor_baseline = SynAxis(name="baseline_motor", labels={"motors", "baseline"})
    sim_registry.register(motor_baseline)
    # Set up a callback to motor streams generated by runengine
    cb = CallbackBase()
    cb.start = MagicMock()
    cb.descriptor = MagicMock()
    cb.event = MagicMock()
    cb.stop = MagicMock()
    RE = run_engine(use_bec=False, connect_databroker=False)
    plan = bp.count([det], num=1)
    plan = baseline_wrapper(plan, devices="baseline")
    RE(plan, cb)
    # Check that the callback has the baseline stream inserted
    assert cb.start.called
    assert cb.descriptor.call_count > 1
    baseline_doc = cb.descriptor.call_args_list[0][0][0]
    primary_doc = cb.descriptor.call_args_list[1][0][0]
    assert baseline_doc["name"] == "baseline"
    assert "baseline_motor" in baseline_doc["data_keys"].keys()


def test_baseline_decorator(sim_registry, sim_aps):
    """Similar to baseline wrapper test, but used as a decorator."""
    # Create the decorated function before anything else
    func = baseline_decorator(devices="motors")(bp.count)
    # Create a test device
    motor_baseline = SynAxis(name="baseline_motor", labels={"motors"})
    sim_registry.register(motor_baseline)
    # Set up a callback to motor streams generated by runengine
    cb = CallbackBase()
    cb.start = MagicMock()
    cb.descriptor = MagicMock()
    cb.event = MagicMock()
    cb.stop = MagicMock()
    RE = run_engine(use_bec=False, connect_databroker=False)
    plan = func([det], num=1)
    RE(plan, cb)
    # Check that the callback has the baseline stream inserted
    assert cb.start.called
    assert cb.descriptor.call_count > 1
    baseline_doc = cb.descriptor.call_args_list[0][0][0]
    primary_doc = cb.descriptor.call_args_list[1][0][0]
    assert baseline_doc["name"] == "baseline"
    assert "baseline_motor" in baseline_doc["data_keys"].keys()


def test_metadata(sim_registry, sim_aps, monkeypatch):
    """Similar to baseline wrapper test, but used as a decorator."""
    # Load devices
    bss = instantiate_fake_device(EpicsBssDevice, name="bss", prefix="255id:bss:")
    bss.esaf.esaf_id._readback = "12345"
    bss.esaf.title._readback = "Testing the wetness of water."
    bss.esaf.user_last_names._readback = "Bose, Einstein"
    bss.esaf.user_badges._readback = "287341, 339203, 59208"
    bss.proposal.proposal_id._readback = "25873"
    bss.proposal.title._readback = "Making the world a more interesting place."
    bss.proposal.user_last_names._readback = "Franklin, Watson, Crick"
    bss.proposal.user_badges._readback = "287341, 203884, 59208"
    bss.proposal.mail_in_flag._readback = "1"
    bss.proposal.proprietary_flag._readback = "0"
    bss.esaf.aps_cycle._readback = "2023-2"
    bss.proposal.beamline_name._readback = "255ID-C"
    # bss = FakeBss(name="bss")
    sim_registry.register(bss)
    monkeypatch.setenv("EPICS_HOST_ARCH", "PDP11")
    monkeypatch.setenv("EPICS_CA_MAX_ARRAY_BYTES", "16")
    monkeypatch.setenv("PYEPICS_LIBCA", "/dev/null")
    # Set up a callback to motor streams generated by runengine
    cb = CallbackBase()
    cb.start = MagicMock()
    cb.descriptor = MagicMock()
    cb.event = MagicMock()
    cb.stop = MagicMock()
    RE = run_engine(use_bec=False, connect_databroker=False)
    plan = bp.count([det], num=1)
    RE(plan, cb)
    # Check that the callback has the correct metadata
    assert cb.start.called
    assert cb.start.call_count == 1
    start_doc = cb.start.call_args[0][0]
    # Check versions
    assert "versions" in start_doc.keys()
    versions = start_doc["versions"]
    assert "haven" in versions.keys()
    assert versions["haven"] == "23.7.1"
    assert "bluesky" in versions.keys()
    # Check metadata keys
    expected_keys = [
        "uid",
        "time",
        "EPICS_HOST_ARCH",
        "beamline_id",
        "facility_id",
        "xray_source",
        "epics_libca",
        "EPICS_CA_MAX_ARRAY_BYTES",
        "login_id",
        "pid",
        "scan_id",
        "proposal_id",
        "plan_type",
        "plan_name",
        "detectors",
        "hints",
        "parameters",
        "purpose",
        "bss_aps_cycle",
        "bss_beamline_name",
        "esaf_id",
        "esaf_title",
        "esaf_users",
        "esaf_user_badges",
        "mail_in_flag",
        "proposal_title",
        "proprietary_flag",
        "proposal_users",
        "proposal_user_badges",
        "sample_name",
    ]
    missing_keys = set(expected_keys) - set(start_doc.keys())
    assert not missing_keys
    # Check metadata values
    expected_data = {
        "EPICS_HOST_ARCH": "PDP11",
        "beamline_id": "SPC Beamline (sector unknown)",
        "facility_id": "Advanced Photon Source",
        "xray_source": "insertion device",
        "epics_libca": "/dev/null",
        "EPICS_CA_MAX_ARRAY_BYTES": "16",
        "scan_id": 1,
        "plan_type": "generator",
        "plan_name": "count",
        "parameters": "",
        "purpose": "",
        "esaf_id": "12345",
        "esaf_title": "Testing the wetness of water.",
        "esaf_users": "Bose, Einstein",
        "esaf_user_badges": "287341, 339203, 59208",
        "mail_in_flag": "1",
        "proposal_id": "25873",
        "proposal_title": "Making the world a more interesting place.",
        "proposal_users": "Franklin, Watson, Crick",
        "proposal_user_badges": "287341, 203884, 59208",
        "proprietary_flag": "0",
        "sample_name": "",
        "bss_aps_cycle": "2023-2",
        "bss_beamline_name": "255ID-C",
    }
    for key, val in expected_data.items():
        assert start_doc[key] == val, f"{key}: {start_doc[key]}"


# uid: 600852ca-3776-4e7a-ba29-f11786371e55
# time: 1667935604.6147602
# EPICS_HOST_ARCH: linux-x86_64
# beamline_id: APS 9-ID-C USAXS
# epics_libca: >-
#   /home/beams11/USAXS/micromamba/envs/bluesky_2022_3/lib/python3.10/site-packages/epics/clibs/linux64/libca.so
# EPICS_CA_MAX_ARRAY_BYTES: '1280000'
# login_id: usaxs@usaxscontrol.xray.aps.anl.gov
# pid: 1639175
# scan_id: 92
# proposal_id: ''
# versions:
#   apstools: 1.6.8
#   area_detector_handlers: 0.0.10
#   bluesky: 1.10.0
#   databroker: 1.2.5
#   epics_ca: 3.5.0
#   Epics: 3.5.0
#   h5py: 3.7.0
#   matplotlib: 3.6.1
#   numpy: 1.23.3
#   ophyd: 1.7.0
#   pymongo: 4.2.0
#   pyRestTable: 2020.0.6
#   spec2nexus: 2021.2.4
# plan_type: generator
# plan_name: WAXS
# detectors:
#   - waxs_det
# num_points: 1
# num_intervals: 0
# plan_args:
#   detectors:
#     - >-
#       MyPilatusDetector(prefix='usaxs_pilatus2:', name='waxs_det',
#       read_attrs=['hdf1'], configuration_attrs=['cam', 'cam.acquire_period',
#       'cam.acquire_time', 'cam.image_mode', 'cam.manufacturer', 'cam.model',
#       'cam.num_exposures', 'cam.num_images', 'cam.trigger_mode', 'hdf1'])
#   num: 1
# hints:
#   dimensions:
#     - - - time
#       - primary
# full_filename: /share1/USAXS_data/2022-11/usaxs.mac
# filename: usaxs.mac
# line_number: 38
# action: waxsExp
# parameters:
#   - '40'
#   - '120'
#   - '3.77'
#   - Frye_VAC_Perp
# iso8601: '2022-11-08 13:26:41.101412'
# purpose: tuner
# datetime: '2022-11-08 12:48:48.735664'
# sx: 40
# sy: 120
# thickness: 3.77
# title: Frye_VAC_Perp
# bss_aps_cycle: ''
# bss_beamline_name: ''
# esaf_id: ''
# esaf_title: ''
# mail_in_flag: 'OFF'
# principal_user: no users listed
# proposal_title: ''
# proprietary_flag: 'OFF'
# sample_thickness_mm: 3.77
# hdf5_path: /share1/USAXS_data/2022-11/11_08_Frye/11_08_Frye_waxs
# hdf5_file: Frye_VAC_Perp_0009.hdf
# sample_image_name: /share1/USAXS_data/2022-11/11_08_Frye/11_08_Frye_waxs/Frye_VAC_Perp_0009.jpg
# method: areaDetectorAcquire
# area_detector_name: waxs_det
