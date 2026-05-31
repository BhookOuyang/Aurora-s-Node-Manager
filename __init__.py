bl_info = {
    "name": "Aurora's Node Manager",
    "author": "BhookOuyang",
    "version": (1, 2, 1),
    "blender": (3, 0, 0),
    "location": "Node Editor > Sidebar > Dear.Aurora",
    "description": "Implement node JSON serialization for storage and sharing.",
    "category": "Node",
    "doc_url": "",
    "tracker_url": "",
}

import atexit
import bpy
from . import ui, io_module, core
from .utils.translations import translations_dict


def _cleanup_cache():
    """Clear undo cache on Blender shutdown."""
    try:
        from .utils.file_utils import clear_cache
        clear_cache()
    except Exception:
        pass


class NodeManagerAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    use_custom_path: bpy.props.BoolProperty(
        name="Use Custom Storage Path",
        description="Enable to use a custom directory for storing node patterns",
        default=False,
    )

    patterns_path: bpy.props.StringProperty(
        name="Patterns Storage Path",
        description="Custom directory for storing node patterns",
        subtype='DIR_PATH',
        default="",
    )

    auto_migrate: bpy.props.BoolProperty(
        name="Auto-migrate on path change",
        description="Automatically move pattern files to the new path when changed",
        default=True,
    )

    show_advanced: bpy.props.BoolProperty(
        name="Show Advanced Options",
        description="Show advanced serialization options",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_custom_path")

        row = layout.row()
        row.enabled = self.use_custom_path
        row.prop(self, "patterns_path")

        if self.use_custom_path:
            layout.prop(self, "auto_migrate")

        layout.prop(self, "show_advanced")

        box = layout.box()
        box.label(text="Author's Note:", icon='INFO')
        box.label(text="If you run into any issues, please let me know:", icon='URL')
        box.label(text="GitHub Issues (with Blender version & node info)")
        box.label(text="Bilibili: 欧阳魄鬼")
        box.label(text="Twitter / X: @BhookOuyang")


classes = [
    NodeManagerAddonPreferences,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    ui.register()
    io_module.register()
    core.register()
    bpy.app.translations.register(__name__, translations_dict)
    atexit.register(_cleanup_cache)


def unregister():
    bpy.app.translations.unregister(__name__)
    core.unregister()
    io_module.unregister()
    ui.unregister()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    try:
        atexit.unregister(_cleanup_cache)
    except Exception:
        pass


if __name__ == "__main__":
    register()