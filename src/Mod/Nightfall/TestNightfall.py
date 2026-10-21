# SPDX-FileCopyrightText: 2026 The Nightfall Authors
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native FreeCAD tests; run with FreeCADCmd, not a mocked solver."""
import json
import os
from pathlib import Path
import time
import unittest

import FreeCAD as App
import Part
import Sketcher
import Nightfall


class SketchFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("NightfallTest")
        self.doc.UndoMode = 1

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def circle(self):
        sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        sketch.addGeometry(Part.Circle(App.Vector(4, 6, 0), App.Vector(0, 0, 1), 3))
        self.doc.recompute()
        return sketch

    def test_freedom_dimensions_and_fully_constrained(self):
        sketch = self.circle()
        report = Nightfall.inspect_sketch(sketch)
        self.assertEqual((report["status"], report["degrees_of_freedom"]), ("underconstrained", 3))
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 3))
        self.doc.recompute()
        self.assertEqual(Nightfall.inspect_sketch(sketch)["degrees_of_freedom"], 2)
        sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 3, 4))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", 0, 3, 6))
        self.doc.recompute()
        report = Nightfall.inspect_sketch(sketch)
        self.assertEqual((report["status"], report["degrees_of_freedom"]), ("fully_constrained", 0))

    def test_inspection_does_not_edit_or_solve(self):
        sketch = self.circle()
        before = (
            sketch.Shape.exportBrepToString(),
            repr(sketch.Constraints),
            tuple(sketch.State),
            self.doc.UndoCount,
            self.doc.RedoCount,
        )
        start = time.perf_counter()
        for _ in range(200):
            json.dumps(Nightfall.inspect_sketch(sketch), allow_nan=False)
        self.report_average_ms = (time.perf_counter() - start) * 1000 / 200
        print("NIGHTFALL_REPORT_AVERAGE_MS", self.report_average_ms, flush=True)
        self.assertEqual(
            before,
            (
                sketch.Shape.exportBrepToString(),
                repr(sketch.Constraints),
                tuple(sketch.State),
                self.doc.UndoCount,
                self.doc.RedoCount,
            ),
        )

    def test_conflict_is_reported_without_auto_repair(self):
        sketch = self.circle()
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 3))
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 5))
        self.doc.recompute()
        before = repr(sketch.Constraints)
        report = Nightfall.inspect_sketch(sketch)
        self.assertIn(report["status"], ("conflicting", "overconstrained"))
        self.assertEqual(set(report["constraints"]["conflicting"]), {1, 2})
        self.assertEqual(report["constraints"]["numbering"], "one_based")
        if "Touched" in sketch.State:
            self.assertEqual(report["diagnostics_freshness"], "unverified")
            self.assertIsNone(report["degrees_of_freedom"])
        self.assertEqual(before, repr(sketch.Constraints))

    def test_redundancy_is_reported_without_auto_deletion(self):
        sketch = self.circle()
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 3))
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 3))
        self.doc.recompute()
        report = Nightfall.inspect_sketch(sketch)
        self.assertEqual(report["status"], "redundant")
        self.assertTrue(report["constraints"]["redundant"])
        self.assertEqual(sketch.ConstraintCount, 2)

    def test_stale_solver_state_is_explicit(self):
        sketch = self.circle()
        sketch.touch()
        report = Nightfall.inspect_sketch(sketch)
        self.assertEqual(report["status"], "needs_recompute")
        self.assertIsNone(report["degrees_of_freedom"])
        self.assertEqual(report["cached_degrees_of_freedom"], 3)
        self.assertFalse(report["checked"])
        self.assertEqual(report["diagnostics_freshness"], "unverified")
        self.assertIn("Touched", sketch.State)

    def test_origin_planes_and_single_undo(self):
        expected = {
            "XY": App.Vector(0, 0, 1),
            "XZ": App.Vector(0, -1, 0),
            "YZ": App.Vector(1, 0, 0),
        }
        for plane, normal in expected.items():
            with self.subTest(plane=plane):
                old_objects = {obj.Name for obj in self.doc.Objects}
                old_undo = self.doc.UndoCount
                sketch = Nightfall.new_sketch(self.doc, plane)
                self.assertEqual(sketch.AttachmentSupport[0][0].Role, plane + "_Plane")
                actual = sketch.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
                self.assertLessEqual((actual - normal).Length, 1e-12)
                self.assertEqual(self.doc.UndoCount, old_undo + 1)
                self.doc.undo()
                self.assertEqual({obj.Name for obj in self.doc.Objects}, old_objects)

    def test_invalid_plane_and_foreign_body_leave_document_unchanged(self):
        before = ({obj.Name for obj in self.doc.Objects}, self.doc.UndoCount)
        with self.assertRaises(ValueError):
            Nightfall.new_sketch(self.doc, "arbitrary")
        other = App.newDocument("Other")
        try:
            body = other.addObject("PartDesign::Body", "Body")
            with self.assertRaises(ValueError):
                Nightfall.new_sketch(self.doc, "XY", body)
        finally:
            App.closeDocument(other.Name)
        self.assertEqual(before, ({obj.Name for obj in self.doc.Objects}, self.doc.UndoCount))

    def test_existing_transformed_body_keeps_its_origin(self):
        body = self.doc.addObject("PartDesign::Body", "ExistingBody")
        body.Placement = App.Placement(
            App.Vector(10, 20, 30), App.Rotation(App.Vector(0, 0, 1), 90)
        )
        self.doc.recompute()
        sketch = Nightfall.new_sketch(self.doc, "XZ", body)
        expected = body.Placement.Rotation.multVec(App.Vector(0, -1, 0))
        actual = sketch.getGlobalPlacement()
        self.assertLessEqual(
            (actual.Rotation.multVec(App.Vector(0, 0, 1)) - expected).Length, 1e-12
        )
        self.assertLessEqual((actual.Base - body.Placement.Base).Length, 1e-12)
        self.assertEqual(sum(obj.TypeId == "PartDesign::Body" for obj in self.doc.Objects), 1)
        self.doc.undo()
        self.assertEqual(self.doc.getObject(body.Name), body)

    def test_native_save_reload_preserves_reported_geometry(self):
        sketch = self.circle()
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 3))
        self.doc.recompute()
        before = sketch.Shape.exportBrepToString()
        path = Path(os.environ["NIGHTFALL_TEST_OUTPUT"]).parent / "sketch-replay.FCStd"
        self.doc.saveAs(str(path))
        App.closeDocument(self.doc.Name)
        self.doc = App.openDocument(str(path))
        self.doc.recompute()
        self.assertEqual(self.doc.Sketch.Shape.exportBrepToString(), before)
        restored = Nightfall.inspect_sketch(self.doc.Sketch)
        self.assertEqual(restored["status"], "needs_recompute")
        self.assertIsNone(restored["degrees_of_freedom"])
        self.doc.Sketch.touch()
        self.doc.recompute()
        self.assertEqual(Nightfall.inspect_sketch(self.doc.Sketch)["degrees_of_freedom"], 2)

    def test_pending_user_transaction_is_preserved(self):
        self.doc.openTransaction("User work")
        self.doc.addObject("Part::Box", "UserBox")
        with self.assertRaises(ValueError):
            Nightfall.new_sketch(self.doc, "XY")
        self.assertTrue(self.doc.HasPendingTransaction)
        self.doc.abortTransaction()
        self.assertFalse(self.doc.Objects)

    def test_empty_and_wrong_type(self):
        sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.doc.recompute()
        self.assertEqual(Nightfall.inspect_sketch(sketch)["status"], "empty")
        with self.assertRaises(TypeError):
            Nightfall.inspect_sketch(self.doc.addObject("Part::Box", "Box"))


def run_tests():
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SketchFeedbackTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "kind": "nightfall-freecad-native-sketch-tests",
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "elapsed_seconds": time.perf_counter() - started,
        "version": list(App.Version()),
        "gui_up": App.GuiUp,
        "scope": "Real Sketcher/Part native runtime; no full C++ rebuild or full FreeCAD suite",
    }
    Path(os.environ["NIGHTFALL_TEST_OUTPUT"]).write_text(json.dumps(report, indent=2) + "\n")
    if not result.wasSuccessful():
        raise SystemExit(1)
