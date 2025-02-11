from typing import Sequence
import subprocess
from pathlib import Path

from qtpy.QtCore import Signal, Slot
from qtpy import QtWidgets
from pydm import Display


class FireflyDisplay(Display):
    caqtdm_ui_file: str = ""
    caqtdm_command: str = "/APSshare/bin/caQtDM -style plastique -noMsg -attach"
    caqtdm_actions: Sequence

    # Signals
    status_message_changed = Signal(str, int)

    def __init__(self, parent=None, args=None, macros=None, ui_filename=None, **kwargs):
        super().__init__(
            parent=parent, args=args, macros=macros, ui_filename=ui_filename, **kwargs
        )
        self.customize_device()
        self.customize_ui()
        self.prepare_caqtdm_actions()

    def prepare_caqtdm_actions(self):
        """Create QActions for opening caQtDM panels.

        By default, this method creates one action if
        *self.caqtdm_ui_file* is set. Individual displays should
        override this method to add their own QActions. Any actions
        added to the *self.caqtdm_actions* list will be added to the
        "Setup" menu if the display is the root display in a main
        window.

        """
        self.caqtdm_actions = []
        if self.caqtdm_ui_file != "":
            # Create an action for launching a single caQtDM file
            action = QtWidgets.QAction(self)
            action.setObjectName("launch_caqtdm_action")
            action.setText("ca&QtDM")
            action.triggered.connect(self.launch_caqtdm)
            action.setToolTip("Launch the caQtDM panel for {self.device.name}.")
            self.caqtdm_actions.append(action)

    def _open_caqtdm_subprocess(self, cmds, *args, **kwargs):
        """Launch a new subprocess and save it to self._caqtdm_process."""
        # Try to leave this as just a simple call to Popen.
        # It helps simplify testing
        print(cmds)
        self._caqtdm_process = subprocess.Popen(cmds, *args, **kwargs)

    @Slot()
    def launch_caqtdm(self, macros={}, ui_file: str = None):
        """Launch a caQtDM window showing the window's panel."""
        if ui_file is None:
            ui_file = self.caqtdm_ui_file
        cmds = self.caqtdm_command.split()
        # Add macros
        macro_str = ",".join(f"{key}={val}" for key, val in macros.items())
        if macro_str != "":
            cmds.extend(["-macro", macro_str])
        # Add the path to caQtDM .ui file
        cmds.append(ui_file)
        self._open_caqtdm_subprocess(cmds)

    def customize_device(self):
        pass

    def customize_ui(self):
        pass

    def show_message(self, message, timeout=0):
        """Display a message in the status bar."""
        self.status_message_changed.emit(str(message), timeout)

    def ui_filename(self):
        raise NotImplementedError

    def ui_filepath(self):
        path_base = Path(__file__).parent
        return path_base / self.ui_filename()
