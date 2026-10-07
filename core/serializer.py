# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""Core serialization engine for node patterns."""
import uuid
import bpy
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..compat.blender_compat import get_socket_value_safe, map_socket_type, get_socket_index, f32_short
from ..utils.file_utils import get_addon_preferences
from .topology import NodeTopology
from .properties_db import NodePropertiesDB
from .zone_handler import ZoneHandler
from ..utils import logger


class PatternSerializer:
    """Industrial-grade node pattern serializer."""

    def __init__(self):
        self.group_cache: Dict[str, Dict] = {}
        self.group_file_map: Dict[str, Dict] = {}

    def serialize(self, nodes: List[bpy.types.Node], node_tree: bpy.types.NodeTree,
                  meta: Dict[str, Any] = None) -> Dict[str, Any]:
        """Serialize selected nodes to pattern format v2.0."""

        if not nodes:
            return None

        # 1. Generate stable UUIDs for each node
        node_uuids = {}
        used_uuids = set()
        for node in nodes:
            existing_uuid = node.get("_aurora_uuid", None)
            if existing_uuid and existing_uuid in used_uuids:
                existing_uuid = str(uuid.uuid4())
                node["_aurora_uuid"] = existing_uuid
            elif not existing_uuid:
                existing_uuid = str(uuid.uuid4())
                node["_aurora_uuid"] = existing_uuid
            used_uuids.add(existing_uuid)
            node_uuids[node] = existing_uuid

        # 2. Collect links (only within selected set)
        selected_set = set(nodes)
        links_data = []

        for link in node_tree.links:
            if link.from_node in selected_set and link.to_node in selected_set:
                links_data.append({
                    "from_uuid": node_uuids[link.from_node],
                    "from_socket_id": link.from_socket.identifier,
                    "from_socket_name": link.from_socket.name,
                    "from_socket_index": get_socket_index(link.from_socket, is_input=False),
                    "to_uuid": node_uuids[link.to_node],
                    "to_socket_id": link.to_socket.identifier,
                    "to_socket_name": link.to_socket.name,
                    "to_socket_index": get_socket_index(link.to_socket, is_input=True),
                })

        # 3. Topological sort
        temp_nodes = [{"uuid": node_uuids[n], "bl_idname": n.bl_idname} for n in nodes]
        sorted_nodes = NodeTopology.sort(temp_nodes, links_data)

        # Map back to actual nodes
        uuid_to_node = {node_uuids[n]: n for n in nodes}
        sorted_actual = [uuid_to_node[n["uuid"]] for n in sorted_nodes if n["uuid"] in uuid_to_node]

        # 4. Serialize each node
        only_modified = meta.get("only_modified", False) if meta else False
        nodes_data = []
        for node in sorted_actual:
            node_data = self._serialize_node(node, node_uuids, only_modified=only_modified)
            nodes_data.append(node_data)

        # 5. Serialize interface (for node groups)
        interface_data = self._serialize_interface(node_tree)

        # 6. Build result
        result = {
            "format_version": "2.0.0",
            "meta": {
                "name": meta.get("name", "") if meta else "",
                "description": meta.get("description", "") if meta else "",
                "author": meta.get("author", "") if meta else "",
                "version": meta.get("version", "1.0.0") if meta else "1.0.0",
                "created": datetime.now().isoformat(),
                "blender_version": list(bpy.app.version),
                "node_tree_type": node_tree.bl_idname,
                "is_subgroup": meta.get("is_subgroup", False) if meta else False,
                "tags": meta.get("tags", []) if meta else [],
                "locale": meta.get("locale", "") if meta else "",
                "platform": bpy.app.build_platform,
            },
            "nodes": nodes_data,
            "links": links_data,
            "interface": interface_data,
        }

        return result

    def _serialize_node(self, node: bpy.types.Node, node_uuids: Dict[bpy.types.Node, str],
                     only_modified: bool = False) -> Dict[str, Any]:
        """Serialize a single node."""
        data = {
            "uuid": node_uuids[node],
            "bl_idname": node.bl_idname,
            "label": node.label,
            "location": [round(node.location.x, 4), round(node.location.y, 4)],
            "dimensions": [round(node.width, 2), round(node.height, 2)],
            "mute": node.mute,
            "hide": node.hide,
        }

        # Properties
        data["properties"] = NodePropertiesDB.discover_properties(node, only_modified=only_modified)

        # Input sockets (only unlinked with default values)
        data["inputs"] = []
        for i, socket in enumerate(node.inputs):
            socket_data = {
                "identifier": socket.identifier,
                "type": socket.bl_idname if hasattr(socket, 'bl_idname') else map_socket_type(socket.type),
                "is_linked": socket.is_linked,
                "name": socket.name,
                "index": i,
            }

            if not socket.is_linked and hasattr(socket, 'default_value'):
                try:
                    val = get_socket_value_safe(socket)
                    if val is not None:
                        socket_data["default_value"] = val
                except Exception as e:
                    logger.warning(f"Failed to read socket default: {e}")

            data["inputs"].append(socket_data)

        # Output sockets
        data["outputs"] = []
        for i, socket in enumerate(node.outputs):
            socket_data = {
                "identifier": socket.identifier,
                "type": socket.bl_idname if hasattr(socket, 'bl_idname') else map_socket_type(socket.type),
                "name": socket.name,
                "index": i,
            }
            if hasattr(socket, 'default_value'):
                try:
                    val = get_socket_value_safe(socket)
                    if val is not None:
                        socket_data["default_value"] = val
                except Exception as e:
                    logger.warning(f"Failed to read output socket default: {e}")
            data["outputs"].append(socket_data)

        # Special handling
        special = {}

        # Color Ramp
        if node.bl_idname == "ShaderNodeValToRGB":
            special["color_ramp"] = self._serialize_color_ramp(node)

        # Curve nodes (RGB curves, Vector curves)
        if node.bl_idname in ("ShaderNodeRGBCurve", "ShaderNodeVectorCurve", "CompositorNodeHueCorrect", "CompositorNodeCurveRGB", "ShaderNodeFloatCurve", "GeometryNodeRGBCurve"):
            special["curve_mapping"] = self._serialize_curve_mapping(node)

        # Zone nodes
        if ZoneHandler.is_zone_node(node.bl_idname):
            special["zone"] = ZoneHandler.serialize_zone(node, node.id_data)

        # Node groups
        if node.bl_idname in ("ShaderNodeGroup", "GeometryNodeGroup", "CompositorNodeGroup"):
            if node.node_tree:
                special["group"] = self._serialize_node_group(node, node_uuids)

        # Image/Texture references
        if hasattr(node, 'image') and node.image:
            special["image"] = node.image.name

        if hasattr(node, 'material') and node.material:
            special["material"] = node.material.name

        # Local file references (images, clips, scripts, IES, etc.)
        prefs = get_addon_preferences()
        if getattr(prefs, 'store_absolute_paths', False):
            file_paths = self._collect_file_paths(node)
            if file_paths:
                special["file_paths"] = file_paths

        # Capture Attribute items (Blender 5.x multi-attribute capture)
        if node.bl_idname == "GeometryNodeCaptureAttribute" and hasattr(node, 'capture_items'):
            capture_items_data = []
            for item in node.capture_items:
                capture_items_data.append({
                    "name": item.name,
                    "socket_type": getattr(item, 'socket_type', 'FLOAT'),
                    "data_type": getattr(item, 'data_type', 'FLOAT'),
                })
            if capture_items_data:
                special["capture_items"] = capture_items_data

        # Frame parent reference
        if node.parent and node.parent.bl_idname == 'NodeFrame':
            data["parent_frame"] = node_uuids.get(node.parent)
            data["location_relative"] = [
                round(node.location.x - node.parent.location.x, 4),
                round(node.location.y - node.parent.location.y, 4)
            ]

        if special:
            data["special"] = special

        return data

    # Node block attributes that hold ID datablocks with a '.filepath'.
    _ID_ATTR_FILEPATH = ('image', 'clip', 'sound', 'texture', 'script', 'ies')

    def _collect_file_paths(self, node) -> Dict[str, Any]:
        """Collect absolute paths of files referenced by a node."""
        import os
        paths = {}

        # ID datablocks referenced by a dedicated attribute (e.g. node.image).
        for attr in self._ID_ATTR_FILEPATH:
            try:
                obj = getattr(node, attr, None)
                if obj is None or not hasattr(obj, 'filepath'):
                    continue
                fp = obj.filepath
                if not fp:
                    continue
                abs_path = bpy.path.abspath(fp)
                if abs_path:
                    paths[attr] = abs_path
            except Exception as e:
                logger.warning(f"Failed to read {node.bl_idname}.{attr}: {e}")

        # Script / IES nodes in 'external' mode keep their path in node.filepath.
        try:
            if hasattr(node, 'filepath'):
                fp = node.filepath
                if fp:
                    abs_path = bpy.path.abspath(fp)
                    if abs_path and os.path.exists(abs_path):
                        paths.setdefault("filepath", abs_path)
        except Exception as e:
            logger.warning(f"Failed to read {node.bl_idname}.filepath: {e}")

        return paths

    def _serialize_color_ramp(self, node) -> Dict[str, Any]:
        """Serialize color ramp data."""
        ramp = node.color_ramp
        return {
            "interpolation": ramp.interpolation,
            "elements": [
                {
                    "position": round(elem.position, 6),
                    "color": [round(c, 6) for c in elem.color]
                }
                for elem in ramp.elements
            ]
        }

    def _serialize_curve_mapping(self, node) -> Dict[str, Any]:
        """Serialize curve mapping data."""
        curve_map = node.mapping
        curves_data = []

        for curve in curve_map.curves:
            points = []
            for point in curve.points:
                points.append({
                    "location": [round(point.location.x, 6), round(point.location.y, 6)],
                    "handle_type": point.handle_type,
                })
            curves_data.append({
                "points": points,
            })

        return {
            "curves": curves_data,
            "black_level": [round(v, 6) for v in curve_map.black_level],
            "white_level": [round(v, 6) for v in curve_map.white_level],
            "clip_min_x": round(curve_map.clip_min_x, 6),
            "clip_min_y": round(curve_map.clip_min_y, 6),
            "clip_max_x": round(curve_map.clip_max_x, 6),
            "clip_max_y": round(curve_map.clip_max_y, 6),
            "use_clip": curve_map.use_clip,
        }

    def _serialize_node_group(self, node: bpy.types.Node, parent_uuids: Dict) -> Dict[str, Any]:
        """Serialize node group reference and internal structure."""
        group_tree = node.node_tree
        group_id = group_tree.name

        # Cache check
        if group_id not in self.group_cache:
            # Recursively serialize internal nodes
            internal_nodes = list(group_tree.nodes)
            group_data = self.serialize(
                internal_nodes,
                group_tree,
                meta={
                    "name": group_tree.name,
                    "is_subgroup": True,
                    "version": "1.0.0",
                }
            )
            self.group_cache[group_id] = group_data
            self.group_file_map[group_id] = group_data

        # Collect input values
        inputs_data = []
        for socket in node.inputs:
            if hasattr(socket, 'default_value') and not socket.is_linked:
                try:
                    val = get_socket_value_safe(socket)
                    if val is not None:
                        inputs_data.append({
                            "name": socket.name,
                            "identifier": socket.identifier,
                            "value": val,
                        })
                except:
                    pass

        return {
            "group_id": group_id,
            "group_name": group_tree.name,
            "inputs": inputs_data,
        }

    def _serialize_interface(self, node_tree: bpy.types.NodeTree) -> Dict[str, Any]:
        """Serialize node group interface definition."""
        interface = {"inputs": [], "outputs": []}

        # Blender 4.x API - interface.items_tree
        if hasattr(node_tree, 'interface') and hasattr(node_tree.interface, 'items_tree'):
            for item in node_tree.interface.items_tree:
                # Skip non-socket items (panels, etc.)
                if getattr(item, 'item_type', '') != 'SOCKET':
                    continue

                socket_info = {
                    "name": item.name,
                    "identifier": item.identifier,
                    "in_out": item.in_out,
                }

                # 4.x API: socket_type is the base type, bl_socket_idname is the actual type including subtype
                if hasattr(item, 'bl_socket_idname') and item.bl_socket_idname:
                    socket_info["type"] = item.bl_socket_idname
                elif hasattr(item, 'socket_type') and item.socket_type:
                    socket_info["type"] = item.socket_type
                else:
                    socket_info["type"] = "NodeSocketFloat"

                # Extended metadata
                if hasattr(item, 'subtype') and item.subtype:
                    socket_info["subtype"] = item.subtype

                if hasattr(item, 'default_value') and item.bl_socket_idname != 'NodeSocketShader':
                    try:
                        val = get_socket_value_safe(item)
                        if val is not None:
                            socket_info["default_value"] = val
                    except:
                        pass

                if hasattr(item, 'min_value'):
                    socket_info["min_value"] = f32_short(item.min_value)
                if hasattr(item, 'max_value'):
                    socket_info["max_value"] = f32_short(item.max_value)
                if hasattr(item, 'description') and item.description:
                    socket_info["description"] = item.description
                if hasattr(item, 'hide_value'):
                    socket_info["hide_value"] = item.hide_value
                if hasattr(item, 'hide_in_modifier'):
                    socket_info["hide_in_modifier"] = item.hide_in_modifier
                if hasattr(item, 'force_non_field'):
                    socket_info["force_non_field"] = item.force_non_field
                if hasattr(item, 'default_attribute_name') and item.default_attribute_name:
                    socket_info["default_attribute_name"] = item.default_attribute_name

                if item.in_out == 'INPUT':
                    interface["inputs"].append(socket_info)
                else:
                    interface["outputs"].append(socket_info)

        # Blender 3.x API - node_tree.inputs / node_tree.outputs
        elif hasattr(node_tree, 'inputs') and hasattr(node_tree, 'outputs'):
            for inp in node_tree.inputs:
                socket_info = {
                    "name": inp.name,
                    "identifier": getattr(inp, 'identifier', inp.name),
                    "type": inp.bl_idname if hasattr(inp, 'bl_idname') else map_socket_type(inp.type),
                }
                if hasattr(inp, 'default_value'):
                    try:
                        val = get_socket_value_safe(inp)
                        if val is not None:
                            socket_info["default_value"] = val
                    except:
                        pass
                interface["inputs"].append(socket_info)

            for out in node_tree.outputs:
                interface["outputs"].append({
                    "name": out.name,
                    "identifier": getattr(out, 'identifier', out.name),
                    "type": out.bl_idname if hasattr(out, 'bl_idname') else map_socket_type(out.type),
                })

        return interface

    def get_group_data(self) -> Dict[str, Dict]:
        """Get all serialized group data for external file saving."""
        return self.group_file_map.copy()
