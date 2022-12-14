import time
import pytest
from unittest.mock import MagicMock
import asyncio

from bluesky import RunEngine, plans as bp
from qtpy.QtCore import QThread
from qtpy.QtTest import QSignalSpy
from bluesky_queueserver_api.zmq import REManagerAPI

from firefly.queue_client import QueueClient
from firefly.application import REManagerAPI
from firefly.main_window import FireflyMainWindow


def test_setup(qapp):
    api = MagicMock()
    FireflyMainWindow()
    qapp.prepare_queue_client(api=api)

def test_queue_re_control(qapp):
    """Test if the run engine can be controlled from the queue client."""
    FireflyMainWindow()
    api = MagicMock()
    qapp.prepare_queue_client(api=api)
    # Try and pause the run engine
    qapp.pause_run_engine.trigger()
    # Check if the API paused
    time.sleep(0.1)
    api.re_pause.assert_called_once_with(option="deferred")
    # Pause the run engine now!
    api.reset_mock()
    qapp.pause_run_engine_now.trigger()
    # Check if the API paused now
    time.sleep(0.1)
    api.re_pause.assert_called_once_with(option="immediate")
    # Start the queue
    api.reset_mock()
    qapp.start_queue.trigger()
    # Check if the queue started
    time.sleep(0.1)
    api.queue_start.assert_called_once()

def test_run_plan(qapp, qtbot):
    """Test if a plan can be queued in the queueserver."""
    FireflyMainWindow()
    api = MagicMock()
    api.item_add.return_value = {"success": True, "qsize": 2}
    qapp.prepare_queue_client(api=api)
    # Send a plan
    with qtbot.waitSignal(qapp.queue_length_changed, timeout=1000,
                          check_params_cb=lambda l: l == 2):
        qapp.queue_item_added.emit({})
    # Check if the API sent it
    api.item_add.assert_called_once_with(item={})
