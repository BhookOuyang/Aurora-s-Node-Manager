"""IO module for file and clipboard operations."""
import bpy
from . import operators

def register():
    operators.register()

def unregister():
    operators.unregister()
