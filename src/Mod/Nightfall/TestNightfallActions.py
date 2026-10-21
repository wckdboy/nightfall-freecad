# SPDX-FileCopyrightText: 2026 The Nightfall Authors
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Behavior checks against real native sketch commands, not mocked dispatch."""
import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher
from PySide import QtCore, QtGui, QtWidgets
import shiboken6

import Nightfall


def selection():
    return [
        (item.Object.Document.Name, item.Object.Name, tuple(item.SubElementNames))
        for item in Gui.Selection.getSelectionEx()
    ]


def model(sketch):
    return (
        tuple(geometry.Content for geometry in sketch.Geometry),
        tuple(constraint.Content for constraint in sketch.Constraints),
        tuple(sketch.State),
        sketch.Document.UndoCount,
        sketch.Document.RedoCount,
        sketch.Document.HasPendingTransaction,
    )


def viewer():
    view = Gui.getMainWindow().findChild(QtWidgets.QGraphicsView)
    assert view is not None and view.isVisible()
    assert view.metaObject().className() == "Gui::View3DInventorViewer"
    if not view.property("nightfallTestLifetimeHook"):
        # Qt 6.8.3 needs this test's wrapper invalidated at native destruction (#5).
        view.setProperty("nightfallTestLifetimeHook", True)
        view.destroyed.connect(lambda: shiboken6.invalidate(view))
    return view


def cancel_native_dimension():
    view = viewer()
    for kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
        QtWidgets.QApplication.sendEvent(
            view, QtGui.QKeyEvent(kind, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier)
        )


def exercise_actions(panel, sketch, report):
    before = model(sketch)
    panel.action_buttons["freedoms"].click()
    selected = selection()
    assert len(selected) == 1 and selected[0][:2] == (sketch.Document.Name, sketch.Name)
    assert "Vertex1" in selected[0][2] and "Edge1" not in selected[0][2]
    assert model(sketch) == before
    report["checks"].append(
        "fixed-radius circle highlights its free centre without model/undo edits"
    )

    sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 3, 4))
    sketch.addConstraint(Sketcher.Constraint("DistanceY", 0, 3, 6))
    sketch.addGeometry(Part.LineSegment(App.Vector(20, 0, 0), App.Vector(24, 3, 0)))
    assert sketch.solve() == 0 and sketch.DoF == 4
    before = model(sketch)
    panel.run_sketch_action("freedoms")
    selected = selection()[0][2]
    assert "Vertex2" in selected and "Vertex3" in selected
    assert "Edge1" not in selected and "Vertex1" not in selected
    assert model(sketch) == before
    report["checks"].append(
        "mixed sketch highlights free line endpoints and excludes constrained circle"
    )

    sketch.addConstraint(Sketcher.Constraint("Block", 1))
    assert sketch.solve() == 0 and sketch.DoF == 0
    panel.refresh()
    assert not panel.action_buttons["freedoms"].isEnabled()
    before, selected = model(sketch), selection()
    try:
        panel.run_sketch_action("freedoms")
        raise AssertionError("fully constrained freedom action must reject")
    except ValueError:
        pass
    assert (model(sketch), selection()) == (before, selected)
    sketch.delConstraint(3)

    sketch.addConstraint(Sketcher.Constraint("Radius", 0, 5))
    assert sketch.solve() != 0
    panel.refresh()
    assert panel.action_buttons["review"].isEnabled()
    assert not panel.action_buttons["dimension"].isEnabled()
    before = model(sketch)
    panel.run_sketch_action("review")
    assert set(selection()[0][2]) == {"Constraint1", "Constraint4"}
    assert model(sketch) == before
    sketch.delConstraint(3)
    sketch.addConstraint(Sketcher.Constraint("Radius", 0, 3))
    assert sketch.solve() != 0
    before = model(sketch)
    panel.run_sketch_action("review")
    assert set(selection()[0][2]) == {"Constraint4"}
    assert model(sketch) == before
    sketch.delConstraint(3)
    assert sketch.solve() == 0
    report["checks"].append(
        "native conflict/redundancy witnesses selected without repair or undo changes"
    )

    other = sketch.Document.addObject("Sketcher::SketchObject", "OtherSketch")
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(other)
    panel.refresh()
    assert not panel.action_buttons["dimension"].isEnabled()
    before, selected = model(sketch), selection()
    try:
        panel.run_sketch_action("dimension")
        raise AssertionError("foreign sketch selection must reject")
    except ValueError:
        pass
    assert (model(sketch), selection()) == (before, selected)
    Gui.Selection.clearSelection()
    sketch.Document.removeObject(other.Name)

    Gui.Selection.addSelection(sketch.Document.Name, sketch.Name, "Edge2")
    viewer()
    before = model(sketch)
    constraint_count = sketch.ConstraintCount
    cancellation = []
    loop = QtCore.QEventLoop()

    def cancel_dimension():
        modal = QtWidgets.QApplication.activeModalWidget()
        if modal is not None:
            cancellation.append({"route": "modal", "title": modal.windowTitle()})
            modal.reject()
        else:
            transaction = App.getActiveTransaction()
            panel.refresh()
            pending_model, pending_selection = model(sketch), selection()
            guarded = all(not button.isEnabled() for button in panel.action_buttons.values())
            try:
                panel.run_sketch_action("dimension")
                guarded = False
            except ValueError:
                pass
            guarded = guarded and (model(sketch), selection()) == (
                pending_model,
                pending_selection,
            )
            cancellation.append(
                {
                    "route": "native_qt_events",
                    "transaction": transaction,
                    "preview_constraint_count": sketch.ConstraintCount,
                    "preview_type": sketch.Constraints[-1].Type,
                    "preview_value": sketch.Constraints[-1].Value,
                    "transaction_pending": Nightfall.inspect_sketch(sketch)["transaction_pending"],
                    "pending_edit_guard": guarded,
                }
            )
            cancel_native_dimension()
            cancellation[-1]["after_first_escape"] = {
                "transaction": App.getActiveTransaction(),
                "constraint_count": sketch.ConstraintCount,
                "transaction_pending": sketch.Document.HasPendingTransaction,
            }
            cancel_native_dimension()

    timer = QtCore.QTimer()
    timer.setSingleShot(True)

    def cancel_and_resume():
        try:
            cancel_dimension()
        except Exception as error:
            cancellation.append({"error": repr(error)})
        finally:
            loop.quit()

    timer.timeout.connect(cancel_and_resume)
    timer.start(100)
    try:
        panel.run_sketch_action("dimension")
        if timer.isActive():
            loop.exec()
    finally:
        timer.stop()
    report["dimension_cancel"] = cancellation
    report["dimension_transaction_after"] = App.getActiveTransaction()
    report["dimension_history"] = {"before": before[3:], "after": model(sketch)[3:]}
    assert cancellation
    assert Gui.activeDocument().getInEdit().Object == sketch
    transaction = App.getActiveTransaction()
    assert transaction is None
    assert model(sketch)[:2] == before[:2]
    preview = cancellation[0]
    assert preview["route"] == "native_qt_events"
    assert preview["transaction"] is not None
    assert preview["preview_constraint_count"] == constraint_count + 1
    expected = {"Distance": 5, "DistanceX": 4, "DistanceY": 3}
    assert abs(preview["preview_value"] - expected[preview["preview_type"]]) <= 1e-9
    assert preview["transaction_pending"]
    assert preview["pending_edit_guard"]
    first = preview["after_first_escape"]
    assert first["transaction"] is not None and first["transaction"][0] == "Dimension"
    assert first["constraint_count"] == constraint_count and not first["transaction_pending"]
    report["pointer_placement_preview_checked"] = False
    report["keyboard_input_bridge_checked"] = True
    report["viewport_wrapper_scope"] = (
        "The fixture invalidates its own Qt viewport wrapper on native destruction; "
        "this does not fix other clients or macOS accessibility (#2, #5)."
    )
    report["checks"].append(
        "native length-5 preview cancels with Escape; second Escape exits the tool"
    )

    sketch.delGeometry(1)
    sketch.delConstraint(2)
    sketch.delConstraint(1)
    assert sketch.solve() == 0 and sketch.DoF == 2
    panel.refresh()
