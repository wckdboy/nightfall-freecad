# SPDX-FileCopyrightText: 2026 The Nightfall Authors
# SPDX-License-Identifier: LGPL-2.1-or-later
import FreeCADGui as Gui


class NightfallWorkbench(Workbench):
    MenuText = "Nightfall"
    ToolTip = "Sketch freely, make it precise, and inspect the facts"

    def Initialize(self):
        import NightfallGui

        Gui.addCommand("Nightfall_Show", NightfallGui.ShowPanel())
        self.appendToolbar("Nightfall", ["Nightfall_Show"])
        self.appendMenu("Nightfall", ["Nightfall_Show"])

    def Activated(self):
        import NightfallGui

        NightfallGui.show_panel()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(NightfallWorkbench())
