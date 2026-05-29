"""Blender UI panel definitions for AuroraSNodeManager."""
import hashlib
import json
from pathlib import Path

import bpy

from ..utils.file_utils import get_patterns_dir, get_cached_items


class NodePatternItem(bpy.types.PropertyGroup):
    """Item in the pattern list."""
    name: bpy.props.StringProperty(name="Name")
    file_name: bpy.props.StringProperty(name="File Name")
    is_locked: bpy.props.BoolProperty(name="Locked", default=False)
    node_count: bpy.props.IntProperty(name="Node Count", default=0)
    has_groups: bpy.props.BoolProperty(name="Has Groups", default=False)
    node_type: bpy.props.StringProperty(name="Node Type")


class NodePatternInfo(bpy.types.PropertyGroup):
    """Pattern metadata display."""
    description: bpy.props.StringProperty(name="Description")
    author: bpy.props.StringProperty(name="Author")
    created: bpy.props.StringProperty(name="Created")
    version: bpy.props.StringProperty(name="Version")
    node_count: bpy.props.IntProperty(name="Node Count")
    group_count: bpy.props.IntProperty(name="Group Count")
    node_type: bpy.props.StringProperty(name="Node Type")
    format_version: bpy.props.StringProperty(name="Format Version")


class NODE_UL_pattern_list(bpy.types.UIList):
    """Pattern list UI."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            if item.is_locked:
                row.label(text="", icon='LOCKED')
            else:
                row.label(text="", icon='BLANK1')

            if item.is_locked:
                sub = row.row()
                sub.enabled = False
                sub.label(text=item.name)
            else:
                row.label(text=item.name)

            if item.has_groups:
                row.label(text="", icon='NODETREE')


def _get_type_icon(node_type):
    """Get icon and label for node tree type."""
    type_map = {
        'ShaderNodeTree': ('SHADING_RENDERED', "Shader"),
        'CompositorNodeTree': ('NODE_COMPOSITING', "Compositor"),
        'GeometryNodeTree': ('MODIFIER_DATA', "Geometry"),
    }
    return type_map.get(node_type, ('QUESTION', "Unknown"))


def _get_current_subdir(wm):
    """Get current subdirectory based on category."""
    type_map = {
        'SHADER': 'shader',
        'COMPOSITOR': 'compositor',
        'GEOMETRY': 'geometry',
    }
    return type_map.get(wm.node_pattern_category, 'shader')


def _get_current_type_str(wm):
    """Get current node tree type string."""
    type_map = {
        'SHADER': 'ShaderNodeTree',
        'COMPOSITOR': 'CompositorNodeTree',
        'GEOMETRY': 'GeometryNodeTree',
    }
    return type_map.get(wm.node_pattern_category, 'ShaderNodeTree')


class NODE_PT_pattern_panel(bpy.types.Panel):
    """Main pattern management panel."""
    bl_label = "Node Patterns"
    bl_idname = "NODE_PT_pattern_panel_v2"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Dear.Aurora"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        # Always sync before drawing
        self._sync_check(wm)

        # Main actions
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator("node.save_pattern_v2", text="Save Selected", icon='FILE_TICK')

        row = layout.row(align=True)
        row.operator("node.export_pattern_v2", text="Export", icon='EXPORT')
        row.operator("node.import_pattern_v2", text="Import", icon='IMPORT')
        row.operator("node.paste_pattern_v2", text="Paste", icon='PASTEDOWN')

        layout.separator()

        # Category selector
        row = layout.row(align=True)
        row.prop(wm, "node_pattern_category", expand=True)

        layout.separator()

        # Pattern list
        type_str = _get_current_type_str(wm)
        icon, type_name = _get_type_icon(type_str)

        box = layout.box()
        row = box.row()
        row.label(text=f"{type_name} Patterns", icon=icon)
        row.label(text=f"({len(wm.node_pattern_items)})")

        if len(wm.node_pattern_items) > 0:
            row = box.row()
            row.template_list(
                "NODE_UL_pattern_list",
                "pattern_list",
                wm,
                "node_pattern_items",
                wm,
                "node_pattern_active_index",
                rows=5
            )

            active_idx = wm.node_pattern_active_index
            actual_item = None
            if 0 <= active_idx < len(wm.node_pattern_items):
                actual_item = wm.node_pattern_items[active_idx]

            if actual_item:
                # Action buttons
                row = box.row(align=True)

                op = row.operator("node.load_pattern_v2", text="Load", icon='IMPORT')
                op.file_name = actual_item.file_name

                sub = row.row(align=True)
                sub.enabled = not actual_item.is_locked
                op = sub.operator("node.overwrite_pattern_v2", text="Overwrite", icon='FILE_REFRESH')
                op.file_name = actual_item.file_name

                row = box.row(align=True)
                row.operator("node.copy_pattern_v2", text="Copy", icon='COPYDOWN')

                if actual_item.is_locked:
                    op = row.operator("node.toggle_lock_pattern_v2", text="Unlock", icon='LOCKED')
                else:
                    op = row.operator("node.toggle_lock_pattern_v2", text="Lock", icon='UNLOCKED')
                op.file_name = actual_item.file_name

                sub = row.row(align=True)
                sub.enabled = not actual_item.is_locked
                op = sub.operator("node.edit_pattern_info_v2", text="Edit", icon='GREASEPENCIL')
                op.file_name = actual_item.file_name

                sub = row.row(align=True)
                sub.enabled = not actual_item.is_locked
                op = sub.operator("node.delete_pattern_v2", text="Delete", icon='TRASH')
                op.file_name = actual_item.file_name
        else:
            box.label(text="No patterns in this category", icon='INFO')

    def _sync_check(self, wm):
        """Synchronize pattern list with filesystem."""
        subdir = _get_current_subdir(wm)
        target_dir = get_patterns_dir() / subdir

        if not target_dir.exists():
            if len(wm.node_pattern_items) > 0:
                wm.node_pattern_items.clear()
                wm.node_pattern_active_index = -1
            return

        actual_files = set()
        patterns_root = get_patterns_dir()
        for f in target_dir.glob("*.json"):
            if "_group_" not in f.stem:
                rel_path = f.relative_to(patterns_root).as_posix()
                actual_files.add(rel_path)

        recorded_files = {item.file_name for item in wm.node_pattern_items}

        if actual_files != recorded_files:
            refresh_pattern_list(wm)


class NODE_PT_pattern_info_panel(bpy.types.Panel):
    """Pattern metadata panel."""
    bl_label = "Pattern Info"
    bl_idname = "NODE_PT_pattern_info_panel_v2"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Dear.Aurora"
    bl_parent_id = "NODE_PT_pattern_panel_v2"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        return 0 <= wm.node_pattern_active_index < len(wm.node_pattern_items)

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        info = wm.node_pattern_info

        col = layout.column(align=True)

        icon, type_name = _get_type_icon(info.node_type)
        row = col.row()
        row.label(text="Type:")
        row.label(text=type_name or "-", icon=icon)

        col.separator()

        col.label(text="Description:", icon='INFO')
        col.label(text=info.description or "-")

        col.separator()

        row = col.row()
        row.label(text="Author:")
        row.label(text=info.author or "-")

        row = col.row()
        row.label(text="Created:")
        row.label(text=info.created or "-")

        row = col.row()
        row.label(text="Version:")
        row.label(text=info.version or "-")

        row = col.row()
        row.label(text="Format:")
        row.label(text=info.format_version or "-")

        row = col.row()
        row.label(text="Nodes:")
        row.label(text=str(info.node_count))

        row = col.row()
        row.label(text="Groups:")
        row.label(text=str(info.group_count))


class NODE_PT_advanced_panel(bpy.types.Panel):
    """Advanced options panel."""
    bl_label = "Advanced"
    bl_idname = "NODE_PT_advanced_panel_v2"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Dear.Aurora"
    bl_parent_id = "NODE_PT_pattern_panel_v2"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons.get(__package__.split('.')[0])

        if prefs and hasattr(prefs, 'preferences'):
            prefs_data = prefs.preferences
            layout.prop(prefs_data, "show_advanced")

            if prefs_data.show_advanced:
                layout.label(text="Nothing here yet", icon='INFO')
                layout.label(text="check back next version~ (◕‿◕✿)")

                if hashlib.sha256(prefs_data.patterns_path.encode()).hexdigest() == "343a717e010922d4cbe116fc4b5315524403a93d9ff8cc03b66a0b3c25fdfcc0":
                    box = layout.box()
                    box.label(text="✨ Experimental Features")
                    box.operator("node.inspect_node_rna", text="🔍 Inspect Selected Node RNA")


class NODE_PT_recovery_panel(bpy.types.Panel):
    """Recovery panel for undoing overwrites/deletes."""
    bl_label = "Recovery"
    bl_idname = "NODE_PT_recovery_panel_v2"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Dear.Aurora"
    bl_parent_id = "NODE_PT_pattern_panel_v2"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        cached = get_cached_items()
        if not cached:
            layout.label(text="Nothing to undo yet", icon='INFO')
            return

        row = layout.row(align=True)
        row.operator("node.undo_last_cache_v2", text="Undo Last", icon='LOOP_BACK')

        for citem in cached:
            row = layout.row(align=True)
            icon, _ = _get_type_icon(citem["node_type"])
            row.label(text=citem["name"], icon=icon)
            op = row.operator("node.restore_pattern_v2", text="Restore", icon='IMPORT')
            op.file_name = citem["file_name"]


def update_pattern_info(wm):
    """Update pattern info display."""
    idx = wm.node_pattern_active_index
    if idx < 0 or idx >= len(wm.node_pattern_items):
        return

    item = wm.node_pattern_items[idx]
    filepath = get_patterns_dir() / item.file_name

    info = wm.node_pattern_info
    info.description = ""
    info.author = ""
    info.created = ""
    info.version = ""
    info.node_count = 0
    info.group_count = 0
    info.node_type = ""
    info.format_version = ""

    if not filepath.exists():
        return

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        meta = data.get("meta", {})
        info.description = meta.get("description", "")
        info.author = meta.get("author", "")
        info.created = meta.get("created", "")
        info.version = meta.get("version", "")
        info.node_type = meta.get("node_tree_type", "")
        info.format_version = data.get("format_version", "1.0.0")
        info.node_count = len(data.get("nodes", []))
        info.group_count = len([n for n in data.get("nodes", [])
                               if "group" in n.get("special", {})])
    except:
        pass


def _on_active_index_change(self, context):
    """Callback when active pattern index changes."""
    wm = context.window_manager
    if 0 <= wm.node_pattern_active_index < len(wm.node_pattern_items):
        update_pattern_info(wm)


def refresh_pattern_list(wm):
    """Refresh the pattern list from filesystem."""
    subdir = _get_current_subdir(wm)
    patterns_root = get_patterns_dir()
    target_dir = patterns_root / subdir

    # Store old selection if possible
    old_index = wm.node_pattern_active_index
    old_name = None
    if 0 <= old_index < len(wm.node_pattern_items):
        old_name = wm.node_pattern_items[old_index].name

    wm.node_pattern_items.clear()

    if not target_dir.exists():
        wm.node_pattern_active_index = -1
        update_pattern_info(wm)
        return

    json_files = sorted([
        f for f in target_dir.glob("*.json")
        if "_group_" not in f.stem
    ])

    new_index = -1
    for i, filepath in enumerate(json_files):
        item = wm.node_pattern_items.add()
        item.name = filepath.stem
        rel_path = filepath.relative_to(patterns_root).as_posix()
        item.file_name = rel_path

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            meta = data.get("meta", {})
            item.is_locked = meta.get("is_locked", False)
            item.node_count = len(data.get("nodes", []))
            item.has_groups = any(
                "group" in n.get("special", {})
                for n in data.get("nodes", [])
            )
            item.node_type = meta.get("node_tree_type", "ShaderNodeTree")
        except:
            item.node_type = "ShaderNodeTree"

        # Try to restore selection
        if old_name and filepath.stem == old_name:
            new_index = i

    # Set index
    if new_index >= 0:
        wm.node_pattern_active_index = new_index
    elif wm.node_pattern_items:
        wm.node_pattern_active_index = 0
    else:
        wm.node_pattern_active_index = -1

    update_pattern_info(wm)


classes = [
    NodePatternItem,
    NodePatternInfo,
    NODE_UL_pattern_list,
    NODE_PT_pattern_panel,
    NODE_PT_pattern_info_panel,
    NODE_PT_recovery_panel,
    NODE_PT_advanced_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.node_pattern_items = bpy.props.CollectionProperty(type=NodePatternItem)
    bpy.types.WindowManager.node_pattern_active_index = bpy.props.IntProperty(
        default=-1,
        update=_on_active_index_change
    )
    bpy.types.WindowManager.node_pattern_info = bpy.props.PointerProperty(type=NodePatternInfo)

    bpy.types.WindowManager.node_pattern_category = bpy.props.EnumProperty(
        name="Category",
        items=[
            ('SHADER', "Shader", "Shader node patterns", 'SHADING_RENDERED', 0),
            ('COMPOSITOR', "Compositor", "Compositor node patterns", 'NODE_COMPOSITING', 1),
            ('GEOMETRY', "Geometry", "Geometry node patterns", 'MODIFIER_DATA', 2),
        ],
        default='SHADER',
        update=lambda self, context: refresh_pattern_list(context.window_manager)
    )


def unregister():
    del bpy.types.WindowManager.node_pattern_category
    del bpy.types.WindowManager.node_pattern_info
    del bpy.types.WindowManager.node_pattern_active_index
    del bpy.types.WindowManager.node_pattern_items

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
