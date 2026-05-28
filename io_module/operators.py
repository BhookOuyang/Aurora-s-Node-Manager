"""Blender operators for AuroraSNodeManager."""
import json
import shutil
import zipfile
import tempfile
from pathlib import Path

import bpy

from ..core.serializer import PatternSerializer
from ..core.deserializer import PatternDeserializer
from ..utils.file_utils import (
    sanitize_filename, get_patterns_dir, get_unique_filename, AuroraJSONEncoder,
    TYPE_SUBDIR_MAP, ADDON_ROOT, validate_clipboard_data, CLIPBOARD_BUNDLE_KEY
)


def auto_refresh(func):
    """Decorator to refresh pattern list after operator execution."""
    def wrapper(self, context):
        from ..ui.panels import refresh_pattern_list
        result = func(self, context)
        if result == {'FINISHED'}:
            refresh_pattern_list(context.window_manager)
        return result
    return wrapper


class NODE_OT_save_pattern(bpy.types.Operator):
    """Save selected nodes as a pattern."""
    bl_idname = "node.save_pattern_v2"
    bl_label = "Save Node Pattern"
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
        meta = {
            "name": self.pattern_name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "tags": [t.strip() for t in self.tags.split(",") if t.strip()],
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
    skip_unsupported: bpy.props.BoolProperty(
        name="Skip Unsupported Nodes",
        description="Skip nodes that cannot be loaded instead of creating placeholders",
        default=False,
    )
    remove_reroutes: bpy.props.BoolProperty(
        name="Remove Placeholder Reroutes",
        description="Remove [MISSING] reroute nodes after loading",
        default=True,
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
        deserializer.skip_unsupported = self.skip_unsupported
        created_nodes = deserializer.deserialize(pattern_data, node_tree, pattern_dir, base_name)

        # Remove placeholder reroutes if requested
        if self.remove_reroutes:
            removed = self._remove_placeholder_reroutes(node_tree)
            if removed > 0:
                self.report({'INFO'}, f"Removed {removed} placeholder reroutes")

        # Report cross-type mappings
        if deserializer.mapped_nodes:
            for original, mapped in deserializer.mapped_nodes:
                self.report({'INFO'}, f"Mapped: {original} -> {mapped}")

        # Report missing nodes
        if deserializer.missing_nodes:
            unique_missing = set(deserializer.missing_nodes)
            self.report({'WARNING'}, f"Skipped {len(deserializer.missing_nodes)} unsupported nodes: {', '.join(unique_missing)}")

        self.report({'INFO'}, f"Loaded {len(created_nodes)} nodes")
        return {'FINISHED'}

    def _remove_placeholder_reroutes(self, node_tree):
        """Remove reroute nodes that were created as placeholders for unsupported nodes."""
        removed = 0
        to_remove = []
        for node in node_tree.nodes:
            if node.bl_idname == "NodeReroute" and node.label.startswith("[MISSING]"):
                to_remove.append(node)

        for node in to_remove:
            # Check if this reroute has any connections
            has_connections = any(link.from_node == node or link.to_node == node for link in node_tree.links)
            if not has_connections:
                node_tree.nodes.remove(node)
                removed += 1

        return removed

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
        layout.prop(self, "skip_unsupported")
        row = layout.row()
        row.enabled = not self.skip_unsupported
        row.prop(self, "remove_reroutes")
        if self.skip_unsupported:
            layout.label(text="No placeholder reroutes will be created", icon='INFO')

    def invoke(self, context, event):
        self._check_version(context)
        return context.window_manager.invoke_props_dialog(self)


class NODE_OT_delete_pattern(bpy.types.Operator):
    """Delete a saved pattern."""
    bl_idname = "node.delete_pattern_v2"
    bl_label = "Delete Pattern"
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

        base_name = filepath.stem
        # Delete associated group files
        for group_file in filepath.parent.glob(f"{base_name}_group_*.json"):
            group_file.unlink()
        # Delete main file
        filepath.unlink()

        self.report({'INFO'}, f"Deleted: {self.file_name}")
        return {'FINISHED'}


class NODE_OT_edit_pattern_info(bpy.types.Operator):
    """Edit pattern metadata."""
    bl_idname = "node.edit_pattern_info_v2"
    bl_label = "Edit Pattern Info"
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
        if not self.file_name:
            return False
        filepath = get_patterns_dir() / self.file_name
        if not filepath.exists():
            return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            saved_ver = data.get("meta", {}).get("blender_version", [0, 0, 0])
            self._saved_version = tuple(saved_ver[:3])
            cur_ver = bpy.app.version[:3]
            if self._saved_version[0] != cur_ver[0]:
                self._version_mismatch = True
        except:
            pass
        return self._version_mismatch and not self.ignore_version

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
        layout.label(text="Overwrite: %s" % Path(self.file_name).stem)

    def invoke(self, context, event):
        self._check_version(context)
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

            # Delete old files
            base_name = filepath.stem
            for group_file in filepath.parent.glob(f"{base_name}_group_*.json"):
                group_file.unlink()
            filepath.unlink()

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


class NODE_OT_migrate_patterns(bpy.types.Operator):
    """Migrate patterns to new storage path."""
    bl_idname = "node.migrate_patterns_v2"
    bl_label = "Migrate Patterns"
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

        self.report({'INFO'}, f"Migrated {count} pattern files")
        return {'FINISHED'}


class NODE_OT_export_pattern(bpy.types.Operator):
    """Export pattern as ZIP bundle."""
    bl_idname = "node.export_pattern_v2"
    bl_label = "Export Pattern"
    bl_description = "Export the selected pattern as a ZIP file"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH', default="pattern_export.zip")
    filter_glob: bpy.props.StringProperty(default="*.zip", options={'HIDDEN'})

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
        zip_path = Path(self.filepath)
        if zip_path.suffix != '.zip':
            zip_path = zip_path.with_suffix('.zip')

        from ..utils.file_utils import export_pattern_bundle
        export_pattern_bundle(main_data, groups_data, zip_path)

        self.report({'INFO'}, f"Exported to {zip_path.name}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class NODE_OT_import_pattern(bpy.types.Operator):
    """Import pattern from ZIP bundle."""
    bl_idname = "node.import_pattern_v2"
    bl_label = "Import Pattern"
    bl_description = "Import patterns from a ZIP file"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.zip", options={'HIDDEN'})

    def execute(self, context):
        from ..utils.file_utils import import_pattern_bundle

        main_data, groups_data = import_pattern_bundle(self.filepath)
        if not main_data:
            self.report({'ERROR'}, "Failed to import pattern")
            return {'CANCELLED'}

        # Determine target directory
        node_type = main_data.get("meta", {}).get("node_tree_type", "ShaderNodeTree")
        subdir_name = TYPE_SUBDIR_MAP.get(node_type, 'shader')
        patterns_root = get_patterns_dir()
        save_dir = patterns_root / subdir_name
        save_dir.mkdir(parents=True, exist_ok=True)

        pattern_name = main_data.get("meta", {}).get("name", "imported_pattern")
        safe_name = sanitize_filename(pattern_name)
        safe_name = get_unique_filename(safe_name, save_dir)

        # Save main file
        main_filepath = save_dir / f"{safe_name}.json"
        with open(main_filepath, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

        # Save group files
        for gid, gdata in (groups_data or {}).items():
            gsafe = sanitize_filename(gid)
            gfpath = save_dir / f"{safe_name}_group_{gsafe}.json"
            with open(gfpath, 'w', encoding='utf-8') as f:
                json.dump(gdata, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

        from ..ui.panels import refresh_pattern_list
        refresh_pattern_list(context.window_manager)

        self.report({'INFO'}, f"Imported pattern: {pattern_name}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class NODE_OT_copy_pattern(bpy.types.Operator):
    """Copy pattern to clipboard as bundle JSON."""
    bl_idname = "node.copy_pattern_v2"
    bl_label = "Copy Pattern"
    bl_description = "Copy the selected pattern to clipboard as a bundle JSON"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        return 0 <= wm.node_pattern_active_index < len(wm.node_pattern_items)

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

        text = json.dumps(bundle, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)
        context.window_manager.clipboard = text
        self.report({'INFO'}, f"Copied to clipboard: {item.name}")
        return {'FINISHED'}


class NODE_OT_inspect_node_rna(bpy.types.Operator):
    """View full RNA properties of the selected node."""
    bl_idname = "node.inspect_node_rna"
    bl_label = "RNA Inspector"
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


class NODE_OT_paste_pattern(bpy.types.Operator):
    """Paste pattern from clipboard."""
    bl_idname = "node.paste_pattern_v2"
    bl_label = "Paste Pattern"
    bl_description = "Import a pattern from clipboard"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        text = context.window_manager.clipboard
        if not text or not text.strip():
            self.report({'ERROR'}, "Clipboard is empty")
            return {'CANCELLED'}

        result = validate_clipboard_data(text)
        if not result["valid"]:
            self.report({'ERROR'}, result["error"])
            return {'CANCELLED'}

        main_data = result["main_data"]
        groups_data = result["groups_data"]

        # Determine target directory
        node_type = main_data.get("meta", {}).get("node_tree_type", "ShaderNodeTree")
        subdir = TYPE_SUBDIR_MAP.get(node_type, 'shader')
        patterns_root = get_patterns_dir()
        save_dir = patterns_root / subdir
        save_dir.mkdir(parents=True, exist_ok=True)

        pattern_name = main_data.get("meta", {}).get("name", "pasted_pattern")
        safe_name = sanitize_filename(pattern_name)
        safe_name = get_unique_filename(safe_name, save_dir)

        # Save main file
        main_filepath = save_dir / f"{safe_name}.json"
        with open(main_filepath, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

        # Save group files
        for gid, gdata in groups_data.items():
            gname = gdata.get("meta", {}).get("name", gid)
            gsafe = sanitize_filename(gname)
            gfpath = save_dir / f"{safe_name}_group_{gsafe}.json"
            with open(gfpath, 'w', encoding='utf-8') as f:
                json.dump(gdata, f, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)

        from ..ui.panels import refresh_pattern_list
        refresh_pattern_list(context.window_manager)

        self.report({'INFO'}, f"Pasted pattern: {pattern_name}")
        return {'FINISHED'}


classes = [
    NODE_OT_save_pattern,
    NODE_OT_load_pattern,
    NODE_OT_delete_pattern,
    NODE_OT_edit_pattern_info,
    NODE_OT_overwrite_pattern,
    NODE_OT_toggle_lock_pattern,
    NODE_OT_migrate_patterns,
    NODE_OT_export_pattern,
    NODE_OT_import_pattern,
    NODE_OT_copy_pattern,
    NODE_OT_paste_pattern,
    NODE_OT_inspect_node_rna,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
