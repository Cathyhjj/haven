from unittest import mock

import pytest
from ophyd import StatusBase
from ophyd.sim import instantiate_fake_device

from haven import registry, exceptions
from haven.instrument import stage


@pytest.fixture()
def sim_aerotech_flyer():
    flyer = instantiate_fake_device(
        stage.AerotechFlyer, name="flyer", axis="@0", encoder=6
    )
    flyer.send_command = mock.MagicMock()
    return flyer


def test_stage_init():
    stage_ = stage.XYStage(
        "motor_ioc", pv_vert=":m1", pv_horiz=":m2", labels={"stages"}, name="aerotech"
    )
    assert stage_.name == "aerotech"
    assert stage_.vert.name == "aerotech_vert"
    # Check registry of the stage and the individiual motors
    registry.clear()
    with pytest.raises(exceptions.ComponentNotFound):
        registry.findall(label="motors")
    with pytest.raises(exceptions.ComponentNotFound):
        registry.findall(label="stages")
    registry.register(stage_)
    assert len(list(registry.findall(label="motors"))) == 2
    assert len(list(registry.findall(label="stages"))) == 1


def test_load_aerotech_stage():
    stage.load_stages()
    # Make sure these are findable
    stage_ = registry.find(name="Aerotech")
    assert stage_ is not None
    vert_ = registry.find(name="Aerotech_vert")
    assert vert_ is not None


def test_aerotech_flyer():
    aeroflyer = stage.AerotechFlyer(name="aerotech_flyer", axis="@0", encoder=6)
    assert aeroflyer is not None


def test_aerotech_stage():
    fly_stage = stage.AerotechFlyStage(
        "motor_ioc", pv_vert=":m1", pv_horiz=":m2", labels={"stages"}, name="aerotech"
    )
    assert fly_stage is not None
    assert fly_stage.asyn.ascii_output.pvname == "motor_ioc:asynEns.AOUT"


def test_aerotech_fly_params(sim_aerotech_flyer):
    flyer = sim_aerotech_flyer
    # Set some example positions
    flyer.motor_egu.set("micron").wait()
    flyer.acceleration.set(.5).wait() # µm/sec^2
    flyer.encoder_resolution.set(0.001).wait()  # µm
    flyer.start_position.set(20).wait()  # µm
    flyer.end_position.set(10).wait()  # µm
    flyer.step_size.set(0.1).wait()  # µm
    flyer.dwell_time.set(1).wait()  # sec
    
    # Check that the fly-scan parameters were calculated correctly
    assert flyer.slew_speed.get(use_monitor=False) == 0.1  # µm/sec
    assert flyer.taxi_start.get(use_monitor=False) == 20.03  # µm
    assert flyer.taxi_end.get(use_monitor=False) == 9.97  # µm
    assert flyer.encoder_step_size.get(use_monitor=False) == 100
    assert flyer.encoder_window_start.get(use_monitor=False) == 5
    assert flyer.encoder_window_end.get(use_monitor=False) == -1005
    assert flyer.pso_positions == ...


def test_enable_pso(sim_aerotech_flyer):
    flyer = sim_aerotech_flyer
    # Set up scan parameters
    flyer.encoder_step_size.set(50).wait()  # In encoder counts
    flyer.encoder_window_start.set(-5).wait()  # In encoder counts
    flyer.encoder_window_end.set(10000).wait()  # In encoder counts
    # Check that commands are sent to set up the controller for flying
    flyer.enable_pso()
    assert flyer.send_command.called
    commands = [c.args[0] for c in flyer.send_command.call_args_list]
    assert commands == [
        "PSOCONTROL @0 RESET",
        "PSOOUTPUT @0 CONTROL 1",
        "PSOPULSE @0 TIME 20,10",
        "PSOOUTPUT @0 PULSE WINDOW MASK",
        "PSOTRACK @0 INPUT 6",
        "PSODISTANCE @0 FIXED 50",
        "PSOWINDOW @0 1 INPUT 6",
        "PSOWINDOW @0 1 RANGE -5,10000",
    ]


def test_arm_pso(sim_aerotech_flyer):
    flyer = sim_aerotech_flyer
    assert not flyer.send_command.called
    flyer.arm_pso()
    assert flyer.send_command.called
    command = flyer.send_command.call_args.args[0]
    assert command == "PSOCONTROL @0 ARM"


def test_motor_units(sim_aerotech_flyer):
    """Check that the motor and flyer handle enginering units properly."""
    flyer = sim_aerotech_flyer
    flyer.motor_egu.set("micron").wait()
    unit = flyer.motor_egu_pint
    assert unit == stage.ureg("1e-6 m")


def test_kickoff(sim_aerotech_flyer):
    # Set up fake flyer with mocked fly method
    flyer = sim_aerotech_flyer
    flyer.fly = mock.MagicMock()
    # Start flying
    status = flyer.kickoff()
    # Check status behavior matches flyer interface
    assert isinstance(status, StatusBase)
    assert not status.done
    # Start flying and see if the status is done
    flyer.is_flying.set(True).wait()
    assert status.done


def test_complete(sim_aerotech_flyer):
    # Set up fake flyer with mocked fly method
    flyer = sim_aerotech_flyer
    flyer.is_flying.set(False).wait()
    # Complete flying
    status = flyer.complete()
    # Check status behavior matches flyer interface
    assert isinstance(status, StatusBase)
    assert not status.done
    # Start flying and see if the status is done
    flyer.is_flying.set(True).wait()
    assert status.done


def test_fly_motor_positions(sim_aerotech_flyer):
    flyer = sim_aerotech_flyer
    # Arbitrary rest position
    flyer.user_setpoint.set(255)
    # Set example fly scan parameters
    flyer.taxi_start.set(5)
    flyer.start_position.set(10)
    flyer.taxi_end.set(105)
    # Mock the motor position so that it returns a status we control
    motor_status = StatusBase()
    motor_status.set_finished()
    setter = mock.MagicMock(return_value=motor_status)
    flyer.user_setpoint.set = setter
    # Check the fly scan moved the motors in the right order
    flyer.fly()
    assert setter.called
    positions = [c.args[0] for c in setter.call_args_list]
    assert len(positions) == 3
    start, taxi, end = positions
    assert start == 10
    assert taxi == 5
    assert end == 105
