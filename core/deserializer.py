"""Core deserialization engine - RNA-based v3.0 with index-priority socket matching."""
import bpy
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from ..compat.blender_compat import map_socket_type, set_socket_value_safe
from ..compat.node_mappings import resolve_node_type, get_cross_type_mapping
from .topology import NodeTopology
from .rna_inspector import RNAInspector
from .zone_handler import ZoneHandler


class PatternDeserializer:
    """Industrial-grade node pattern deserializer - RNA-based."""

    def __init__(self):
        self.uuid_map: Dict[str, bpy.types.Node] = {}
        self.group_cache: Dict[str, bpy.types.NodeTree] = {}
        self.missing_nodes: List[str] = []
        self.mapped_nodes: List[Tuple[str, str]] = []
        self._pattern_dir: Optional[Path] = None
        self._base_name: Optional[str] = None
        self.skip_unsupported: bool = False

    def deserialize(self, data: Dict[str, Any], node_tree: bpy.types.NodeTree,
                    pattern_dir: Path = None, base_name: str = None) -> List[bpy.types.Node]:
        """Deserialize pattern data into node tree."""

        self._pattern_dir = pattern_dir
        self._base_name = base_name

        format_version = data.get("format_version", "1.0.0")
        if format_version == "1.0.0":
            print("[WARN] Loading legacy v1.0 pattern, applying compatibility mode")
        elif format_version == "2.0.0":
            print("[INFO] Loading v2.0 pattern, RNA properties will use fallback mode")
        elif format_version != "3.0.0":
            print(f"[WARN] Loading pattern with format version {format_version}, current is 3.0.0")

        pattern_tree_type = data.get("meta", {}).get("node_tree_type", "ShaderNodeTree")
        current_tree_type = node_tree.bl_idname

        if pattern_tree_type != current_tree_type:
            print(f"[INFO] Cross-type load: {pattern_tree_type} -> {current_tree_type}")

        nodes_data = data.get("nodes", [])
        links_data = data.get("links", [])

        created_nodes = []

        # Phase 1: Create all Frame nodes first
        for node_info in nodes_data:
            if node_info.get("bl_idname") == "NodeFrame":
                new_node = self._create_node(node_info, node_tree, current_tree_type, pattern_tree_type)
                if new_node:
                    old_uuid = node_info.get("uuid", node_info.get("id", ""))
                    self.uuid_map[old_uuid] = new_node
                    created_nodes.append(new_node)
                else:
                    self.missing_nodes.append(node_info.get("bl_idname", "unknown"))

        # Phase 1b: Restore Frame parent relationships with position correction
        for node_info in nodes_data:
            if node_info.get("bl_idname") == "NodeFrame":
                parent_uuid = node_info.get("parent_frame")
                if parent_uuid:
                    child = self.uuid_map.get(node_info.get("uuid"))
                    parent = self.uuid_map.get(parent_uuid)
                    if child and parent:
                        child.parent = parent
                        rel = node_info.get("location_relative")
                        if rel:
                            child.location = (parent.location.x + rel[0], parent.location.y + rel[1])

        # Phase 2: Create non-Frame nodes in topology order
        non_frame_nodes = [n for n in nodes_data if n.get("bl_idname") != "NodeFrame"]
        sorted_non_frames = NodeTopology.sort(non_frame_nodes, links_data)
        for node_info in sorted_non_frames:
            parent_uuid = node_info.get("parent_frame")
            parent_node = self.uuid_map.get(parent_uuid) if parent_uuid else None
            new_node = self._create_node(node_info, node_tree, current_tree_type, pattern_tree_type, parent_frame=parent_node)
            if new_node:
                old_uuid = node_info.get("uuid", node_info.get("id", ""))
                self.uuid_map[old_uuid] = new_node
                created_nodes.append(new_node)
            else:
                self.missing_nodes.append(node_info.get("bl_idname", "unknown"))

        # Node group interface must be set before links, otherwise GroupInput/Output sockets don't exist yet
        if data.get("meta", {}).get("is_subgroup", False):
            interface_data = data.get("interface", {})
            self._setup_interface(interface_data, node_tree)

        for link_info in links_data:
            self._create_link(link_info, node_tree)

        # Frame downgraded capture attribute nodes with their connected inputs
        saved_version = data.get("meta", {}).get("blender_version", [0, 0, 0])
        if bool(saved_version) and saved_version[0] > bpy.app.version[0]:
            for node_info in nodes_data:
                special = node_info.get("special", {})
                if "capture_items" not in special:
                    continue
                capture_uuid = node_info.get("uuid", "")
                capture_node = self.uuid_map.get(capture_uuid)
                if not capture_node or hasattr(capture_node, 'capture_items'):
                    continue
                connected_uuids = set()
                for link in links_data:
                    if link.get("to_uuid") == capture_uuid:
                        if link.get("to_socket_name", "") == "Geometry":
                            continue
                        from_uuid = link.get("from_uuid", "")
                        if from_uuid in self.uuid_map:
                            connected_uuids.add(from_uuid)
                nodes_to_frame = [capture_node] + [self.uuid_map[u] for u in connected_uuids]
                abs_x, abs_y = capture_node.location.x, capture_node.location.y
                frame = node_tree.nodes.new(type='NodeFrame')
                frame.location = (abs_x - 120, abs_y - 150)
                frame.width = max(400, capture_node.width + 200)
                frame.height = 350
                frame.label = "Version downgrade: capture socket mismatch"
                frame.use_custom_color = True
                frame.color = (1.0, 0.6, 0.0)
                for n in nodes_to_frame:
                    n.parent = frame

        self._pattern_dir = None
        self._base_name = None

        return created_nodes

    def _create_node(self, node_info: Dict[str, Any], node_tree: bpy.types.NodeTree,
                     target_tree_type: str, source_tree_type: str,
                     parent_frame: bpy.types.Node = None) -> Optional[bpy.types.Node]:
        """Create a single node with RNA property restoration."""

        original_type = node_info.get("bl_idname", "")

        blender_version = bpy.app.version
        resolved_type = resolve_node_type(original_type, blender_version)

        if source_tree_type != target_tree_type:
            mapped = get_cross_type_mapping(original_type, source_tree_type, target_tree_type)
            if mapped:
                resolved_type = mapped
                self.mapped_nodes.append((original_type, resolved_type))

        try:
            new_node = node_tree.nodes.new(type=resolved_type)
            if parent_frame:
                new_node.parent = parent_frame
        except Exception as e:
            print(f"[ERROR] Failed to create node {resolved_type}: {e}")
            if self.skip_unsupported:
                return None
            try:
                new_node = node_tree.nodes.new(type="NodeReroute")
                new_node.label = f"[MISSING] {original_type}"
                if parent_frame:
                    new_node.parent = parent_frame
                loc = node_info.get("location", [0, 0])
                new_node.location = (loc[0], loc[1])
                return new_node
            except:
                return None

        new_node.label = node_info.get("label", "")
        location = node_info.get("location", [0, 0])
        new_node.location = (location[0], location[1])

        if "dimensions" in node_info:
            dims = node_info["dimensions"]
            new_node.width = dims[0]
            new_node.height = dims[1]

        new_node.mute = node_info.get("mute", False)
        new_node.hide = node_info.get("hide", False)

        # Apply properties using RNAInspector
        properties = node_info.get("properties", {})
        if properties and "_special" not in properties:
            RNAInspector.apply_properties(new_node, properties)

        # Set input defaults (supports both list and dict formats)
        inputs_data = node_info.get("inputs", [])
        if isinstance(inputs_data, dict):
            inputs_data = inputs_data.values()
        for socket_data in inputs_data:
            if not socket_data.get("is_linked", False) and "default_value" in socket_data:
                socket = self._find_socket(new_node, socket_data, is_input=True)
                if socket:
                    set_socket_value_safe(socket, socket_data["default_value"])

        # Special handling
        special = node_info.get("special", {})

        if "color_ramp" in special:
            RNAInspector._apply_color_ramp(
                new_node, "color_ramp",
                {"value": special["color_ramp"]}
            )

        if "curve_mapping" in special:
            RNAInspector._apply_curve_mapping(
                new_node, "mapping",
                {"value": special["curve_mapping"]}
            )

        if "group" in special:
            self._setup_node_group(new_node, special["group"], node_tree)

        if "zone" in special:
            ZoneHandler.deserialize_zone(node_info, node_tree, self.uuid_map, new_node)

        if "capture_items" in special and hasattr(new_node, 'capture_items'):
            while new_node.capture_items:
                new_node.capture_items.remove(new_node.capture_items[0])
            _CAPTURE_SOCKET_MAP = {
                'FLOAT_VECTOR': 'VECTOR',
                'FLOAT_COLOR': 'RGBA',
                'FLOAT4X4': 'MATRIX',
                'QUATERNION': 'ROTATION',
            }
            for item_data in special["capture_items"]:
                try:
                    raw_type = item_data.get("data_type") or item_data.get("socket_type", 'FLOAT')
                    socket_type = _CAPTURE_SOCKET_MAP.get(raw_type, raw_type)
                    item = new_node.capture_items.new(
                        socket_type=socket_type,
                        name=item_data.get("name", "Attribute"),
                    )
                except Exception as e:
                    print(f"[WARN] Failed to restore capture item on {new_node.bl_idname}: {e}")

        # Restore output socket default values
        for socket_data in node_info.get("outputs", []):
            if "default_value" in socket_data:
                socket = self._find_socket(new_node, socket_data, is_input=False)
                if socket:
                    set_socket_value_safe(socket, socket_data["default_value"])

        return new_node

    def _find_socket(self, node: bpy.types.Node, socket_data: Dict[str, Any],
                     is_input: bool) -> Optional[bpy.types.NodeSocket]:
        sockets = node.inputs if is_input else node.outputs

        target_index = socket_data.get("index", -1)
        if 0 <= target_index < len(sockets):
            return sockets[target_index]

        target_id = socket_data.get("identifier", "")
        if target_id:
            for socket in sockets:
                if getattr(socket, 'identifier', '') == target_id:
                    return socket

        target_name = socket_data.get("name", "")
        if target_name:
            for socket in sockets:
                if socket.name == target_name:
                    return socket

        target_type = socket_data.get("type", "")
        if target_type:
            for socket in sockets:
                socket_type = socket.bl_idname if hasattr(socket, 'bl_idname') else socket.type
                if socket_type == target_type or map_socket_type(socket_type) == target_type:
                    return socket

        return None

    def _create_link(self, link_info: Dict[str, Any], node_tree: bpy.types.NodeTree) -> None:
        """Create a link with index-priority socket matching."""
        from_uuid = link_info.get("from_uuid") or link_info.get("from", "").split(".")[0]
        to_uuid = link_info.get("to_uuid") or link_info.get("to", "").split(".")[0]

        from_node = self.uuid_map.get(from_uuid)
        to_node = self.uuid_map.get(to_uuid)

        if not from_node or not to_node:
            return

        from_socket_data = {
            "identifier": link_info.get("from_socket_id", ""),
            "name": link_info.get("from_socket_name", ""),
            "index": link_info.get("from_socket_index", -1),
        }
        to_socket_data = {
            "identifier": link_info.get("to_socket_id", ""),
            "name": link_info.get("to_socket_name", ""),
            "index": link_info.get("to_socket_index", -1),
        }

        from_socket = self._find_socket(from_node, from_socket_data, is_input=False)
        to_socket = self._find_socket(to_node, to_socket_data, is_input=True)

        if not from_socket and from_node.bl_idname == "NodeReroute" and from_node.label.startswith("[MISSING]"):
            if from_node.outputs:
                from_socket = from_node.outputs[0]
        if not to_socket and to_node.bl_idname == "NodeReroute" and to_node.label.startswith("[MISSING]"):
            if to_node.inputs:
                to_socket = to_node.inputs[0]

        if from_socket and to_socket:
            try:
                node_tree.links.new(from_socket, to_socket)
                print(f"[DEBUG_LINK] OK {from_node.name}.{from_socket.name} -> {to_node.name}.{to_socket.name}")
            except Exception as e:
                print(f"[ERROR] Failed to create link: {e}")
        else:
            if not from_socket:
                print(f"[WARN] Could not find output socket {from_socket_data} on {from_node.bl_idname} (node={from_node.name})")
                print(f"[WARN]   Available outputs on {from_node.name}:")
                for i, s in enumerate(from_node.outputs):
                    print(f"[WARN]     [{i}] id={s.identifier} name={s.name} type={s.bl_idname}")
            if not to_socket:
                print(f"[WARN] Could not find input socket {to_socket_data} on {to_node.bl_idname} (node={to_node.name})")
                print(f"[WARN]   Available inputs on {to_node.name}:")
                for i, s in enumerate(to_node.inputs):
                    print(f"[WARN]     [{i}] id={s.identifier} name={s.name} type={s.bl_idname}")

    def _setup_interface(self, interface_data: Dict[str, Any], node_tree: bpy.types.NodeTree) -> None:
        """Setup node group interface with index-aware ordering."""

        if hasattr(node_tree, 'interface'):
            if hasattr(node_tree.interface, 'clear'):
                try:
                    node_tree.interface.clear()
                except:
                    pass

            inputs_sorted = sorted(
                interface_data.get("inputs", []),
                key=lambda x: x.get("index", 9999)
            )
            outputs_sorted = sorted(
                interface_data.get("outputs", []),
                key=lambda x: x.get("index", 9999)
            )

            for inp in inputs_sorted:
                socket_type = inp.get("type", "NodeSocketFloat")
                base_type = map_socket_type(socket_type)
                try:
                    item = node_tree.interface.new_socket(
                        name=inp.get("name", "Input"),
                        in_out='INPUT',
                        socket_type=base_type,
                    )

                    if "default_value" in inp:
                        set_socket_value_safe(item, inp["default_value"])
                    if "min_value" in inp and hasattr(item, 'min_value'):
                        item.min_value = inp["min_value"]
                    if "max_value" in inp and hasattr(item, 'max_value'):
                        item.max_value = inp["max_value"]
                    if "description" in inp and hasattr(item, 'description'):
                        item.description = inp["description"]
                    if "subtype" in inp and hasattr(item, 'subtype'):
                        item.subtype = inp["subtype"]
                    if "hide_value" in inp and hasattr(item, 'hide_value'):
                        item.hide_value = inp["hide_value"]
                    if "hide_in_modifier" in inp and hasattr(item, 'hide_in_modifier'):
                        item.hide_in_modifier = inp["hide_in_modifier"]
                    if "force_non_field" in inp and hasattr(item, 'force_non_field'):
                        item.force_non_field = inp["force_non_field"]
                    if "default_attribute_name" in inp and hasattr(item, 'default_attribute_name'):
                        item.default_attribute_name = inp["default_attribute_name"]

                except Exception as e:
                    print(f"[ERROR] Failed to create input socket: {e}")

            for out in outputs_sorted:
                socket_type = out.get("type", "NodeSocketFloat")
                base_type = map_socket_type(socket_type)
                try:
                    item = node_tree.interface.new_socket(
                        name=out.get("name", "Output"),
                        in_out='OUTPUT',
                        socket_type=base_type,
                    )

                    if "description" in out and hasattr(item, 'description'):
                        item.description = out["description"]
                    if "subtype" in out and hasattr(item, 'subtype'):
                        item.subtype = out["subtype"]

                except Exception as e:
                    print(f"[ERROR] Failed to create output socket: {e}")

        elif hasattr(node_tree, 'inputs') and hasattr(node_tree, 'outputs'):
            for inp in interface_data.get("inputs", []):
                socket_type = map_socket_type(inp.get("type", "NodeSocketFloat"))
                try:
                    new_input = node_tree.inputs.new(socket_type, inp.get("name", "Input"))
                    if "default_value" in inp:
                        set_socket_value_safe(new_input, inp["default_value"])
                except Exception as e:
                    print(f"[ERROR] Failed to create input: {e}")

            for out in interface_data.get("outputs", []):
                socket_type = map_socket_type(out.get("type", "NodeSocketFloat"))
                try:
                    node_tree.outputs.new(socket_type, out.get("name", "Output"))
                except Exception as e:
                    print(f"[ERROR] Failed to create output: {e}")

    def _setup_node_group(self, node: bpy.types.Node, group_info: Dict[str, Any],
                          parent_tree: bpy.types.NodeTree) -> None:
        """Setup node group reference."""
        group_id = group_info.get("group_id", "")
        group_name = group_info.get("group_name", group_id)

        def _apply_inputs(target_node):
            inputs_data = group_info.get("inputs", [])
            if isinstance(inputs_data, dict):
                for input_name, value in inputs_data.items():
                    if input_name in target_node.inputs:
                        set_socket_value_safe(target_node.inputs[input_name], value)
            else:
                for item in inputs_data:
                    input_name = item.get("name", "")
                    value = item.get("value")
                    if input_name in target_node.inputs and value is not None:
                        set_socket_value_safe(target_node.inputs[input_name], value)

        if group_id in self.group_cache:
            node.node_tree = self.group_cache[group_id]
        else:
            if group_name in bpy.data.node_groups:
                existing = bpy.data.node_groups[group_name]
                if existing.bl_idname == parent_tree.bl_idname:
                    node.node_tree = existing
                    self.group_cache[group_id] = existing
                    _apply_inputs(node)
                    return

            if self._pattern_dir and self._base_name:
                from ..utils.file_utils import sanitize_filename
                group_safe_name = sanitize_filename(group_name)
                group_filename = f"{self._base_name}_group_{group_safe_name}.json"
                group_filepath = self._pattern_dir / group_filename

                if group_filepath.exists():
                    import json
                    try:
                        with open(group_filepath, 'r', encoding='utf-8') as f:
                            group_data = json.load(f)
                        new_group = bpy.data.node_groups.new(group_name, parent_tree.bl_idname)
                        sub_deserializer = PatternDeserializer()
                        sub_deserializer.deserialize(group_data, new_group, self._pattern_dir, self._base_name)
                        node.node_tree = new_group
                        self.group_cache[group_id] = new_group
                        _apply_inputs(node)
                        return
                    except Exception as e:
                        print(f"[ERROR] Failed to load node group from file: {e}")

        _apply_inputs(node)