import logging
import subprocess
from typing import Sequence
import json
from contextlib import contextmanager
from functools import partial

from qtpy.QtCore import Qt
import qtawesome as qta
import pyqtgraph
import pydm
from pydm.widgets import PyDMEmbeddedDisplay
import numpy as np
import matplotlib.pyplot as plt

import haven
from firefly import display, FireflyApplication

import sys

np.set_printoptions(threshold=sys.maxsize)


log = logging.getLogger(__name__)


pyqtgraph.setConfigOption("imageAxisOrder", "row-major")


class XRFDetectorDisplay(display.FireflyDisplay):
    roi_displays: Sequence = []

    def ui_filename(self):
        return "xrf_detector.ui"

    def customize_ui(self):
        device_name = self.macros()["DEV"]
        self.device = device = haven.registry.find(device_name)
        # Set ROI and element selection comboboxes
        self.ui.mca_combobox.currentIndexChanged.connect(self.draw_roi_widgets)
        self.ui.roi_combobox.currentIndexChanged.connect(self.draw_mca_widgets)
        elements = [str(i) for i in range(1, device.num_elements+1)]
        self.ui.mca_combobox.addItems(elements)
        rois = [str(i) for i in range(device.num_rois)]
        self.ui.roi_combobox.addItems(rois)
        # Controls for increment/decrement ROI/MCA combobox
        self.ui.mca_up_button.setIcon(qta.icon("fa5s.arrow-right"))
        self.ui.mca_down_button.setIcon(qta.icon("fa5s.arrow-left"))
        self.ui.roi_up_button.setIcon(qta.icon("fa5s.arrow-right"))
        self.ui.roi_down_button.setIcon(qta.icon("fa5s.arrow-left"))
        self.ui.mca_up_button.clicked.connect(
            partial(self.increment_combobox, combobox=self.ui.mca_combobox, step=1)
        )
        self.ui.mca_down_button.clicked.connect(
            partial(self.increment_combobox, combobox=self.ui.mca_combobox, step=-1)
        )
        self.ui.roi_up_button.clicked.connect(
            partial(self.increment_combobox, combobox=self.ui.roi_combobox, step=1)
        )
        self.ui.roi_down_button.clicked.connect(
            partial(self.increment_combobox, combobox=self.ui.roi_combobox, step=-1)
        )
        # Button for starting/stopping the detector
        self.ui.acquire_button.setIcon(qta.icon("fa5s.play"))

    def increment_combobox(self, combobox, step):
        n_items = combobox.count()
        new_index = (combobox.currentIndex() + step) % n_items
        combobox.setCurrentIndex(new_index)

    @contextmanager
    def disable_ui(self):
        widget = self
        # Disable to widgets
        widget.setEnabled(False)
        # Set waiting cursor
        old_cursor = self.cursor()
        self.setCursor(Qt.WaitCursor)
        # Update the UI
        FireflyApplication.instance().processEvents()
        yield
        # Re-enabled everything
        widget.setEnabled(True)
        widget.setCursor(old_cursor)

    def draw_roi_widgets(self, element_idx):
        with self.disable_ui():
            # Prepare all the ROI widgets
            layout = self.ui.rois_layout
            self.remove_widgets_from_layout(layout)
            self.roi_displays = []
            for roi_idx in range(self.device.num_rois):
                disp = PyDMEmbeddedDisplay(parent=self)
                disp.macros = json.dumps(
                    {
                        "DEV": self.device.name,
                        "MCA": element_idx+1,
                        "ROI": roi_idx,
                        "NUM": roi_idx,
                    }
                )
                disp.filename = "xrf_roi.py"
                # Add the Embedded Display to the ROI Layout
                layout.addWidget(disp)
                self.roi_displays.append(disp)

    def draw_mca_widgets(self, roi_idx):
        with self.disable_ui():
            # Prepare all the ROI widgets
            layout = self.ui.mcas_layout
            self.remove_widgets_from_layout(layout)
            self.mca_displays = []
            for mca_idx in range(1, self.device.num_elements+1):
                disp = PyDMEmbeddedDisplay(parent=self)
                disp.macros = json.dumps(
                    {
                        "DEV": self.device.name,
                        "MCA": mca_idx,
                        "ROI": roi_idx,
                        "NUM": mca_idx,
                    }
                )
                disp.filename = "xrf_roi.py"
                # Add the Embedded Display to the ROI Layout
                layout.addWidget(disp)
                self.mca_displays.append(disp)
                

    # def update_roi_widget_mca(self, mca_idx):
    #     try:
    #         disp = self.roi_displays[0]
    #     except Exception:
    #         print("Failed")
    #     else:
    #         from pprint import pprint
    #         pprint(dir(disp))
    #         pprint(dir(disp.embedded_widget))
    #     for disp in self.roi_displays:
    #         disp.embedded_widget._macros['MCA'] = mca_idx + 1
    #         # disp.macros['MCA'] = mca_idx + 1
        
    def remove_widgets_from_layout(self, layout):
        # Delete existing camera widgets
        for idx in reversed(range(layout.count())):
            layout.takeAt(idx).widget().deleteLater()

    def draw_widgets(self, layout):
        # Add embedded displays for all the cameras
        try:
            cameras = haven.registry.findall(label="cameras")
        except haven.exceptions.ComponentNotFound:
            log.warning(
                "No cameras found, [Detectors] -> [Cameras] panel will be empty."
            )
            cameras = []
