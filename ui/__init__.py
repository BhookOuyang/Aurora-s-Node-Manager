"""UI module for panels and lists."""
import bpy
from . import panels

def register():
    panels.register()

def unregister():
    panels.unregister()
