# SPDX-FileCopyrightText: 2026 The Nightfall Authors
# SPDX-License-Identifier: LGPL-2.1-or-later
set(Nightfall_FILES Init.py InitGui.py Nightfall.py NightfallGui.py TestNightfall.py RunTests.py
    TestNightfallGui.py TestNightfallActions.py RunGuiTests.FCMacro)
fc_copy_to_mod_path("Nightfall" ${Nightfall_FILES})
install(FILES ${Nightfall_FILES} DESTINATION Mod/Nightfall)
