# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""Blender operators for AuroraSNodeManager."""
import json
import re
import shutil
import zipfile
import tempfile
from pathlib import Path

import bpy

from ..core.serializer import PatternSerializer
from ..core.deserializer import PatternDeserializer
from ..core import transport
from ..utils import logger
from ..utils.translations import tr
from ..utils.file_utils import (
    sanitize_filename, get_patterns_dir, get_unique_filename, AuroraJSONEncoder,
    TYPE_SUBDIR_MAP, ADDON_ROOT, validate_clipboard_data, CLIPBOARD_BUNDLE_KEY,
    move_to_cache, restore_from_cache, get_cached_items, clear_cache,
    strip_local_paths, get_addon_preferences,
    inject_resource_paths, scan_resources, extract_resources,
    validate_json_paths,
)


_CONTEXT_KEYS = (
    "window_manager", "window", "screen", "workspace",
    "area", "region", "space_data", "scene",
)


def _captured_context():
    """Snapshot the context members needed to invoke an operator later."""
    c = bpy.context
    out = {}
    for key in _CONTEXT_KEYS:
        if hasattr(c, key):
            value = getattr(c, key)
            if value is not None:
                out[key] = value
    return out


def _run_with_context(legacy_call, modern_call, overrides):
    """Execute an operator under a context override, compatible with
    Blender 3.6 through 5.x.

    Blender 4.0 removed the legacy "context dict as first bpy.ops argument"
    override, so 4.0+ uses ``Context.temp_override`` (available since 3.2),
    while 3.6 keeps the legacy call.
    """
    if bpy.app.version >= (4, 0, 0):
        with bpy.context.temp_override(**overrides):
            return modern_call()
    return legacy_call(overrides)


def _schedule_dialog(bl_idname):
    """Invoke an operator (e.g. a props dialog) after the current operator
    finishes, avoiding nested ``bpy.ops`` popups that fail to display."""
    overrides = _captured_context()

    def _open():
        try:
            module, name = bl_idname.split(".")
            op = getattr(getattr(bpy.ops, module), name)
            _run_with_context(
                lambda o: op(o, 'INVOKE_DEFAULT'),
                lambda: op('INVOKE_DEFAULT'),
                overrides,
            )
        except Exception as e:
            print(f"[AURORA] Failed to open dialog ({bl_idname}): {e}")
        return None

    try:
        bpy.app.timers.register(_open, first_interval=0.1)
    except Exception as e:
        print(f"[AURORA] Failed to open dialog via timer: {e}")


def auto_refresh(func):
    """Decorator to refresh pattern list after operator execution."""
    def wrapper(self, context):
        from ..ui.panels import refresh_pattern_list
        result = func(self, context)
        if result == {'FINISHED'}:
            refresh_pattern_list(context.window_manager)
        return result
    return wrapper


# State handed between the import operator and the resource-confirm dialogs.
_pending_import = None


def _finish_import(context, main_data, groups_data):
    """Save an imported pattern + groups and refresh the pattern list.

    Returns (safe_name, pattern_name).
    """
    node_type = main_data.get("meta", {}).get("node_tree_type", "ShaderNodeTree")
    subdir_name = TYPE_SUBDIR_MAP.get(node_type, 'shader')
    patterns_root = get_patterns_dir()
    save_dir = patterns_root / subdir_name
    save_dir.mkdir(parents=True, exist_ok=True)

    pattern_name = main_data.get("meta", {}).get("name", "imported_pattern")
    safe_name = sanitize_filename(pattern_name)
    safe_name = get_unique_filename(safe_name, save_dir)

    main_filepath = save_dir / f"{safe_name}.json"
    with open(main_filepath, 'w', encoding='utf-8') as f:
        json.dump(main_data, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

    for gid, gdata in (groups_data or {}).items():
        gsafe = sanitize_filename(gid)
        gfpath = save_dir / f"{safe_name}_group_{gsafe}.json"
        with open(gfpath, 'w', encoding='utf-8') as f:
            json.dump(gdata, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

    from ..ui.panels import refresh_pattern_list
    refresh_pattern_list(context.window_manager)
    return safe_name, pattern_name


def _cleanup_inner(res):
    """Delete the temp pack file referenced by a res dict."""
    if res and res.get("inner_path"):
        try:
            Path(res["inner_path"]).unlink()
        except OSError:
            pass


def _cleanup_pending():
    """Delete the pending temp pack and clear the pending import state."""
    global _pending_import
    if _pending_import:
        _cleanup_inner(_pending_import.get("res"))
    _pending_import = None


class NODE_OT_save_pattern(bpy.types.Operator):
    """Save selected nodes as a pattern."""
    bl_idname = "node.save_pattern_v2"
    bl_label = "Save Node Pattern"
    bl_description = "Save the selected node state as a pattern file"
    bl_options = {'REGISTER', 'UNDO'}

    pattern_name: bpy.props.StringProperty(name="Pattern Name", default="my_pattern")
    description: bpy.props.StringProperty(name="Description", default="")
    author: bpy.props.StringProperty(name="Author", default="")
    version: bpy.props.StringProperty(name="Version", default="1.0.0")
    tags: bpy.props.StringProperty(name="Tags", default="")

    @auto_refresh
    def execute(self, context):
        node_tree = context.space_data.node_tree
        if not node_tree:
            self.report({'WARNING'}, "Please open node editor first")
            return {'CANCELLED'}

        selected = [n for n in node_tree.nodes if n.select]
        if not selected:
            self.report({'WARNING'}, "Please select some nodes")
            return {'CANCELLED'}

        # Serialize
        prefs = get_addon_preferences()
        meta = {
            "name": self.pattern_name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "tags": [t.strip() for t in self.tags.split(",") if t.strip()],
            "only_modified": prefs.only_modified if prefs else False,
        }

        serializer = PatternSerializer()
        pattern_data = serializer.serialize(selected, node_tree, meta)

        if not pattern_data:
            self.report({'ERROR'}, "Failed to serialize pattern")
            return {'CANCELLED'}

        # Determine save location
        node_type = node_tree.bl_idname
        subdir_name = TYPE_SUBDIR_MAP.get(node_type, 'shader')
        patterns_root = get_patterns_dir()
        save_dir = patterns_root / subdir_name
        save_dir.mkdir(parents=True, exist_ok=True)

        safe_name = sanitize_filename(self.pattern_name)
        safe_name = get_unique_filename(safe_name, save_dir)

        # Save main file
        main_filepath = save_dir / f"{safe_name}.json"
        with open(main_filepath, 'w', encoding='utf-8') as f:
            json.dump(pattern_data, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

        # Save group files
        group_data = serializer.get_group_data()
        saved_groups = 0
        for group_id, group_info in group_data.items():
            group_safe_name = sanitize_filename(group_id)
            group_filepath = save_dir / f"{safe_name}_group_{group_safe_name}.json"
            with open(group_filepath, 'w', encoding='utf-8') as f:
                json.dump(group_info, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)
            saved_groups += 1

        file_name = f"{subdir_name}/{safe_name}.json"
        self.report({'INFO'}, f"Saved {len(selected)} nodes to {file_name}")
        if saved_groups > 0:
            self.report({'INFO'}, f"Also saved {saved_groups} node groups")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pattern_name")
        layout.prop(self, "description")
        layout.prop(self, "author")
        layout.prop(self, "version")
        layout.prop(self, "tags")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class NODE_OT_load_pattern(bpy.types.Operator):
    """Load a pattern into the current node tree."""
    bl_idname = "node.load_pattern_v2"
    bl_label = "Load Pattern"
    bl_description = "Load the selected pattern into the node editor"
    bl_options = {'REGISTER', 'UNDO'}

    file_name: bpy.props.StringProperty()
    force_type: bpy.props.EnumProperty(
        name="Target Type",
        description="Force load into different node tree type",
        items=[
            ('AUTO', "Auto", "Use pattern's original type", 0),
            ('SHADER', "Shader", "Load as shader nodes", 1),
            ('COMPOSITOR', "Compositor", "Load as compositor nodes", 2),
            ('GEOMETRY', "Geometry", "Load as geometry nodes", 3),
        ],
        default='AUTO',
    )
    create_placeholders: bpy.props.BoolProperty(
        name="Create Placeholders",
        description="Create [MISSING] reroute placeholders for unsupported nodes",
        default=False,
        update=lambda self, ctx: (
            setattr(self, 'remove_orphan_islands', False),
            setattr(self, 'trim_reroute_chains', False),
        ) if self.create_placeholders else None,
    )
    remove_orphan_islands: bpy.props.BoolProperty(
        name="Remove Orphan Islands",
        description="Remove orphan nodes, empty frames, and reroute-only chains",
        default=False,
    )
    trim_reroute_chains: bpy.props.BoolProperty(
        name="Trim",
        description="Trim dangling reroute chains that connect to a real node on only one side",
        default=False,
    )
    ignore_version: bpy.props.BoolProperty(
        name="Ignore Version Mismatch",
        description="Load even if Blender major version differs from saved pattern",
        default=False,
    )

    def _check_version(self, context):
        """Read file version and check mismatch. Returns True if should block."""
        self._saved_version = (0, 0, 0)
        self._version_mismatch = False
        if not self.file_name:
            return False
        main_filepath = get_patterns_dir() / self.file_name
        if not main_filepath.exists():
            return False
        try:
            with open(main_filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            saved_ver = data.get("meta", {}).get("blender_version", [0, 0, 0])
            self._saved_version = tuple(saved_ver[:3])
            cur_ver = bpy.app.version[:3]
            if self._saved_version[0] != cur_ver[0]:
                self._version_mismatch = True
        except:
            pass
        return self._version_mismatch and not self.ignore_version

    def execute(self, context):
        if self._check_version(context):
            self.report({'WARNING'}, "Cancelled: Blender major version mismatch")
            return {'CANCELLED'}

        main_filepath = get_patterns_dir() / self.file_name

        if not main_filepath.exists():
            self.report({'ERROR'}, f"File does not exist: {self.file_name}")
            return {'CANCELLED'}

        node_tree = context.space_data.node_tree
        if not node_tree:
            self.report({'WARNING'}, "Please open node editor first")
            return {'CANCELLED'}

        with open(main_filepath, 'r', encoding='utf-8') as f:
            pattern_data = json.load(f)

        # Check type compatibility and handle cross-type loading
        pattern_tree_type = pattern_data.get("meta", {}).get("node_tree_type", "ShaderNodeTree")
        current_tree_type = node_tree.bl_idname

        # Handle forced type override
        force_type_map = {
            'SHADER': 'ShaderNodeTree',
            'COMPOSITOR': 'CompositorNodeTree',
            'GEOMETRY': 'GeometryNodeTree',
        }
        if self.force_type != 'AUTO':
            target_type = force_type_map.get(self.force_type)
            if target_type and target_type != pattern_tree_type:
                pattern_data["meta"]["node_tree_type"] = target_type
                pattern_tree_type = target_type
                self.report({'INFO'}, f"Forced cross-type load: {pattern_tree_type} -> {current_tree_type}")

        if pattern_tree_type != current_tree_type:
            self.report({'INFO'}, f"Cross-type load: {pattern_tree_type} -> {current_tree_type}")

        # Deserialize
        pattern_dir = main_filepath.parent
        base_name = main_filepath.stem

        deserializer = PatternDeserializer()
        deserializer.skip_unsupported = not self.create_placeholders
        warning_messages = []
        deserializer.on_warning = lambda msg: warning_messages.append(msg)
        created_nodes = deserializer.deserialize(pattern_data, node_tree, pattern_dir, base_name)

        # Trim dangling reroute chains if requested
        if self.trim_reroute_chains:
            trimmed = self._trim_reroute_chains(node_tree)
            if trimmed > 0:
                self.report({'INFO'}, f"Trimmed {trimmed} dangling reroute chains")

        # Remove orphan [MISSING] reroutes if requested
        if self.remove_orphan_islands:
            removed = self._remove_orphan_islands(node_tree)
            if removed > 0:
                self.report({'INFO'}, f"Removed {removed} orphan islands")

        # Report cross-type mappings
        if deserializer.mapped_nodes:
            for original, mapped in deserializer.mapped_nodes:
                self.report({'INFO'}, f"Mapped: {original} -> {mapped}")

        # Report missing nodes
        if deserializer.missing_nodes:
            unique_missing = set(deserializer.missing_nodes)
            self.report({'WARNING'}, f"Skipped {len(deserializer.missing_nodes)} unsupported nodes: {', '.join(unique_missing)}")

        if warning_messages:
            data = {}
            for m in warning_messages:
                if m.startswith("[WARN] ") and "." in m:
                    key = m[7:].split(".")[0]
                else:
                    key = "Unknown"
                entry = data.setdefault(key, {"count": 0})
                entry["count"] += 1
            parts = []
            for node_type, info in sorted(data.items()):
                parts.append(f"{info['count']} socket(s) had value errors in '{node_type}'")

            def draw_popup(self, ctx):
                layout = self.layout
                layout.label(text=f"Loaded {len(created_nodes)} nodes", icon='INFO')
                layout.separator()
                for part in parts:
                    layout.label(text=part, icon='ERROR')
                layout.label(text="Please check the affected nodes")

            context.window_manager.popup_menu(draw_popup, title="Load Warnings", icon='ERROR')
            self.report({'WARNING'}, f"Loaded {len(created_nodes)} nodes, {len(data)} node type(s) had errors")
        else:
            self.report({'INFO'}, f"Loaded {len(created_nodes)} nodes")
        return {'FINISHED'}

    def _remove_orphan_islands(self, node_tree):
        """Remove orphan nodes, empty frames, and reroute-only chains.

        Handles:
        1. Nodes with no links at all (orphan nodes)
        2. Empty frames (frames with no children)
        3. [MISSING] reroute placeholders with no connections
        4. Reroute-only chains (reroutes that do not connect to any real node)
        """
        to_remove = set()

        # Phase 1: collect all nodes that participate in any link
        linked_nodes = set()
        for link in node_tree.links:
            linked_nodes.add(link.from_node)
            linked_nodes.add(link.to_node)

        # Phase 2: orphan non-frame nodes with no links at all
        for node in node_tree.nodes:
            if node.bl_idname == "NodeFrame":
                continue
            if node not in linked_nodes:
                to_remove.add(node)

        # Phase 3: reroute-only chains
        # Build adjacency for reroute nodes
        reroute_nodes = {
            n for n in node_tree.nodes
            if n.bl_idname == "NodeReroute" and n not in to_remove
        }
        reroute_adj = {n: set() for n in reroute_nodes}
        reroute_to_real = {n: set() for n in reroute_nodes}

        for link in node_tree.links:
            fn, tn = link.from_node, link.to_node
            if fn in reroute_adj and tn in reroute_adj:
                reroute_adj[fn].add(tn)
                reroute_adj[tn].add(fn)
            elif fn in reroute_adj:
                reroute_to_real[fn].add(tn)
            elif tn in reroute_adj:
                reroute_to_real[tn].add(fn)

        visited = set()
        for reroute in reroute_nodes:
            if reroute in visited:
                continue
            component = set()
            stack = [reroute]
            has_real = False
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                if reroute_to_real.get(current):
                    has_real = True
                for neighbor in reroute_adj.get(current, set()):
                    if neighbor not in visited:
                        stack.append(neighbor)
            if not has_real:
                to_remove.update(component)

        # Phase 4: empty frames (handle nesting via iterative pass)
        changed = True
        while changed:
            changed = False
            for node in node_tree.nodes:
                if node.bl_idname == "NodeFrame" and node not in to_remove:
                    has_children = any(
                        other.parent == node
                        for other in node_tree.nodes
                        if other != node and other not in to_remove
                    )
                    if not has_children:
                        to_remove.add(node)
                        changed = True

        # Phase 5: execute removal
        removed = 0
        for node in to_remove:
            try:
                node_tree.nodes.remove(node)
                removed += 1
            except Exception:
                pass

        return removed

    def _trim_reroute_chains(self, node_tree):
        """Trim dangling reroute chain segments.

        Iteratively prunes reroute nodes with fewer than 2 connections
        (reroute neighbors + real node neighbors). This handles branches:
        only the dangling dead-end branch gets removed.
        """
        reroutes = {n for n in node_tree.nodes if n.bl_idname == "NodeReroute"}
        if not reroutes:
            return 0

        adj = {n: set() for n in reroutes}
        real_conn = {n: set() for n in reroutes}

        for link in node_tree.links:
            a, b = link.from_node, link.to_node
            if a in adj and b in adj:
                adj[a].add(b)
                adj[b].add(a)
            elif a in adj:
                real_conn[a].add(b)
            elif b in adj:
                real_conn[b].add(a)

        to_remove = set()

        changed = True
        while changed:
            changed = False
            for node in reroutes:
                if node in to_remove:
                    continue
                rr = [n for n in adj.get(node, set()) if n not in to_remove]
                rl = real_conn.get(node, set())
                if len(rr) + len(rl) < 2:
                    to_remove.add(node)
                    changed = True

        links_to_remove = [
            l for l in node_tree.links
            if l.from_node in to_remove or l.to_node in to_remove
        ]
        for link in links_to_remove:
            try:
                node_tree.links.remove(link)
            except Exception:
                pass

        trimmed = 0
        for node in to_remove:
            try:
                node_tree.nodes.remove(node)
                trimmed += 1
            except Exception:
                pass

        return trimmed

    def draw(self, context):
        layout = self.layout
        if getattr(self, '_version_mismatch', False):
            box = layout.box()
            box.alert = True
            saved_ver = '.'.join(str(v) for v in self._saved_version)
            cur_ver = '.'.join(str(v) for v in bpy.app.version[:3])
            box.label(text="Saved in Blender %s" % saved_ver, icon='ERROR')
            box.label(text="Current Blender %s" % cur_ver)
            box.label(text="Major version difference may cause unexpected errors")
            box.prop(self, "ignore_version")
            layout.separator()
        layout.prop(self, "force_type")
        layout.prop(self, "create_placeholders")
        col = layout.column()
        col.enabled = not self.create_placeholders
        col.prop(self, "remove_orphan_islands")
        col.prop(self, "trim_reroute_chains")

    def invoke(self, context, event):
        self._check_version(context)
        self.create_placeholders = False
        if self.file_name:
            main_filepath = get_patterns_dir() / self.file_name
            if main_filepath.exists():
                try:
                    with open(main_filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    pattern_tree_type = data.get("meta", {}).get("node_tree_type", "ShaderNodeTree")
                    current_tree_type = context.space_data.node_tree.bl_idname
                    if pattern_tree_type != current_tree_type:
                        self.create_placeholders = True
                except Exception:
                    pass
        return context.window_manager.invoke_props_dialog(self)


class NODE_OT_delete_pattern(bpy.types.Operator):
    """Delete a saved pattern."""
    bl_idname = "node.delete_pattern_v2"
    bl_label = "Delete Pattern"
    bl_description = "Delete the selected pattern"
    bl_options = {'REGISTER', 'UNDO'}

    file_name: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    @auto_refresh
    def execute(self, context):
        filepath = get_patterns_dir() / self.file_name

        if not filepath.exists():
            self.report({'ERROR'}, f"File does not exist: {self.file_name}")
            return {'CANCELLED'}

        if not move_to_cache(self.file_name):
            self.report({'ERROR'}, f"Failed to move to cache: {self.file_name}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Moved to cache: {self.file_name}")
        return {'FINISHED'}


class NODE_OT_edit_pattern_info(bpy.types.Operator):
    """Edit pattern metadata."""
    bl_idname = "node.edit_pattern_info_v2"
    bl_label = "Edit Pattern Info"
    bl_description = "Edit the metadata of the selected pattern"
    bl_options = {'REGISTER', 'UNDO'}

    file_name: bpy.props.StringProperty()

    new_name: bpy.props.StringProperty(name="Name")
    new_description: bpy.props.StringProperty(name="Description")
    new_author: bpy.props.StringProperty(name="Author")
    new_version: bpy.props.StringProperty(name="Version")
    new_tags: bpy.props.StringProperty(name="Tags")

    @auto_refresh
    def execute(self, context):
        filepath = get_patterns_dir() / self.file_name
        if not filepath.exists():
            self.report({'ERROR'}, f"File does not exist: {self.file_name}")
            return {'CANCELLED'}

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        meta = data.get("meta", {})
        meta["name"] = self.new_name
        meta["description"] = self.new_description
        meta["author"] = self.new_author
        meta["version"] = self.new_version
        meta["tags"] = [t.strip() for t in self.new_tags.split(",") if t.strip()]
        data["meta"] = meta

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

        # Rename file if needed
        old_stem = filepath.stem
        new_stem = sanitize_filename(self.new_name)
        if new_stem != old_stem:
            new_path = filepath.parent / f"{new_stem}.json"
            if new_path.exists() and new_path != filepath:
                self.report({'ERROR'}, f"Name already exists: {self.new_name}")
                return {'CANCELLED'}

            filepath.rename(new_path)
            # Rename associated group files
            for group_file in filepath.parent.glob(f"{old_stem}_group_*.json"):
                new_group_name = group_file.name.replace(old_stem, new_stem, 1)
                group_file.rename(filepath.parent / new_group_name)

        self.report({'INFO'}, f"Updated: {self.new_name}")
        return {'FINISHED'}

    def invoke(self, context, event):
        filepath = get_patterns_dir() / self.file_name
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            meta = data.get("meta", {})
            self.new_name = meta.get("name", filepath.stem)
            self.new_description = meta.get("description", "")
            self.new_author = meta.get("author", "")
            self.new_version = meta.get("version", "1.0.0")
            self.new_tags = ", ".join(meta.get("tags", []))

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "new_name")
        layout.prop(self, "new_description")
        layout.prop(self, "new_author")
        layout.prop(self, "new_version")
        layout.prop(self, "new_tags")


class NODE_OT_overwrite_pattern(bpy.types.Operator):
    """Overwrite an existing pattern."""
    bl_idname = "node.overwrite_pattern_v2"
    bl_label = "Overwrite Pattern"
    bl_description = "Overwrite the selected pattern with the current node state"
    bl_options = {'REGISTER', 'UNDO'}

    file_name: bpy.props.StringProperty()
    ignore_version: bpy.props.BoolProperty(
        name="Ignore Version Mismatch",
        description="Overwrite even if Blender major version differs",
        default=False,
    )

    def _check_version(self, context):
        self._saved_version = (0, 0, 0)
        self._version_mismatch = False
        self._saved_node_tree_type = None
        if not self.file_name:
            return False
        filepath = get_patterns_dir() / self.file_name
        if not filepath.exists():
            return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            meta = data.get("meta", {})
            saved_ver = meta.get("blender_version", [0, 0, 0])
            self._saved_version = tuple(saved_ver[:3])
            self._saved_node_tree_type = meta.get("node_tree_type", "ShaderNodeTree")
            cur_ver = bpy.app.version[:3]
            if self._saved_version[0] != cur_ver[0]:
                self._version_mismatch = True
        except:
            pass
        return self._version_mismatch and not self.ignore_version

    def draw(self, context):
        layout = self.layout
        # Confirmation prompt
        if getattr(self, '_is_cross_type', False):
            type_name = getattr(self, '_cross_type_name', "Unknown")
            layout.label(text="Confirm overwrite to %s type?" % type_name, icon='QUESTION')
        else:
            layout.label(text="Confirm overwrite?", icon='QUESTION')
        layout.separator()
        if getattr(self, '_version_mismatch', False):
            box = layout.box()
            box.alert = True
            saved_ver = '.'.join(str(v) for v in self._saved_version)
            cur_ver = '.'.join(str(v) for v in bpy.app.version[:3])
            box.label(text="Saved in Blender %s" % saved_ver, icon='ERROR')
            box.label(text="Current Blender %s" % cur_ver)
            box.label(text="Major version difference may cause unexpected errors")
            box.prop(self, "ignore_version")
            layout.separator()
        layout.label(text="Overwrite: %s" % Path(self.file_name).stem)

    def invoke(self, context, event):
        self._check_version(context)
        # Determine cross-type info
        node_tree = context.space_data.node_tree
        current_type = node_tree.bl_idname if node_tree else "ShaderNodeTree"
        saved_type = getattr(self, '_saved_node_tree_type', None) or "ShaderNodeTree"
        self._is_cross_type = saved_type != current_type
        type_name_map = {
            'ShaderNodeTree': "Shader",
            'CompositorNodeTree': "Compositor",
            'GeometryNodeTree': "Geometry",
        }
        self._cross_type_name = type_name_map.get(current_type, "Unknown")
        return context.window_manager.invoke_props_dialog(self)

    @auto_refresh
    def execute(self, context):
        if self._check_version(context):
            self.report({'WARNING'}, "Cancelled: Blender major version mismatch")
            return {'CANCELLED'}

        filepath = get_patterns_dir() / self.file_name
        pattern_name = filepath.stem

        # Check if nodes are selected
        node_tree = context.space_data.node_tree
        if not node_tree:
            self.report({'WARNING'}, "Please open node editor first")
            return {'CANCELLED'}

        selected = [n for n in node_tree.nodes if n.select]
        if not selected:
            self.report({'WARNING'}, "Please select some nodes to overwrite")
            return {'CANCELLED'}

        # Read old meta
        old_meta = {}
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                old_meta = old_data.get("meta", {})
            except:
                pass

            # Move old files to cache
            move_to_cache(self.file_name)

        # Serialize with old meta preserved
        meta = {
            "name": pattern_name,
            "description": old_meta.get("description", ""),
            "author": old_meta.get("author", ""),
            "version": old_meta.get("version", "1.0.0"),
            "tags": old_meta.get("tags", []),
        }

        serializer = PatternSerializer()
        pattern_data = serializer.serialize(selected, node_tree, meta)

        if not pattern_data:
            self.report({'ERROR'}, "Failed to serialize pattern")
            return {'CANCELLED'}

        # Determine save location
        node_type = node_tree.bl_idname
        subdir_name = TYPE_SUBDIR_MAP.get(node_type, 'shader')
        patterns_root = get_patterns_dir()
        save_dir = patterns_root / subdir_name
        save_dir.mkdir(parents=True, exist_ok=True)

        safe_name = sanitize_filename(pattern_name)
        safe_name = get_unique_filename(safe_name, save_dir)

        # Save main file
        main_filepath = save_dir / f"{safe_name}.json"
        with open(main_filepath, 'w', encoding='utf-8') as f:
            json.dump(pattern_data, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

        # Save group files
        group_data = serializer.get_group_data()
        saved_groups = 0
        for group_id, group_info in group_data.items():
            group_safe_name = sanitize_filename(group_id)
            group_filepath = save_dir / f"{safe_name}_group_{group_safe_name}.json"
            with open(group_filepath, 'w', encoding='utf-8') as f:
                json.dump(group_info, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)
            saved_groups += 1

        self.report({'INFO'}, f"Overwritten: {pattern_name}")
        return {'FINISHED'}


class NODE_OT_toggle_lock_pattern(bpy.types.Operator):
    """Toggle pattern lock status."""
    bl_idname = "node.toggle_lock_pattern_v2"
    bl_label = "Toggle Lock Pattern"
    bl_description = "Toggle the lock of the selected pattern"
    bl_options = {'REGISTER', 'UNDO'}

    file_name: bpy.props.StringProperty()

    @auto_refresh
    def execute(self, context):
        filepath = get_patterns_dir() / self.file_name

        if not filepath.exists():
            return {'CANCELLED'}

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        is_locked = data.get("meta", {}).get("is_locked", False)
        data["meta"]["is_locked"] = not is_locked

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

        status = "Locked" if not is_locked else "Unlocked"
        self.report({'INFO'}, f"{status}: {self.file_name}")
        return {'FINISHED'}


class NODE_OT_restore_pattern(bpy.types.Operator):
    """Restore a pattern from cache."""
    bl_idname = "node.restore_pattern_v2"
    bl_label = "Restore Pattern"
    bl_description = "Restore the selected cached pattern"
    bl_options = {'REGISTER', 'UNDO'}

    file_name: bpy.props.StringProperty()

    @auto_refresh
    def execute(self, context):
        if not restore_from_cache(self.file_name):
            self.report({'ERROR'}, f"Failed to restore: {self.file_name}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Restored: {self.file_name}")
        return {'FINISHED'}


class NODE_OT_undo_last_cache(bpy.types.Operator):
    """Restore the most recently cached pattern."""
    bl_idname = "node.undo_last_cache_v2"
    bl_label = "Undo Last"
    bl_description = "Undo the last overwrite/delete operation"
    bl_options = {'REGISTER', 'UNDO'}

    @auto_refresh
    def execute(self, context):
        items = get_cached_items()
        if not items:
            self.report({'WARNING'}, "Nothing to undo")
            return {'CANCELLED'}
        latest = items[0]
        if not restore_from_cache(latest["file_name"]):
            self.report({'ERROR'}, "Failed to undo last operation")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Restored: {latest['name']}")
        return {'FINISHED'}


class NODE_OT_migrate_patterns(bpy.types.Operator):
    """Migrate patterns to new storage path."""
    bl_idname = "node.migrate_patterns_v2"
    bl_label = "Migrate Patterns"
    bl_description = "Move pattern files to the new storage path"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = context.preferences.addons[__package__.split('.')[0]].preferences
        dst = Path(prefs.patterns_path)

        if prefs.last_known_path:
            src = Path(prefs.last_known_path)
        else:
            src = ADDON_ROOT / "patterns"

        if not src.exists():
            self.report({'INFO'}, "No source pattern files found")
            return {'FINISHED'}

        json_files = list(src.glob("**/*.json"))
        if not json_files:
            self.report({'INFO'}, "Source folder is already empty")
            return {'FINISHED'}

        dst.mkdir(parents=True, exist_ok=True)

        count = 0
        for f in json_files:
            rel = f.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(target))
            count += 1

        # Clean empty directories
        for d in sorted(src.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

        prefs.last_known_path = str(dst)

        from ..ui.panels import refresh_pattern_list
        refresh_pattern_list(context.window_manager)

        self.report({'INFO'}, tr("Migrated {} pattern files").format(count))
        return {'FINISHED'}


class NODE_OT_export_pattern(bpy.types.Operator):
    """Export pattern as .aurpak bundle."""
    bl_idname = "node.export_pattern_v2"
    bl_label = "Export Pattern"
    bl_description = "Export the selected pattern as an .aurpak file"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH', default="pattern_export.aurpak")
    filter_glob: bpy.props.StringProperty(default="*.aurpak", options={'HIDDEN'})

    use_pack_resources: bpy.props.BoolProperty(
        name="Pack Resources",
        description="Validate and pack resource files referenced by nodes (images/IES/videos/audio, etc.) into the pack; absolute paths never leak, the receiver may choose whether to keep them.",
        default=True,
    )

    def execute(self, context):
        wm = context.window_manager
        idx = wm.node_pattern_active_index
        if idx < 0 or idx >= len(wm.node_pattern_items):
            self.report({'ERROR'}, "No pattern selected")
            return {'CANCELLED'}

        file_name = wm.node_pattern_items[idx].file_name
        patterns_root = get_patterns_dir()
        main_file = patterns_root / file_name
        base_stem = Path(file_name).stem

        if not main_file.exists():
            self.report({'ERROR'}, "Pattern file not found")
            return {'CANCELLED'}

        with open(main_file, 'r', encoding='utf-8') as f:
            main_data = json.load(f)

        # Collect group files
        groups_data = {}
        for gf in main_file.parent.glob(f"{base_stem}_group_*.json"):
            with open(gf, 'r', encoding='utf-8') as f:
                gdata = json.load(f)
            gid = gdata.get("meta", {}).get("name", gf.stem)
            groups_data[gid] = gdata

        # Export
        bundle_path = Path(self.filepath)
        if bundle_path.suffix != '.aurpak':
            bundle_path = bundle_path.with_suffix('.aurpak')

        from ..utils.file_utils import export_pattern_bundle
        bundle_path, warnings = export_pattern_bundle(
            main_data, groups_data, bundle_path,
            use_pack_resources=self.use_pack_resources,
        )

        for w in warnings:
            self.report({'WARNING'}, w)
        self.report({'INFO'}, tr("Exported to {}").format(bundle_path.name))
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class NODE_OT_import_pattern(bpy.types.Operator):
    """Import pattern from an .aurpak or .zip bundle."""
    bl_idname = "node.import_pattern_v2"
    bl_label = "Import Pattern"
    bl_description = "Import patterns from an .aurpak or .zip file"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.aurpak;*.zip", options={'HIDDEN'})

    def execute(self, context):
        global _pending_import

        from ..utils.file_utils import import_pattern_bundle
        from ..utils.translations import tr

        main_data, groups_data, res = import_pattern_bundle(self.filepath)
        if not main_data:
            self.report({'ERROR'}, "Failed to import pattern")
            return {'CANCELLED'}

        # Cross-platform warning
        saved_platform = main_data.get("meta", {}).get("platform")
        current_platform = bpy.app.build_platform
        if saved_platform and saved_platform != current_platform:
            def draw_popup(self, context):
                layout = self.layout
                layout.label(text=tr("节点组创建于 {platform}。跨平台加载时，渲染与计算效果可能存在细微差异。").format(platform=saved_platform))
            bpy.ops.wm.popup_menu(draw_popup, title=tr("Cross-Platform Warning"), icon='INFO')

        issues, has_tokens = validate_json_paths(main_data, groups_data)
        if issues:
            _cleanup_inner(res)
            shown = ", ".join(issues[:3])
            self.report({'ERROR'},
                        tr("JSON contains non-token paths that cannot be matched to resources ({} issue(s)): {}").format(len(issues), shown))
            return {'CANCELLED'}
        if has_tokens and not (res and res.get("present")):
            _cleanup_inner(res)
            self.report({'ERROR'}, tr("JSON contains resource tokens but the pack has no resource pack; cannot resolve references"))
            return {'CANCELLED'}

        _pending_import = {
            "filepath": self.filepath,
            "main_data": main_data,
            "groups_data": groups_data,
            "res": res,
        }

        if res and res["present"]:
            _schedule_dialog("node.import_resources_keep")
            return {'FINISHED'}

        # No pack: foreign members are tamper evidence -> drop and import.
        if res and res.get("foreign"):
            _pending_import = None
            for name in res["foreign"][:10]:
                self.report({'WARNING'}, tr("Foreign file (tamper evidence) ignored: {}").format(name))
            safe_name, pattern_name = _finish_import(context, main_data, groups_data)
            self.report({'INFO'}, tr("Imported pattern: {}").format(pattern_name))
            return {'FINISHED'}

        _pending_import = None
        safe_name, pattern_name = _finish_import(context, main_data, groups_data)
        self.report({'INFO'}, tr("Imported pattern: {}").format(pattern_name))
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class NODE_OT_import_resources_keep(bpy.types.Operator):
    """Ask whether to keep the resource pack attached to an .aurpak bundle."""
    bl_idname = "node.import_resources_keep"
    bl_label = "Keep Resource Pack?"
    bl_options = {'REGISTER'}

    keep_resources: bpy.props.BoolProperty(name="Keep Resource Pack", default=True)

    def draw(self, context):
        layout = self.layout
        pi = _pending_import
        res = pi["res"] if pi else None
        count = res["file_count"] if res else 0
        size = res["total_size"] if res else 0
        layout.label(text=tr("This pack includes a resource pack:"))
        layout.label(text=tr("{} resource files, {:.2f} MB total").format(count, size/1024/1024), icon='PACKAGE')
        if res and res.get("bomb"):
            layout.label(text=tr("Resource pack exceeds size limit: {}").format(res.get('bomb_reason') or ''), icon='ERROR')
        if res and res.get("foreign"):
            layout.label(text=tr("The pack contains foreign files that will be treated as tampering and deleted"), icon='ERROR')
        layout.prop(self, "keep_resources")
        layout.label(text=tr("Not keeping will discard the resources without checks"), icon='INFO')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=480)

    def execute(self, context):
        global _pending_import
        pi = _pending_import
        if not pi:
            self.report({'ERROR'}, tr("No pending import data"))
            return {'CANCELLED'}

        if not self.keep_resources:
            main_data = pi["main_data"]
            strip_local_paths(main_data)
            for gd in pi["groups_data"].values():
                strip_local_paths(gd)
            _cleanup_pending()
            safe_name, pattern_name = _finish_import(context, main_data, pi["groups_data"])
            self.report({'INFO'}, tr("Discarded resource pack, imported pattern: {}").format(pattern_name))
            return {'FINISHED'}

        # Keep -> scan (in-memory classification, nothing written to disk).
        res = pi["res"] or {}
        scan = {"tamper": False, "entries": [], "manifest": None}
        if res.get("inner_path"):
            scan = scan_resources(res["inner_path"])
        pi["scan"] = scan

        prefs = get_addon_preferences()
        safe_mode = bool(getattr(prefs, 'safe_import', True))

        auto_deleted = list(res.get("foreign") or [])
        unexpected = []
        dialog_tiers = set()
        for e in scan["entries"]:
            if not e.get("sha_valid"):
                auto_deleted.append(e["name"])
                continue
            tier = e["tier"]
            if tier == 'whitelist':
                continue
            if tier == 'blacklist':
                if safe_mode:
                    auto_deleted.append(e["name"])
                else:
                    unexpected.append(e)
                    dialog_tiers.add('blacklist')
            else:  # report / unknown type
                unexpected.append(e)
                dialog_tiers.add('report')
        pi["auto_deleted"] = auto_deleted
        pi["dialog_tiers"] = dialog_tiers

        if unexpected:
            _schedule_dialog("node.import_resources_unexpected")
        else:
            _schedule_dialog("node.import_resources_confirm")
        return {'FINISHED'}


class NODE_OT_import_resources_unexpected(bpy.types.Operator):
    """Report unexpected resource types; user decides keep-all or delete-all."""
    bl_idname = "node.import_resources_unexpected"
    bl_label = "Unexpected Extra Resource Types"
    bl_options = {'REGISTER'}

    keep_all: bpy.props.BoolProperty(name="Keep these resources (keep-all)", default=False)

    def draw(self, context):
        layout = self.layout
        layout.alert = True
        layout.label(text=tr("The resource pack contains unexpected extra resource types:"), icon='QUESTION')
        pi = _pending_import
        if pi:
            scan = pi.get("scan") or {}
            tiers = pi.get("dialog_tiers") or set()
            for e in scan.get("entries", []):
                if not e.get("sha_valid"):
                    continue
                if e["tier"] not in tiers:
                    continue
                icon = 'ERROR' if e["tier"] == 'blacklist' else 'INFO'
                layout.label(text=f"  - {e['name']}", icon=icon)
        layout.prop(self, "keep_all")
        layout.label(text=tr("Not keeping will delete all of them (default)."), icon='INFO')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)

    def execute(self, context):
        global _pending_import
        pi = _pending_import
        if not pi:
            self.report({'ERROR'}, tr("No pending import data"))
            return {'CANCELLED'}
        pi["keep_unexpected"] = self.keep_all
        _schedule_dialog("node.import_resources_confirm")
        return {'FINISHED'}


class NODE_OT_import_resources_confirm(bpy.types.Operator):
    """Confirm resource storage location and extract."""
    bl_idname = "node.import_resources_confirm"
    bl_label = "Choose Resource Storage Location"
    bl_options = {'REGISTER'}

    extract_dir: bpy.props.StringProperty(name="Storage Location", subtype='DIR_PATH', default="")

    def draw(self, context):
        layout = self.layout
        layout.label(text=tr("Choose where to store the resource files:"), icon='FILE_FOLDER')
        layout.prop(self, "extract_dir")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)

    def execute(self, context):
        global _pending_import
        pi = _pending_import
        if not pi:
            self.report({'ERROR'}, tr("No pending import data"))
            return {'CANCELLED'}
        if not self.extract_dir:
            self.report({'ERROR'}, tr("Please choose a resource storage location"))
            return {'CANCELLED'}

        scan = pi.get("scan") or {}
        manifest = scan.get("manifest")
        res = pi.get("res") or {}
        inner_path = res.get("inner_path")

        extra_extract = set()
        if pi.get("keep_unexpected"):
            extra_extract = set(pi.get("dialog_tiers") or set())

        extract_map = {}
        warnings = []
        integrity_skipped = 0
        if inner_path:
            extract_map, warnings, integrity_skipped = extract_resources(
                inner_path, self.extract_dir, manifest, extra_extract=extra_extract,
            )

        if extract_map:
            inject_resource_paths(pi["main_data"], extract_map)
            for gd in pi["groups_data"].values():
                inject_resource_paths(gd, extract_map)
        else:
            strip_local_paths(pi["main_data"])
            for gd in pi["groups_data"].values():
                strip_local_paths(gd)

        auto_deleted = pi.get("auto_deleted") or []
        _cleanup_pending()
        safe_name, pattern_name = _finish_import(context, pi["main_data"], pi["groups_data"])
        for w in warnings:
            self.report({'WARNING'}, w)
        for name in auto_deleted[:10]:
            self.report({'WARNING'}, tr("Tampered/risky file deleted: {}").format(name))
        msg = tr("Imported pattern: {} ({} resource(s) extracted)").format(pattern_name, len(extract_map))
        if integrity_skipped:
            msg += tr(", {} integrity-flagged file(s) deleted").format(integrity_skipped)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def _build_copy_payload(compact_text, use_encryption, password, use_sharding, shard_size):
    """Apply the optional encryption/sharding layers to a compact payload.

    Returns (clipboard_text, chunks, error). ``chunks`` is the shard list when
    sharding is enabled (and ``clipboard_text`` is the serialized first chunk),
    else None. ``error`` is set on failure.
    """
    payload = compact_text
    if use_encryption:
        if not password:
            return None, None, tr("No encryption password set")
        try:
            wrapper = transport.encrypt_text(compact_text, password)
        except ValueError as e:
            return None, None, str(e)
        payload = json.dumps(wrapper, separators=(",", ":"), ensure_ascii=False)
    if use_sharding:
        extra_first = {"encrypted": 1 if use_encryption else 0}
        chunks = transport.shard_text(payload, shard_size, extra_first=extra_first)
        return transport.chunk_to_text(chunks[0]), chunks, None
    return payload, None, None


class NODE_OT_copy_pattern(bpy.types.Operator):
    """Copy pattern to clipboard as bundle JSON."""
    bl_idname = "node.copy_pattern_v2"
    bl_label = "Copy Pattern"
    bl_description = "Copy the selected pattern to clipboard as a bundle JSON"
    bl_options = {'REGISTER'}

    password: bpy.props.StringProperty(
        name="Encryption Password",
        description="Encryption password used for this copy.",
        subtype='PASSWORD',
        default="",
    )

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        return 0 <= wm.node_pattern_active_index < len(wm.node_pattern_items)

    def invoke(self, context, event):
        prefs = get_addon_preferences()
        if prefs and prefs.use_encryption and not prefs.encryption_password:
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "password")

    def execute(self, context):
        wm = context.window_manager
        idx = wm.node_pattern_active_index
        item = wm.node_pattern_items[idx]

        patterns_root = get_patterns_dir()
        main_file = patterns_root / item.file_name

        if not main_file.exists():
            self.report({'ERROR'}, "Pattern file not found")
            return {'CANCELLED'}

        with open(main_file, 'r', encoding='utf-8') as f:
            main_data = json.load(f)

        bundle = {
            CLIPBOARD_BUNDLE_KEY: True,
            "main": main_data,
            "groups": {},
        }

        base_stem = main_file.stem
        for gf in sorted(main_file.parent.glob(f"{base_stem}_group_*.json")):
            with open(gf, 'r', encoding='utf-8') as f:
                gdata = json.load(f)
            gid = gdata.get("meta", {}).get("name", gf.stem)
            bundle["groups"][gid] = gdata

        # Strip local absolute paths before sharing via clipboard
        strip_local_paths(main_data)
        for gdata in bundle["groups"].values():
            strip_local_paths(gdata)

        from ..core.codec import encode as codec_encode
        compact_text = codec_encode(bundle)

        prefs = get_addon_preferences()
        use_encryption = bool(prefs and prefs.use_encryption)
        use_sharding = bool(prefs and prefs.use_sharding)
        password = self.password or (prefs.encryption_password if prefs else "")
        shard_size = int(prefs.shard_size_preset) if prefs else 2000
        clip_text, chunks, err = _build_copy_payload(
            compact_text, use_encryption, password, use_sharding, shard_size)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        if chunks is not None:
            transport.open_send_session(chunks)
            context.window_manager.clipboard = clip_text
            transport.mark_shard_copied(0)
            self.report({'INFO'}, tr("Shard 1/{} copied; keep copying shards from the transfer window").format(len(chunks)))
            return {'FINISHED'}

        context.window_manager.clipboard = clip_text
        self.report({'INFO'}, tr("Copied to clipboard: {}").format(item.name))
        return {'FINISHED'}


class NODE_OT_copy_shard(bpy.types.Operator):
    """Copy a single shard to the clipboard."""
    bl_idname = "node.copy_shard_v2"
    bl_label = "Copy Shard"
    bl_description = "Copy a single shard to the clipboard"
    bl_options = {'REGISTER'}

    shard_index: bpy.props.IntProperty(default=0)

    def execute(self, context):
        session = transport.send_session()
        if not session:
            self.report({'ERROR'}, tr("No shard session"))
            return {'CANCELLED'}
        chunks = session["chunks"]
        if not (0 <= self.shard_index < len(chunks)):
            self.report({'ERROR'}, tr("Invalid shard number"))
            return {'CANCELLED'}
        context.window_manager.clipboard = transport.chunk_to_text(chunks[self.shard_index])
        transport.mark_shard_copied(self.shard_index)
        for area in context.screen.areas:
            area.tag_redraw()
        chunk = chunks[self.shard_index]
        self.report({'INFO'}, tr("Copied shard {}/{}").format(chunk['n'], chunk['m']))
        return {'FINISHED'}


class NODE_OT_reset_shard_session(bpy.types.Operator):
    """Clear the current send-side shard session."""
    bl_idname = "node.reset_shard_session_v2"
    bl_label = "Clear Shard Session"
    bl_description = "Clear the current shard send session"
    bl_options = {'REGISTER'}

    def execute(self, context):
        transport.reset_send_session()
        self.report({'INFO'}, tr("Send session cleared"))
        return {'FINISHED'}


class NODE_OT_reset_receiver_session(bpy.types.Operator):
    """Clear the current receive-side shard session."""
    bl_idname = "node.reset_receiver_session_v2"
    bl_label = "Clear Receive Session"
    bl_description = "Clear the current shard receive session"
    bl_options = {'REGISTER'}

    def execute(self, context):
        transport.collector.reset()
        transport.clear_receiver_token()
        transport.set_receiver_phase(None)
        transport.clear_pending_payload()
        self.report({'INFO'}, tr("Receive session cleared"))
        return {'FINISHED'}


class NODE_OT_inspect_node_rna(bpy.types.Operator):
    """View full RNA properties of the selected node."""
    bl_idname = "node.inspect_node_rna"
    bl_label = "RNA Inspector"
    bl_description = "Inspect the RNA properties of the selected node"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space and space.node_tree and space.node_tree.nodes.active

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=700)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        node = context.space_data.node_tree.nodes.active
        if not node:
            layout.label(text="No active node")
            return

        # Basic info
        box = layout.box()
        row = box.row()
        row.label(text=node.name, icon='NODE')
        row.label(text=node.bl_idname)
        if node.label:
            box.label(text=f"Label: {node.label}")

        # RNA Properties
        layout.separator()
        box = layout.box()
        box.label(text="RNA Properties")
        from ..core.rna_inspector import RNAInspector
        props = RNAInspector.discover_properties(node)
        if props:
            col = box.column(align=True)
            for prop_id, prop_info in props.items():
                row = col.row()
                row.label(text=prop_id)
                row = col.row()
                row.label(text=f"  [{prop_info.get('type', '?')}]  {str(prop_info.get('value', ''))[:100]}")
                col.separator()
        else:
            box.label(text="No serializable properties found")

        # Inputs
        layout.separator()
        box = layout.box()
        box.label(text="Inputs", icon='IMPORT')
        if node.inputs:
            for socket in node.inputs:
                val = ""
                if hasattr(socket, 'default_value'):
                    try:
                        val = str(socket.default_value)[:60]
                    except:
                        val = "<unreadable>"
                row = box.row()
                row.label(text=socket.name)
                row.label(text=socket.bl_idname)
                if val:
                    row.label(text=f"default={val}")
        else:
            box.label(text="(none)")

        # Outputs
        box = layout.box()
        box.label(text="Outputs", icon='EXPORT')
        if node.outputs:
            for socket in node.outputs:
                row = box.row()
                row.label(text=socket.name)
                row.label(text=socket.bl_idname)
        else:
            box.label(text="(none)")


def _paste_text(context, text):
    """Persist a decoded payload (compact or plain JSON) to disk and refresh."""
    result = validate_clipboard_data(text)
    if not result["valid"]:
        return {'CANCELLED'}, ({'ERROR'}, result["error"])

    main_data = result["main_data"]
    groups_data = result["groups_data"]

    node_type = main_data.get("meta", {}).get("node_tree_type", "ShaderNodeTree")
    subdir = TYPE_SUBDIR_MAP.get(node_type, 'shader')
    patterns_root = get_patterns_dir()
    save_dir = patterns_root / subdir
    save_dir.mkdir(parents=True, exist_ok=True)

    pattern_name = main_data.get("meta", {}).get("name", "pasted_pattern")
    safe_name = sanitize_filename(pattern_name)
    safe_name = get_unique_filename(safe_name, save_dir)

    main_filepath = save_dir / f"{safe_name}.json"
    with open(main_filepath, 'w', encoding='utf-8') as f:
        json.dump(main_data, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

    for gid, gdata in groups_data.items():
        gname = gdata.get("meta", {}).get("name", gid)
        gsafe = sanitize_filename(gname)
        gfpath = save_dir / f"{safe_name}_group_{gsafe}.json"
        with open(gfpath, 'w', encoding='utf-8') as f:
            json.dump(gdata, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

    from ..ui.panels import refresh_pattern_list
    refresh_pattern_list(context.window_manager)

    return {'FINISHED'}, ({'INFO'}, tr("Pasted pattern: {}").format(pattern_name))


def _handle_receiver_complete(context, operator, token):
    """Finish a receiver session: assemble all shards.

    Plain payloads are pasted immediately; encrypted payloads are stashed as
    pending and the receiver panel switches to its password UI (no nested
    operator dialogs). Returns the operator result set.
    """
    try:
        assembled = transport.collector.assemble(token)
    except ValueError as e:
        operator.report({'ERROR'}, str(e))
        return {'CANCELLED'}
    transport.collector.reset(token)
    try:
        data = json.loads(assembled)
    except Exception:
        data = None
    if isinstance(data, dict) and transport.is_encrypted(data):
        transport.set_pending_payload(data)
        transport.set_receiver_phase("decrypt", encrypted=True)
        operator.report({'INFO'}, tr("All shards received; enter the password in the transfer window to decrypt"))
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}
    result_set, msg = _paste_text(context, assembled)
    operator.report(msg[0], msg[1])
    transport.set_receiver_phase(None)
    transport.clear_receiver_token()
    for area in context.screen.areas:
        area.tag_redraw()
    return result_set


class NODE_OT_paste_pattern(bpy.types.Operator):
    """Paste pattern from clipboard."""
    bl_idname = "node.paste_pattern_v2"
    bl_label = "Paste Pattern"
    bl_description = "Import a pattern from clipboard"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        text = context.window_manager.clipboard
        if text and text.strip():
            try:
                data = json.loads(text)
            except Exception:
                data = None
            if isinstance(data, dict):
                if transport.is_shard(data):
                    token = data.get("token")
                    if not token:
                        self.report({'ERROR'}, tr("Incomplete shard info"))
                        return {'CANCELLED'}
                    result = transport.collector.feed(data)
                    if result["status"] == "conflict":
                        self.report({'ERROR'}, result["message"])
                        return {'CANCELLED'}
                    if result["status"] == "invalid":
                        self.report({'ERROR'}, result["message"])
                        return {'CANCELLED'}
                    transport.set_receiver_token(token)
                    if result["status"] == "ok":
                        self.report({'INFO'}, result["message"])
                    if transport.collector.is_complete(token):
                        return _handle_receiver_complete(context, self, token)
                    return {'FINISHED'}
                if transport.is_encrypted(data):
                    transport.set_pending_payload(data)
                    _schedule_dialog("node.decrypt_paste_v2")
                    return {'FINISHED'}
        return self.execute(context)

    def execute(self, context):
        text = context.window_manager.clipboard
        if not text or not text.strip():
            self.report({'ERROR'}, "Clipboard is empty")
            return {'CANCELLED'}
        result_set, msg = _paste_text(context, text)
        self.report(msg[0], msg[1])
        return result_set


class NODE_OT_paste_next_shard(bpy.types.Operator):
    """Read the clipboard and feed it into the current shard session."""
    bl_idname = "node.paste_next_shard_v2"
    bl_label = "Paste Next Shard"
    bl_description = "Paste the next shard from the clipboard"
    bl_options = {'REGISTER'}

    def execute(self, context):
        token = transport.receiver_token()
        if not token:
            self.report({'ERROR'}, tr("No active shard session"))
            return {'CANCELLED'}
        text = context.window_manager.clipboard
        if not text or not text.strip():
            self.report({'ERROR'}, tr("Clipboard is empty; copy a shard first"))
            return {'CANCELLED'}
        try:
            data = json.loads(text)
        except Exception:
            self.report({'ERROR'}, tr("Clipboard content is not a shard"))
            return {'CANCELLED'}
        if not transport.is_shard(data):
            self.report({'ERROR'}, tr("Clipboard content is not a shard"))
            return {'CANCELLED'}
        if data.get("token") != token:
            self.report({'ERROR'}, tr("Shard from a different batch, ignored"))
            return {'CANCELLED'}
        result = transport.collector.feed(data)
        if result["status"] in ("ok", "dup"):
            self.report({'INFO'}, result["message"])
        for area in context.screen.areas:
            area.tag_redraw()
        if transport.collector.is_complete(token):
            return _handle_receiver_complete(context, self, token)
        return {'FINISHED'}


class NODE_OT_decrypt_paste(bpy.types.Operator):
    """Request a password and paste decrypted clipboard data."""
    bl_idname = "node.decrypt_paste_v2"
    bl_label = "Enter Password to Decrypt"
    bl_description = "Enter the password to decrypt encrypted node data in the clipboard"
    bl_options = {'REGISTER', 'UNDO'}

    password: bpy.props.StringProperty(name="Decrypt Password", subtype='PASSWORD', default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "password")
        layout.label(text=tr("Enter the password to decrypt node data"), icon='LOCKED')

    def execute(self, context):
        wrapper = transport.pop_pending_payload()
        if wrapper is None:
            self.report({'ERROR'}, tr("No pending encrypted data"))
            return {'CANCELLED'}
        password = self.password or context.window_manager.aurora_decrypt_password
        if not password:
            self.report({'ERROR'}, tr("Please enter the decrypt password"))
            return {'CANCELLED'}
        try:
            text = transport.decrypt_text(wrapper, password)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        result_set, msg = _paste_text(context, text)
        if msg[1]:
            self.report(msg[0], msg[1])
        if transport.receiver_token() is not None:
            transport.set_receiver_phase(None)
            transport.clear_receiver_token()
            for area in context.screen.areas:
                area.tag_redraw()
        return result_set


def _fmt_size(size):
    return f"{size / 1024.0:.1f} KB" if size >= 1024 else f"{size} B"


class NODE_OT_export_logs(bpy.types.Operator):
    """Export selected session log files into a single archive file."""
    bl_idname = "node.export_logs_v2"
    bl_label = "Export Logs"
    bl_description = "Select the log files to export into a single archive file"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        wm = context.window_manager
        wm.aurora_log_entries.clear()
        for name, path, size, _mtime, entries in logger.list_logs():
            item = wm.aurora_log_entries.add()
            item.name = name
            item.path = path
            item.file_size = size
            item.entry_count = entries
            item.enabled = True
        if not wm.aurora_log_entries:
            self.report({'INFO'}, tr("No log files found"))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        entries = wm.aurora_log_entries
        if not entries:
            layout.label(text=tr("No log files found"), icon='INFO')
            return
        for item in entries:
            row = layout.row(align=True)
            row.prop(item, "enabled", text="")
            row.label(text="{} · {} {} · {}".format(
                item.name, item.entry_count, tr("entries"), _fmt_size(item.file_size)))

    def execute(self, context):
        wm = context.window_manager
        selected = [item.path for item in wm.aurora_log_entries if item.enabled]
        if not selected:
            self.report({'WARNING'}, tr("No logs selected"))
            return {'CANCELLED'}
        if not self.filepath:
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        try:
            target = logger.export_logs(selected, self.filepath)
        except Exception as e:
            self.report({'ERROR'}, "{}: {}".format(tr("Export failed"), e))
            return {'CANCELLED'}
        self.report({'INFO'}, tr("Exported {} logs to {}").format(len(selected), target))
        return {'FINISHED'}


class NODE_OT_clear_logs(bpy.types.Operator):
    """Delete all stored session log files."""
    bl_idname = "node.clear_logs_v2"
    bl_label = "Clear Logs"
    bl_description = "Delete all stored log files"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        deleted = logger.clear_logs()
        if not deleted:
            self.report({'INFO'}, tr("No log files to clear"))
            return {'CANCELLED'}
        self.report({'INFO'}, tr("Cleared {} log file(s)").format(len(deleted)))
        return {'FINISHED'}


classes = [
    NODE_OT_save_pattern,
    NODE_OT_load_pattern,
    NODE_OT_delete_pattern,
    NODE_OT_edit_pattern_info,
    NODE_OT_overwrite_pattern,
    NODE_OT_toggle_lock_pattern,
    NODE_OT_restore_pattern,
    NODE_OT_undo_last_cache,
    NODE_OT_migrate_patterns,
    NODE_OT_export_pattern,
    NODE_OT_import_pattern,
    NODE_OT_import_resources_keep,
    NODE_OT_import_resources_unexpected,
    NODE_OT_import_resources_confirm,
    NODE_OT_copy_pattern,
    NODE_OT_paste_pattern,
    NODE_OT_copy_shard,
    NODE_OT_reset_shard_session,
    NODE_OT_reset_receiver_session,
    NODE_OT_paste_next_shard,
    NODE_OT_decrypt_paste,
    NODE_OT_inspect_node_rna,
    NODE_OT_export_logs,
    NODE_OT_clear_logs,
]

classes = [logger.safe_operator(cls) for cls in classes]


def register():
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
