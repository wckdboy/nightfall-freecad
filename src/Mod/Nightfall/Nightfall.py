# SPDX-FileCopyrightText: 2026 The Nightfall Authors
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared sketch facts and native transactions for Nightfall's first workbench."""
import FreeCAD as App


def inspect_sketch(sketch):
    """Read cached native diagnostics without solving, editing or repairing a sketch."""
    if not sketch.isDerivedFrom("Sketcher::SketchObject"):
        raise TypeError("Select a sketch to inspect")
    constraints = {"numbering": "one_based"}
    for name in ("Conflicting", "Redundant", "PartiallyRedundant", "Malformed"):
        key = "partially_redundant" if name == "PartiallyRedundant" else name.lower()
        constraints[key] = list(getattr(sketch, name + "Constraints"))
    cached_dof = int(sketch.DoF)
    uninitialized = sketch.GeometryCount > 0 and cached_dof == 0 and not sketch.FullyConstrained
    pending = "Touched" in sketch.State or uninitialized
    dof = None if pending else cached_dof
    status = "underconstrained"
    if constraints["conflicting"]:
        status = "overconstrained" if cached_dof < 0 else "conflicting"
    elif constraints["malformed"]:
        status = "malformed"
    elif constraints["redundant"]:
        status = "redundant"
    elif constraints["partially_redundant"]:
        status = "partially_redundant"
    elif pending:
        status = "needs_recompute"
    elif "Invalid" in sketch.State or dof < 0:
        status = "solver_error"
    elif sketch.GeometryCount == 0:
        status = "empty"
    elif sketch.FullyConstrained and dof == 0:
        status = "fully_constrained"
    return {
        "kind": "nightfall.sketch-feedback.v1",
        "document": sketch.Document.Name,
        "object": sketch.Name,
        "label": sketch.Label,
        "status": status,
        "degrees_of_freedom": dof,
        "geometry_count": sketch.GeometryCount,
        "cached_degrees_of_freedom": None if uninitialized else cached_dof,
        "constraint_count": sketch.ConstraintCount,
        "constraints": constraints,
        "diagnostics_freshness": "unverified" if pending else "reported_up_to_date",
        "native_state": list(sketch.State),
        "freecad_version": list(App.Version()),
        "checked": [] if pending else ["cached_native_solver_diagnostics"],
        "unchecked": ["geometric_intent", "profile_closure", "manufacturing_readiness"],
    }


def new_sketch(document, plane="XY", body=None):
    """Create an origin-plane sketch as one undo step; preserve pending user work."""
    if plane not in ("XY", "XZ", "YZ"):
        raise ValueError("Choose XY, XZ or YZ")
    if body is not None and (
        body.Document != document or not body.isDerivedFrom("PartDesign::Body")
    ):
        raise ValueError("The body must belong to the current document")
    if document.HasPendingTransaction:
        raise ValueError("Finish the current edit before creating a sketch")
    if not document.UndoMode:
        raise ValueError("Enable document undo before creating a sketch")
    document.openTransaction("New " + plane + " sketch")
    try:
        if body is None:
            body = document.addObject("PartDesign::Body", "Body")
        support = [obj for obj in body.Origin.OriginFeatures if obj.Role == plane + "_Plane"]
        if len(support) != 1:
            raise ValueError("The body's origin plane is unavailable")
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.Label = "Sketch (" + plane + ")"
        sketch.AttachmentSupport = (support[0], [""])
        sketch.MapMode = "FlatFace"
        if not document.recompute():
            raise RuntimeError("The sketch could not be recomputed")
        document.commitTransaction()
        return sketch
    except Exception:
        document.abortTransaction()
        raise
