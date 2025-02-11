import logging

from qtpy import QtWidgets, QtCore
from bluesky_queueserver_api import BPlan
from haven import registry, load_config, exceptions
from xraydb.xraydb import XrayDB
import qtawesome as qta

from firefly import display


log = logging.getLogger(__name__)


class EnergyDisplay(display.FireflyDisplay):
    caqtdm_mono_ui_file = "/net/s25data/xorApps/ui/DCMControlCenter.ui"
    caqtdm_id_ui_file = (
        "/net/s25data/xorApps/epics/synApps_6_2/ioc/25ida/25idaApp/op/ui/IDControl.ui"
    )
    min_energy = 4000
    max_energy = 33000
    stylesheet_danger = (
        "background: rgb(220, 53, 69); color: white; border-color: rgb(220, 53, 69)"
    )
    stylesheet_normal = ""

    def __init__(self, args=None, macros={}, **kwargs):
        # Load X-ray database for calculating edge energies
        self.xraydb = XrayDB()
        super().__init__(args=args, macros=macros, **kwargs)

    def prepare_caqtdm_actions(self):
        """Create QActions for opening mono/ID caQtDM panels.

        Creates two actions, one for the mono and one for the
        insertion device.

        """
        self.caqtdm_actions = []
        # Create an action for launching the mono caQtDM file
        action = QtWidgets.QAction(self)
        action.setObjectName("launch_mono_caqtdm_action")
        action.setText("Mono caQtDM")
        action.triggered.connect(self.launch_mono_caqtdm)
        action.setIcon(qta.icon("fa5s.wrench"))
        action.setToolTip("Launch the caQtDM panel for the monochromator.")
        try:
            registry.find(name="monochromator")
        except exceptions.ComponentNotFound:
            action.setDisabled(True)
        self.caqtdm_actions.append(action)
        # Create an action for launching the ID caQtDM file
        action = QtWidgets.QAction(self)
        action.setObjectName("launch_id_caqtdm_action")
        action.setText("ID caQtDM")
        action.triggered.connect(self.launch_id_caqtdm)
        action.setIcon(qta.icon("fa5s.wrench"))
        action.setToolTip("Launch the caQtDM panel for the insertion device.")
        self.caqtdm_actions.append(action)

    def launch_mono_caqtdm(self):
        config = load_config()
        prefix = config["monochromator"]["ioc"] + ":"
        mono = registry.find(name="monochromator")
        ID = registry.find(name="undulator")
        caqtdm_macros = {
            "P": prefix,
            "MONO": config["monochromator"]["ioc_branch"],
            "BRAGG": mono.bragg.prefix.replace(prefix, ""),
            "GAP": mono.gap.prefix.replace(prefix, ""),
            "ENERGY": mono.energy.prefix.replace(prefix, ""),
            "OFFSET": mono.offset.prefix.replace(prefix, ""),
            "IDENERGY": ID.energy.pvname,
        }
        self.launch_caqtdm(macros=caqtdm_macros, ui_file=self.caqtdm_mono_ui_file)

    def launch_id_caqtdm(self):
        """Launch the pre-built caQtDM UI file for the ID."""
        config = load_config()
        prefix = config["undulator"]["ioc"]
        # Strip leading "ID" from the mono IOC since caQtDM adds it
        prefix = prefix.strip("ID")
        caqtdm_macros = {
            # No idea what "M", and "D" do, they're not in the UI
            # file.
            "ID": prefix,
            "M": 2,
            "D": 2,
        }
        self.launch_caqtdm(macros=caqtdm_macros, ui_file=self.caqtdm_id_ui_file)

    def set_energy(self, *args, **kwargs):
        energy = float(self.ui.target_energy_lineedit.text())
        log.info(f"Setting new energy: {energy}")
        # Build the queue item
        item = BPlan("set_energy", energy=energy)
        # Submit the item to the queueserver
        from firefly.application import FireflyApplication

        app = FireflyApplication.instance()
        app.add_queue_item(item)

    def customize_ui(self):
        self.ui.set_energy_button.clicked.connect(self.set_energy)
        # Set up the combo box with X-ray energies
        combo_box = self.ui.edge_combo_box
        ltab = self.xraydb.tables["xray_levels"]
        edges = self.xraydb.query(ltab)
        edges = edges.filter(
            ltab.c.absorption_edge < self.max_energy,
            ltab.c.absorption_edge > self.min_energy,
        )
        items = [
            f"{r.element} {r.iupac_symbol} ({int(r.absorption_edge)} eV)"
            for r in edges.all()
        ]
        combo_box.addItems(["Select edge…", *items])
        combo_box.activated.connect(self.select_edge)

    @QtCore.Slot(int)
    def select_edge(self, index):
        if index == 0:
            # The placeholder text was selected
            return
        # Parse the combo box text to get the selected edge
        combo_box = self.ui.edge_combo_box
        text = combo_box.itemText(index)
        elem, edge = text.replace(" ", "_").split("_")[:2]
        # Determine which energy was selected
        edge_info = self.xraydb.xray_edge(element=elem, edge=edge)
        if edge_info is None:
            # Edge is not recognized, so provide feedback
            combo_box.setStyleSheet(self.stylesheet_danger)
        else:
            # Set the text field to the selected edge's energy
            energy, fyield, edge_jump = edge_info
            self.ui.target_energy_lineedit.setText(f"{energy:.3f}")
            combo_box.setStyleSheet(self.stylesheet_normal)

    def ui_filename(self):
        return "energy.ui"
