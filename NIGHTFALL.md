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
- Copy the same compact cached solver facts for AI, with stale/unchecked scope explicit.
- Use existing Part Design, Sketcher, Assembly and Draft commands and documents.

Load the Python workbench with an existing matching runtime:

```sh
FreeCAD -M /absolute/path/to/this/repository/src/Mod/Nightfall
```

Select **Nightfall** in the workbench selector. This loads fork Python source into the
official runtime; it is not a compiled and packaged Nightfall C++ application build.
The normal CMake build also copies/installs the Nightfall module.

Native tests use the same runtime, with `NIGHTFALL_TEST_OUTPUT` set to an output JSON
path, then `FreeCADCmd -P /absolute/path/to/src/Mod/Nightfall /absolute/path/to/src/Mod/Nightfall/RunTests.py`.

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
