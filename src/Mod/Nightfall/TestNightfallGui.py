# SPDX-FileCopyrightText: 2026 The Nightfall Authors
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native GUI integration fixture; this does not exercise macOS accessibility."""
import hashlib
import json
import math
import os
from pathlib import Path
import traceback

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher
from PySide import QtCore, QtWidgets

import Nightfall
import NightfallGui


def run_tests():
    out = Path(os.environ["NIGHTFALL_GUI_OUTPUT"])
    report = {
        "kind": "nightfall-gui-integration",
        "passed": False,
        "checks": [],
        "version": list(App.Version()),
        "gui_up": App.GuiUp,
        "scope": "Native Qt widget and FreeCAD API integration; not accessibility or a full C++ rebuild",
        "accessibility_stability": "failed in separate interactive sessions; issue #2",
    }
    document_name = None

    def finish():
        (out / "gui.json").write_text(json.dumps(report, indent=2) + "\n")
        if document_name in App.listDocuments():
            if Gui.activeDocument().getInEdit() is not None:
                Gui.activeDocument().resetEdit()
            App.closeDocument(document_name)
        QtCore.QTimer.singleShot(300, QtWidgets.QApplication.quit)

    def capture():
        try:
            Gui.activeDocument().activeView().saveImage(
                str(out / "sketch-viewport.png"), 1200, 800, "Current"
            )
            Gui.getMainWindow().grab().save(str(out / "nightfall-sketch.png"))
            assert (out / "nightfall-sketch.png").stat().st_size > 10000
            report["checks"].append("actual Qt main-window screenshot")
            report["capture_scope"] = (
                "Qt widgets; OpenGL scene exported separately in sketch-viewport.png"
            )
            report["passed"] = True
        except Exception:
            report["error"] = traceback.format_exc()
        finish()

    def exercise():
        nonlocal document_name
        try:
            assert App.GuiUp == 1
            Gui.activateWorkbench("NightfallWorkbench")
            panel = NightfallGui.show_panel()
            assert panel.isVisible()
            panel.create_sketch()
            sketch = Gui.activeDocument().getInEdit().Object
            document_name = sketch.Document.Name
            assert sketch.AttachmentSupport[0][0].Role == "XY_Plane"
            panel.refresh()
            assert not panel.create.isEnabled() and not panel.plane.isEnabled()
            report["checks"].append("plane action enters native Sketcher; nested creation disabled")
            sketch.addGeometry(Part.Circle(App.Vector(4, 6, 0), App.Vector(0, 0, 1), 3))
            assert sketch.solve() == 0
            panel.refresh()
            assert panel._report["cached_degrees_of_freedom"] == 3
            assert "3 freedoms" in panel.summary.text()
            sketch.addConstraint(Sketcher.Constraint("Radius", 0, 3))
            assert sketch.solve() == 0
            panel.refresh()
            assert panel._report["cached_degrees_of_freedom"] == 2
            assert "2 freedoms" in panel.summary.text()
            report["checks"].append(
                "feedback follows 3 to 2 native freedoms while remaining flexible"
            )
            Gui.activeDocument().resetEdit()
            sketch.Document.recompute()
            panel.refresh()
            assert panel._report == Nightfall.inspect_sketch(sketch)
            assert panel._report["degrees_of_freedom"] == 2 and panel.create.isEnabled()
            assert abs(sketch.Shape.Length - 2 * math.pi * 3) <= 1e-9
            report["checks"].append("unfinished constraints accepted; human and AI facts agree")
            report["sketch"] = panel._report
            report["brep_sha256"] = hashlib.sha256(
                sketch.Shape.exportBrepToString().encode()
            ).hexdigest()
            sketch.Document.saveAs(str(out / "sketch-study.FCStd"))
            Gui.activeDocument().activeView().viewTop()
            Gui.activeDocument().activeView().fitAll()
            Gui.getMainWindow().resize(1440, 960)
            QtCore.QTimer.singleShot(800, capture)
        except Exception:
            report["error"] = traceback.format_exc()
            finish()

    QtCore.QTimer.singleShot(800, exercise)
