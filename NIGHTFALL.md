# Nightfall

Nightfall is a FreeCAD fork focused on **speed, simplicity, stability, AI nativeness
and an enjoyable human modeling workflow**. The maintainer chose this foundation on
2026-10-21. UI/UX and flexible sketching are core product work again.

## Foundation

Start from FreeCAD **1.1.4**, source `4fd3bf320d9566a27e60069fc8387448aaa3a094`.
Preserve upstream history, licenses, credits, FCStd compatibility and workspaces.
Keep the patch set small and upgrade deliberately. The previous independent Nightfall
engine remains at [wckdboy/nightfall](https://github.com/wckdboy/nightfall) as reference
work; its Rust cutover, stress failures and physics roadmap are not claimed complete.

## First executable slice

The Nightfall workbench adds a native sketch companion:

- Create a sketch on a body's XY, XZ or YZ origin plane as one undo step.
- Keep underconstrained sketches usable while exploring; add precision as needed.
- Show native freedoms, conflicts and redundancy without silently repairing the sketch.
- Highlight what can still move and select flagged constraints for review.
- Start contextual dimensions with native previews; keep pending edits protected.
- Copy the same compact cached solver facts for AI, with stale/unchecked scope explicit.
- Use existing Part Design, Sketcher, Assembly and Draft commands and documents.

Load the Python workbench with an existing matching runtime:

```sh
FreeCAD -M /absolute/path/to/this/repository/src/Mod/Nightfall
```

Select **Nightfall** in the workbench selector. This loads fork Python source into the
official runtime; it is not a compiled and packaged Nightfall C++ application build.
The normal CMake build also copies/installs the Nightfall module.

While editing a sketch, **Show what can move** highlights its remaining freedoms.
**Dimension selection…** starts FreeCAD's contextual tool: select geometry, place the
dimension, use **M** to change its type, and use **Esc** to discard the current preview.
A second **Esc** exits the tool. **Review flagged constraints** selects native conflict
or redundancy witnesses for your review. Actions wait while another sketch edit is
pending; copied facts expose that state as `transaction_pending`.

Native tests use the same runtime, with `NIGHTFALL_TEST_OUTPUT` set to an output JSON
path, then `FreeCADCmd -P /absolute/path/to/src/Mod/Nightfall /absolute/path/to/src/Mod/Nightfall/RunTests.py`.

The native GUI fixture runs `FreeCAD -M /absolute/path/to/src/Mod/Nightfall
/absolute/path/to/src/Mod/Nightfall/RunGuiTests.FCMacro` with `NIGHTFALL_GUI_OUTPUT`
set to an existing output directory. Dimension cancellation uses Qt key press/release
events. The fixture invalidates its own viewport wrapper at native destruction;
pointer placement/value acceptance and OS keyboard delivery remain unchecked. Interactive
macOS accessibility crashes remain open in [#2](https://github.com/wckdboy/nightfall-freecad/issues/2).
The [guided sketch evidence](nightfall/evidence/guided-sketch-actions.json) binds the
tested source, native results, actual screenshots and remaining verification gaps.
The [lifetime evidence](nightfall/evidence/viewport-lifetime.json) records repeated
runtime trials and the fixture's later Qt keyboard checks against their exact source.

The [viewport lifetime reproduction](nightfall/tools/run_viewport_lifetime.py) runs
independently of Nightfall, using a native box in the matching official GUI runtime:

```sh
python3 nightfall/tools/run_viewport_lifetime.py --freecad /path/to/FreeCAD \
  --output-root /path/to/results --case wrap --close document
```

Compare `--case control`, `--quit-delay-ms 0`, and `--invalidate-on-destroy` with fresh
profiles. The runner bounds each owned process to 120 seconds, retains exact inputs,
and treats native crashes/timeouts as failures. Programmatic document closure with a
retained viewport wrapper reproduces intermittent [#5](https://github.com/wckdboy/nightfall-freecad/issues/5)
in the pinned macOS runtime. Explicit invalidation at native destruction avoids this
failure in the fixture; an application-level fix and underlying cause remain open.

## Capability milestones

1. **Foundation:** pinned source, native sketch/undo tests, visible plane-to-sketch flow,
   read-only factual feedback and retained runtime/source evidence.
2. **AI modeling:** bounded typed operations shared with human controls, revision checks,
   atomic transactions/rollback, recompute validation, compact verification receipts.
3. **Sketch experience:** clear plane/selection/navigation flow, contextual dimensions,
   previews of constraint suggestions and understandable conflicts; measure real tasks.
4. **Assemblies:** coherent occurrence hierarchy and transitions, with measured joint
   residuals, DOF/loop behavior and collision scope before stronger capability claims.
5. **Workspace integration:** Part Design, Assembly, Draft, PCB/KiCad and Rendering with
   compatible pinned add-ons and explicit availability. PCB/render integration is pending.

Simulation/CFD remain later engineering work with analytic/convergence/conservation
evidence. A workspace menu, a screenshot or passing tests cannot establish physical
accuracy or industrial parity. Inspection does not certify profile closure, design
intent or manufacturing readiness. The first helper exposes native cached diagnostics;
it does not create a new AI transport or connect a model provider.

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for the upstream process. Use small topic
branches/PRs in this personal fork, preserve Python/API compatibility, test against the
real native runtime and state precisely when a full C++ build was not performed.
