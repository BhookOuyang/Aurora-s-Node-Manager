# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""IO module for file and clipboard operations."""
import bpy
from . import operators

def register():
    operators.register()

def unregister():
    operators.unregister()
