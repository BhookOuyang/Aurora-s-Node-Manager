"""Special handling for Zone nodes (Simulation, Repeat, Bake)."""
import bpy
from typing import Dict, Any, List, Optional


class ZoneHandler:
    """Handle Blender 4.x+ Zone nodes."""

    ZONE_TYPES = {
        "GeometryNodeSimulationZone": {
            "input_type": "GeometryNodeSimulationInput",
            "output_type": "GeometryNodeSimulationOutput",
            "has_internal_tree": True,
        },
        "GeometryNodeRepeatZone": {
            "input_type": "GeometryNodeRepeatInput",
            "output_type": "GeometryNodeRepeatOutput",
            "has_internal_tree": True,
        },
        "GeometryNodeBake": {
            "has_internal_tree": False,
            "has_external_ref": True,
        },
    }

    ZONE_INPUT_TYPES = {"GeometryNodeSimulationInput", "GeometryNodeRepeatInput"}
    ZONE_OUTPUT_TYPES = {"GeometryNodeSimulationOutput", "GeometryNodeRepeatOutput"}

    @classmethod
    def is_zone_node(cls, bl_idname: str) -> bool:
        return bl_idname in cls.ZONE_TYPES

    @classmethod
    def serialize_zone(cls, node: bpy.types.Node, node_tree: bpy.types.NodeTree) -> Dict[str, Any]:
        zone_info = {
            "zone_type": node.bl_idname,
            "has_internal_tree": cls.ZONE_TYPES.get(node.bl_idname, {}).get("has_internal_tree", False),
        }

        if hasattr(node, 'zone') and node.zone:
            internal_tree = node.zone
            internal_nodes = list(internal_tree.nodes)
            if internal_nodes:
                from ..core.serializer import PatternSerializer
                ser = PatternSerializer()
                internal_data = ser.serialize(
                    internal_nodes, internal_tree,
                    {"name": internal_tree.name, "is_subgroup": True}
                )
                if internal_data:
                    zone_info["internal_data"] = internal_data

        if hasattr(node, 'simulation_state_items'):
            items = []
            for item in node.simulation_state_items:
                items.append({
                    "name": item.name,
                    "socket_type": getattr(item, 'socket_type', 'GEOMETRY'),
                    "data_type": getattr(item, 'data_type', 'GEOMETRY'),
                })
            if items:
                zone_info["state_items"] = items

        if node.bl_idname == "GeometryNodeBake":
            if hasattr(node, 'bake_items'):
                zone_info["bake_items"] = []
                for item in node.bake_items:
                    zone_info["bake_items"].append({
                        "name": item.name,
                        "socket_type": getattr(item, 'socket_type', ''),
                    })

        return zone_info

    @classmethod
    def deserialize_zone(cls, node_info: Dict[str, Any], node_tree: bpy.types.NodeTree,
                         uuid_map: Dict[str, bpy.types.Node],
                         zone_node: bpy.types.Node = None) -> Optional[bpy.types.Node]:
        bl_idname = node_info.get("bl_idname", "")

        if not cls.is_zone_node(bl_idname):
            return None

        new_node = zone_node
        if new_node is None:
            try:
                new_node = node_tree.nodes.new(type=bl_idname)
            except Exception as e:
                print(f"[ERROR] Failed to create zone node {bl_idname}: {e}")
                return None

        zone_data = node_info.get("special", {}).get("zone", {})
        internal_data = zone_data.get("internal_data")
        if not internal_data:
            return new_node

        internal_tree = getattr(new_node, 'zone', None)
        if not internal_tree:
            return new_node

        state_items_data = zone_data.get("state_items", [])
        if state_items_data and hasattr(new_node, 'simulation_state_items'):
            while new_node.simulation_state_items:
                new_node.simulation_state_items.remove(new_node.simulation_state_items[0])
            for item_data in state_items_data:
                try:
                    new_node.simulation_state_items.new(
                        socket_type=item_data.get("socket_type", 'GEOMETRY'),
                        name=item_data.get("name", "Item"),
                    )
                except Exception as e:
                    print(f"[WARN] Failed to restore state item: {e}")

        for n in list(internal_tree.nodes):
            internal_tree.nodes.remove(n)

        from ..core.deserializer import PatternDeserializer
        sub = PatternDeserializer()

        filtered_meta = dict(internal_data.get("meta", {}))
        filtered_meta["is_subgroup"] = False
        filtered_data = dict(internal_data)
        filtered_data["meta"] = filtered_meta

        sub.deserialize(filtered_data, internal_tree)

        return new_node
