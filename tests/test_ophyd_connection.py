import time
import pytest
from ophyd import EpicsSignal, EpicsMotor, sim
from ophyd.sim import instantiate_fake_device, make_fake_device
from pydm.data_plugins import plugin_for_address, add_plugin
from pydm.main_window import PyDMMainWindow
from pydm.widgets import PyDMLineEdit
from pydm import PyDMChannel
from qtpy import QtCore
from unittest.mock import MagicMock

from haven import HavenMotor
from firefly.ophyd_plugin import Connection as OphydConnection, OphydPlugin
from firefly.main_window import FireflyMainWindow


class DummyObject(QtCore.QObject):
    signal = QtCore.Signal()


@pytest.fixture()
def sim_motor(sim_registry):
    FakeMotor = make_fake_device(HavenMotor)
    motor = FakeMotor("255idVME:m1", name="motor")
    motor.user_setpoint.sim_set_limits((0, 1000))
    sim_registry.register(motor)
    return motor


@pytest.fixture()
def ophyd_channel(sim_motor):
    channel = PyDMChannel(address="oph://motor.user_setpoint")
    return channel


@pytest.fixture()
def ophyd_connection(sim_motor, ophyd_channel, pydm_ophyd_plugin):
    channel = ophyd_channel
    pydm_ophyd_plugin.add_connection(channel)
    connection = pydm_ophyd_plugin.connections["motor.user_setpoint"]
    yield connection
    pydm_ophyd_plugin.remove_connection(channel)


def test_ophyd_pydm_ophyd_plugin(pydm_ophyd_plugin):
    plugin = plugin_for_address("oph://sim_detector")
    assert isinstance(plugin, OphydPlugin)


def test_new_value(sim_motor, ophyd_connection, qtbot):
    with qtbot.waitSignal(ophyd_connection.new_value_signal) as blocker:
        sim_motor.set(45.0)
    assert blocker.args[0] == 45.0


def test_set_value(sim_motor, ophyd_connection, ophyd_channel):
    ophyd_connection.set_value(87.0).wait()
    assert sim_motor.user_setpoint.get(use_monitor=False) == 87.0


def test_missing_device(sim_motor, pydm_ophyd_plugin, qtbot, ffapp):
    """See if the connection responds properly if the device is not there."""
    connection_slot = MagicMock()
    channel = PyDMChannel(
        address="oph://motor.nonsense_parts", connection_slot=connection_slot
    )
    pydm_ophyd_plugin.add_connection(channel)


def test_update_ctrl_vals(sim_motor, ophyd_connection, qtbot):
    conn = ophyd_connection
    conn._ctrl_vars = {}
    # Check if the connection state is updated
    with qtbot.waitSignal(conn.connection_state_signal) as blocker:
        conn.update_ctrl_vars(connected=True)
    assert blocker.args[0] is True
    # Make sure it isn't emitted a second time if it doesn't change
    conn._ctrl_vars = {"connected": True}
    conn.connection_state_signal = MagicMock()
    conn.update_ctrl_vars(connected=True)
    assert not conn.connection_state_signal.emit.called
    # Check other metadata signals
    conn._ctrl_vars = {}
    with qtbot.waitSignal(conn.new_severity_signal) as blocker:
        conn.update_ctrl_vars(severity=2)
    assert blocker.args[0] == 2

    conn._ctrl_vars = {}
    with qtbot.waitSignal(conn.write_access_signal) as blocker:
        conn.update_ctrl_vars(write_access=True)
    assert blocker.args[0] is True

    conn._ctrl_vars = {}
    with qtbot.waitSignal(conn.enum_strings_signal) as blocker:
        conn.update_ctrl_vars(enum_strs=("Option 1", "Option 2"))
    assert blocker.args[0] == ("Option 1", "Option 2")

    conn._ctrl_vars = {}
    with qtbot.waitSignal(conn.unit_signal) as blocker:
        conn.update_ctrl_vars(units="µm")
    assert blocker.args[0] == "µm"

    conn._ctrl_vars = {}
    with qtbot.waitSignal(conn.prec_signal) as blocker:
        conn.update_ctrl_vars(precision=5)
    assert blocker.args[0] == 5

    conn._ctrl_vars = {}
    with qtbot.waitSignal(conn.lower_ctrl_limit_signal) as blocker:
        conn.update_ctrl_vars(lower_ctrl_limit=-200)
    assert blocker.args[0] == -200

    conn._ctrl_vars = {}
    with qtbot.waitSignal(conn.upper_ctrl_limit_signal) as blocker:
        conn.update_ctrl_vars(upper_ctrl_limit=850.3)
    assert blocker.args[0] == 850.3

    conn._ctrl_vars = {}
    with qtbot.waitSignal(conn.timestamp_signal) as blocker:
        conn.update_ctrl_vars(timestamp=1693014035.3913143)
    assert blocker.args[0] == 1693014035.3913143
    {
        "connected": True,
        "read_access": True,
        "write_access": True,
        "timestamp": 1693014035.3913143,
        "status": None,
        "severity": None,
        "precision": None,
        "lower_ctrl_limit": None,
        "upper_ctrl_limit": None,
        "units": None,
        "enum_strs": None,
        "setpoint_status": None,
        "setpoint_severity": None,
        "setpoint_precision": None,
        "setpoint_timestamp": None,
        "sub_type": "meta",
    }


def test_widget_signals(sim_motor, ffapp, qtbot):
    """Does this work with a real widget in a real window."""
    sim_motor.user_setpoint.set(5.15)
    sim_motor.user_setpoint._metadata["precision"] = 3
    window = PyDMMainWindow()
    widget = PyDMLineEdit(parent=window, init_channel="oph://motor.user_setpoint")
    # widget.precisionChanged(3)
    ffapp.processEvents()
    time.sleep(0.05)
    assert widget.text() == "5.150"
    # Now check that we can set the widget text and have it update the ophyd device
    widget.send_value_signal[float].emit(4.9)
    ffapp.processEvents()
    time.sleep(0.05)
    assert sim_motor.user_setpoint.get(use_monitor=False) == 4.9
