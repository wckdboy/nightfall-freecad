# SPDX-FileCopyrightText: 2026 The Nightfall Authors
# SPDX-License-Identifier: LGPL-2.1-or-later
"""A native sketch companion; no background solver or model-provider dependency."""
import json
import weakref

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

import Nightfall


class Observer:
    def __init__(self, panel):
        self.panel = weakref.ref(panel)

    def changed(self, *args):
        panel = self.panel()
        if panel is not None:
            panel.schedule_refresh()

    slotChangedObject = slotRecomputedDocument = slotDeletedDocument = changed
    slotCreatedDocument = addSelection = removeSelection = clearSelection = changed


class Panel(QtWidgets.QDockWidget):
    def __init__(self, parent):
        super().__init__("Nightfall", parent)
        self.setObjectName("NightfallSketchPanel")
        self.setMinimumWidth(285)
        self._pending = False
        self._disposed = False
        self._report = None
        content = QtWidgets.QWidget()
        self.setWidget(content)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title = QtWidgets.QLabel("Nightfall")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(title)
        intro = QtWidgets.QLabel("Explore freely. Add precision when you need it.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        workspaces = QtWidgets.QHBoxLayout()
        for label, name in (
            ("Model", "PartDesignWorkbench"),
            ("Assembly", "AssemblyWorkbench"),
            ("Draft", "DraftWorkbench"),
        ):
            button = QtWidgets.QPushButton(label)
            button.setEnabled(name in Gui.listWorkbenches())
            button.clicked.connect(lambda checked=False, key=name: Gui.activateWorkbench(key))
            workspaces.addWidget(button)
        layout.addLayout(workspaces)
        layout.addWidget(QtWidgets.QLabel("START A SKETCH"))
        self.plane = QtWidgets.QComboBox()
        for label, value in (("XY · Top", "XY"), ("XZ · Front", "XZ"), ("YZ · Side", "YZ")):
            self.plane.addItem(label, value)
        layout.addWidget(self.plane)
        self.create = QtWidgets.QPushButton("New sketch")
        self.create.setMinimumHeight(34)
        self.create.clicked.connect(self.create_sketch)
        layout.addWidget(self.create)
        layout.addSpacing(12)
        layout.addWidget(QtWidgets.QLabel("SKETCH FEEDBACK"))
        self.summary = QtWidgets.QLabel()
        self.summary.setTextFormat(QtCore.Qt.PlainText)
        self.summary.setStyleSheet("font-size: 17px; font-weight: 600;")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.detail = QtWidgets.QLabel()
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.action_buttons = {}
        for action, label, tooltip in (
            ("freedoms", "Show what can move", "Highlight geometry with remaining freedoms."),
            (
                "dimension",
                "Dimension selection…",
                "Select geometry, then place a dimension. M changes its type. "
                "Esc discards the preview; Esc again exits the tool.",
            ),
            (
                "review",
                "Review flagged constraints",
                "Select the reported constraints so you can review your intent.",
            ),
        ):
            button = QtWidgets.QPushButton(label)
            button.setToolTip(tooltip)
            button.clicked.connect(
                lambda checked=False, key=action: self.activate_sketch_action(key)
            )
            self.action_buttons[action] = button
            layout.addWidget(button)
        refresh = QtWidgets.QPushButton("Refresh facts")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        self.copy = QtWidgets.QPushButton("Copy facts for AI")
        self.copy.clicked.connect(self.copy_report)
        layout.addWidget(self.copy)
        layout.addStretch()
        self.observer = Observer(self)
        App.addDocumentObserver(self.observer)
        Gui.Selection.addObserver(self.observer)
        self.destroyed.connect(lambda: self.dispose())
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.dispose)
        self.refresh()

    def dispose(self):
        if not self._disposed:
            self._disposed = True
            App.removeDocumentObserver(self.observer)
            Gui.Selection.removeObserver(self.observer)

    def schedule_refresh(self):
        if not self._pending and not self._disposed:
            self._pending = True
            QtCore.QTimer.singleShot(80, self.refresh)

    def current_sketch(self):
        document = App.ActiveDocument
        if document is None or Gui.activeDocument() is None:
            return None
        edited = Gui.activeDocument().getInEdit()
        if edited and edited.Object.isDerivedFrom("Sketcher::SketchObject"):
            return edited.Object
        selected = Gui.Selection.getSelection()
        if len(selected) == 1 and selected[0].isDerivedFrom("Sketcher::SketchObject"):
            return selected[0]
        sketches = [obj for obj in document.Objects if obj.isDerivedFrom("Sketcher::SketchObject")]
        return sketches[0] if len(sketches) == 1 else None

    def refresh(self):
        self._pending = False
        if self._disposed:
            return
        editing = Gui.activeDocument() is not None and Gui.activeDocument().getInEdit() is not None
        self.create.setEnabled(not editing)
        self.plane.setEnabled(not editing)
        sketch = self.current_sketch()
        self._report = Nightfall.inspect_sketch(sketch) if sketch else None
        self.copy.setEnabled(self._report is not None)
        for action, enabled in self.available_sketch_actions().items():
            self.action_buttons[action].setEnabled(enabled)
        if self._report is None:
            self.summary.setText("Choose a plane to begin")
            self.detail.setText(
                "Create a sketch, or select an existing sketch to see its freedoms and constraints."
            )
            return
        status = self._report["status"]
        if status == "underconstrained":
            self.summary.setText(str(self._report["degrees_of_freedom"]) + " freedoms remain")
            self.detail.setText(
                "Keep exploring, or add dimensions and relations that express your intent."
            )
        elif status == "fully_constrained":
            self.summary.setText("Fully constrained")
            self.detail.setText(
                "Every geometric freedom is constrained. Finish the sketch when you're ready."
            )
        elif status == "empty":
            self.summary.setText("Ready to sketch")
            self.detail.setText("Draw a shape first. You can refine its dimensions as you go.")
        elif status == "needs_recompute":
            cached = self._report["cached_degrees_of_freedom"]
            self.summary.setText(
                "Solver facts unavailable" if cached is None else str(cached) + " freedoms reported"
            )
            self.detail.setText(
                "Keep sketching freely. Recompute to verify the final constraint state."
            )
        else:
            numbers = sorted(
                {
                    n
                    for key, values in self._report["constraints"].items()
                    if key != "numbering"
                    for n in values
                }
            )
            self.summary.setText(status.replace("_", " ").capitalize())
            detail = "Review constraints " + ", ".join(map(str, numbers)) + ". " if numbers else ""
            detail += "Nothing has been removed or fixed automatically."
            if self._report["diagnostics_freshness"] == "unverified":
                detail += " Recompute to confirm these cached solver facts."
            self.detail.setText(detail)
        if self._report["transaction_pending"]:
            self.detail.setText(
                "Finish or cancel the current sketch action before starting another."
            )

    def edited_sketch(self):
        document = Gui.activeDocument()
        edited = document.getInEdit() if document else None
        if edited and edited.Object.isDerivedFrom("Sketcher::SketchObject"):
            return edited.Object
        return None

    @staticmethod
    def review_command(report):
        for key, command in (
            ("conflicting", "Sketcher_SelectConflictingConstraints"),
            ("redundant", "Sketcher_SelectRedundantConstraints"),
            ("partially_redundant", "Sketcher_SelectPartiallyRedundantConstraints"),
        ):
            if report["constraints"][key]:
                return command
        return None

    def available_sketch_actions(self):
        sketch = self.edited_sketch()
        if sketch is None or sketch.Document.HasPendingTransaction:
            return dict.fromkeys(("freedoms", "dimension", "review"), False)
        report = Nightfall.inspect_sketch(sketch)
        problem = report["status"] == "solver_error" or any(
            values for key, values in report["constraints"].items() if key != "numbering"
        )
        dof = report["cached_degrees_of_freedom"]
        return {
            "freedoms": dof is not None and dof > 0 and not problem,
            "dimension": sketch.GeometryCount > 0
            and dof is not None
            and not problem
            and all(obj == sketch for obj in Gui.Selection.getSelection()),
            "review": self.review_command(report) is not None,
        }

    def run_sketch_action(self, action):
        """Dispatch a native interaction only in its current sketch editing context."""
        if action not in ("freedoms", "dimension", "review"):
            raise ValueError("Unknown sketch action")
        sketch = self.edited_sketch()
        if sketch is None:
            raise ValueError("Open a sketch to use its guided actions")
        if not self.available_sketch_actions()[action]:
            raise ValueError("Check the sketch feedback and select geometry in the active sketch")
        command = {
            "freedoms": "Sketcher_SelectElementsWithDoFs",
            "dimension": "Sketcher_Dimension",
            "review": self.review_command(Nightfall.inspect_sketch(sketch)),
        }[action]
        Gui.runCommand(command)
        self.schedule_refresh()

    def activate_sketch_action(self, action):
        try:
            self.run_sketch_action(action)
        except (ValueError, RuntimeError) as error:
            self.detail.setText(str(error))

    def copy_report(self):
        self.refresh()
        if self._report is not None:
            QtWidgets.QApplication.clipboard().setText(
                json.dumps(self._report, separators=(",", ":"))
            )

    def create_sketch(self):
        try:
            document = App.ActiveDocument
            if document is None:
                document = App.newDocument("Nightfall")
                document.UndoMode = 1
            body = Gui.activeDocument().activeView().getActiveObject("pdbody")
            sketch = Nightfall.new_sketch(document, self.plane.currentData(), body)
            Gui.activateWorkbench("SketcherWorkbench")
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(sketch)
            Gui.activeDocument().setEdit(sketch.Name)
            self.schedule_refresh()
        except Exception as error:
            QtWidgets.QMessageBox.warning(self, "New sketch", str(error))


def show_panel():
    window = Gui.getMainWindow()
    panel = window.findChild(QtWidgets.QDockWidget, "NightfallSketchPanel")
    if panel is None:
        panel = Panel(window)
        window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, panel)
        model = window.findChild(QtWidgets.QDockWidget, "Model")
        if model is not None:
            window.tabifyDockWidget(model, panel)
    panel.show()
    panel.raise_()
    panel.refresh()
    return panel


class ShowPanel:
    def GetResources(self):
        return {
            "MenuText": "Sketch companion",
            "ToolTip": "Planes, sketch freedoms and facts for AI",
            "Pixmap": ":/icons/SketcherWorkbench.svg",
        }

    def Activated(self):
        show_panel()
