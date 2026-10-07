# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

bl_info = {
    "name": "Aurora's Node Manager",
    "author": "BhookOuyang",
    "version": (1, 3, 0),
    "blender": (3, 0, 0),
    "location": "Node Editor > Sidebar > Dear.Aurora",
    "description": "Implement node JSON serialization for storage and sharing.",
    "category": "Node",
    "doc_url": "",
    "tracker_url": "",
}

import atexit
import os
from pathlib import Path
import webbrowser

import bpy
from . import ui, io_module, core
from .utils import banner
from .utils import logger
from .utils.translations import tr, translations_dict


def _cleanup_cache():
    """Clear undo cache on Blender shutdown."""
    try:
        from .utils.file_utils import clear_cache
        clear_cache()
    except Exception:
        pass


def _on_egg_click(self, context):
    # This is an easter egg.
    if not banner.register_click():
        return
    bpy.app.timers.register(_show_banner, first_interval=0.1)


def _show_banner():
    html_path = os.path.join(bpy.app.tempdir, "easter_egg.html")
    try:
        banner.write_viewer(html_path)
        if webbrowser.open(Path(html_path).as_uri()):
            return None
    except Exception:
        pass
    print(banner.banner_text())
    return None


class NodeManagerAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    use_custom_path: bpy.props.BoolProperty(
        name="Use Custom Storage Path",
        description="Enable to use a custom directory for storing node patterns",
        default=False,
        update=_on_egg_click,
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

    store_absolute_paths: bpy.props.BoolProperty(
        name="Store Absolute File Paths",
        description="Save the absolute file paths of referenced files (images, clips, scripts, IES, etc.) so they can be reloaded locally. Paths are stripped when copying to clipboard or exporting .aurpak for sharing.",
        default=False,
    )

    safe_import: bpy.props.BoolProperty(
        name="Auto-delete Risky File Types",
        description="Automatically delete blacklisted/risky file types when importing resource packs; when disabled, these files are shown in a dialog for manual decision.",
        default=True,
    )

    log_directory: bpy.props.StringProperty(
        name="Log Storage Path",
        description="Directory where session log files are stored; leave empty to use the default user scripts folder.",
        subtype='DIR_PATH',
        default="",
    )

    use_sharding: bpy.props.BoolProperty(
        name="Enable Sharded Transfer",
        description="Split clipboard data into multiple shards of a fixed size, sent one at a time; the receiver reassembles and decodes them automatically once all are collected.",
        default=False,
    )

    shard_size_preset: bpy.props.EnumProperty(
        name="Shard Size",
        description="Maximum number of characters per shard.",
        items=[
            ('500', "500 chars", "Up to 500 chars per shard, for very restrictive channels."),
            ('1000', "1000 chars", "Up to 1000 chars per shard."),
            ('2000', "2000 chars", "Up to 2000 chars per shard (default)."),
            ('4000', "4000 chars", "Up to 4000 chars per shard, for long-message channels."),
            ('8000', "8000 chars", "Up to 8000 chars per shard."),
        ],
        default='2000',
    )

    use_encryption: bpy.props.BoolProperty(
        name="Enable Data Encryption",
        description="Encrypt clipboard data with a password; the receiver must enter the correct password to decode it.",
        default=False,
    )

    encryption_password: bpy.props.StringProperty(
        name="Encryption Password",
        description="Password used for encryption (the receiver must enter the same password to decode). Leave empty to be prompted before copying.",
        subtype='PASSWORD',
        default="",
    )

    only_modified: bpy.props.BoolProperty(
        name="Only Modified",
        description="Exclude defaults to reduce size. Defaults depend on current Blender version.",
        default=True,
    )

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="General", icon='PREFERENCES')
        box.prop(self, "use_custom_path")
        if banner.triggered:
            box.label(text="You found the easter egg!", icon='INFO')

        row = box.row()
        row.enabled = self.use_custom_path
        row.prop(self, "patterns_path")

        if self.use_custom_path:
            box.prop(self, "auto_migrate")

        box.prop(self, "store_absolute_paths")
        box.prop(self, "safe_import")

        box = layout.box()
        box.label(text="Logging", icon='CONSOLE')
        box.prop(self, "log_directory")
        row = box.row()
        row.operator("node.export_logs_v2", text="Export Logs", icon='EXPORT')
        row.operator("node.clear_logs_v2", text="Clear Logs", icon='TRASH')
        try:
            log_files = logger.list_logs()
            box.label(text=tr("{} log file(s) · {}").format(len(log_files), logger.log_dir_str()))
        except Exception:
            box.label(text=logger.log_dir_str())

        box = layout.box()
        box.label(text="Author's Note:", icon='INFO')
        row = box.row(align=True)
        row.alignment = 'LEFT'
        row.label(text="Have a bug? Tell me:", icon='URL')
        op = row.operator("wm.url_open", text="Report Issue", icon='URL')
        op.url = "https://github.com/BhookOuyang/Aurora-s-Node-Manager/issues"
        box.label(text="GitHub Issues (with Blender version & node info)")
        box.label(text="Contact Me", icon='USER')
        box.label(text="Bilibili: 欧阳魄鬼")
        box.label(text="Twitter / X: @BhookOuyang")


classes = [
    NodeManagerAddonPreferences,
]


def register():
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)
    ui.register()
    io_module.register()
    core.register()
    logger.register()
    bpy.app.translations.register(__name__, translations_dict)
    atexit.register(_cleanup_cache)


def unregister():
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass
    core.unregister()
    io_module.unregister()
    ui.unregister()
    logger.unregister()
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    try:
        atexit.unregister(_cleanup_cache)
    except Exception:
        pass


if __name__ == "__main__":
    register()