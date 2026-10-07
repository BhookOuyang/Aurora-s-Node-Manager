# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""UI module for panels and lists."""
import bpy
from . import panels

def register():
    panels.register()

def unregister():
    panels.unregister()
