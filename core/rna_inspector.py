"""RNA-based property discovery and serialization engine."""
import bpy
import mathutils
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import OrderedDict

class RNAInspector:
    """Industrial-grade RNA property inspector with dependency-aware ordering."""
    
    # Fixed blacklist: Blender core internal properties (~30 items), stable across versions
    BLACKLIST: Set[str] = {
        'bl_idname', 'type', 'name', 'label', 'location', 'dimensions',
        'width', 'height', 'width_hidden', 'height_hidden',
        'inputs', 'outputs', 'internal_links', 'is_active_output',
        'select', 'show_options', 'show_preview', 'show_texture',
        'color', 'use_custom_color', 'parent', 'id_data', 'rna_type',
        'is_registered_node_type', '__doc__', '__module__', '__slots__',
        'is_missing', 'shader_compatibility', 'active_output',
        'is_active', 'use_auto_update', 'update', 'draw_buttons',
        'draw_buttons_ext', 'copy', 'free', 'poll', 'poll_instance',
        '_aurora_uuid', 'bl_rna', 'bl_icon', 'bl_label', 'bl_description',
        'bl_width_default', 'bl_width_min', 'bl_height_default',
        'location_absolute',
    }
    
    # Fields handled separately (avoid duplicate serialization)
    SEPARATELY_HANDLED = {'location', 'inputs', 'outputs', 'mute', 'hide', 'label'}
    
    # Special POINTER type handler map: bl_idname -> {prop_id -> handler_name}
    SPECIAL_POINTERS = {
        'ShaderNodeValToRGB': {'color_ramp': 'color_ramp'},
        'ShaderNodeRGBCurve': {'mapping': 'curve_mapping'},
        'ShaderNodeVectorCurve': {'mapping': 'curve_mapping'},
        'CompositorNodeHueCorrect': {'mapping': 'curve_mapping'},
        'CompositorNodeCurveRGB': {'mapping': 'curve_mapping'},
        'ShaderNodeFloatCurve': {'mapping': 'curve_mapping'},
        'GeometryNodeColorRamp': {'color_ramp': 'color_ramp'},
        'GeometryNodeRGBCurve': {'mapping': 'curve_mapping'},
        'GeometryNodeFloatCurve': {'mapping': 'curve_mapping'},
        'GeometryNodeBake': {'bake_items': 'bake_items'},
        'GeometryNodeSimulationZone': {'zone': 'zone_internal'},
        'GeometryNodeRepeatZone': {'zone': 'zone_internal'},
    }
    
    # Property load priority (dependency resolution)
    # Key: node bl_idname, Value: list of property names, loaded in this order
    LOAD_PRIORITY: Dict[str, List[str]] = {
        'ShaderNodeMix': ['data_type', 'blend_type', 'clamp_factor', 'clamp_result', 'factor_mode'],
        'GeometryNodeSwitch': ['input_type'],
        'GeometryNodeStoreNamedAttribute': ['data_type', 'domain'],
        'GeometryNodeCaptureAttribute': ['data_type', 'domain'],
        'GeometryNodeSampleIndex': ['data_type', 'domain', 'clamp'],
        'GeometryNodeFieldAtIndex': ['data_type', 'domain'],
        'GeometryNodeFieldOnDomain': ['data_type', 'domain'],
        'GeometryNodeAccumulateField': ['data_type', 'domain'],
        'GeometryNodeInterpolateDomain': ['data_type', 'domain'],
        'GeometryNodeBlurAttribute': ['data_type'],
        'GeometryNodeRandomValue': ['data_type'],
        'GeometryNodeCompare': ['data_type', 'mode', 'operation'],
        'GeometryNodeMapRange': ['data_type', 'clamp', 'interpolation_type'],
        'GeometryNodeSeparateColor': ['mode'],
        'GeometryNodeCombineColor': ['mode'],
        'GeometryNodeMeshToPoints': ['mode'],
        'GeometryNodeCurveToPoints': ['mode'],
        'GeometryNodePointsToVolume': ['resolution_mode'],
        'GeometryNodeVolumeToMesh': ['resolution_mode'],
        'GeometryNodeDistributePointsOnFaces': ['distribute_method'],
        'GeometryNodeDistributePointsInVolume': ['mode'],
        'GeometryNodeStringToCurves': ['overflow', 'align_x', 'align_y', 'pivot_mode'],
        'GeometryNodeValueToString': ['data_type'],
        'GeometryNodeMeshLine': ['mode'],
        'GeometryNodeCurveCircle': ['mode'],
        'GeometryNodeCurveLine': ['mode'],
        'GeometryNodeCurveArc': ['mode'],
        'GeometryNodeCurveSetHandles': ['handle_type'],
        'GeometryNodeFloatToInt': ['rounding_mode'],
        'GeometryNodeDomainSize': ['component'],
        'GeometryNodeDeleteGeometry': ['domain', 'mode'],
        'GeometryNodeSeparateGeometry': ['domain'],
        'GeometryNodeDuplicateElements': ['domain'],
        'GeometryNodeInstanceOnPoints': ['rotation_space'],
        'GeometryNodeSetNormal': ['domain'],
        'GeometryNodeMeshCircle': ['fill_type'],
        'GeometryNodeMeshCylinder': ['fill_type'],
        'GeometryNodeMeshCone': ['fill_type'],
        'GeometryNodeTexNoise': ['noise_dimensions', 'noise_type'],
        'GeometryNodeTexVoronoi': ['voronoi_dimensions', 'feature', 'distance'],
        'GeometryNodeTexWave': ['wave_type', 'wave_profile', 'bands_direction', 'rings_direction'],
        'GeometryNodeTexMusgrave': ['musgrave_dimensions', 'musgrave_type'],
        'GeometryNodeTexMagic': ['turbulence_depth'],
        'GeometryNodeTexBrick': ['offset', 'offset_frequency', 'squash', 'squash_frequency'],
        'GeometryNodeTexGradient': ['gradient_type'],
        'GeometryNodeTexWhiteNoise': ['noise_dimensions'],
        'GeometryNodeTexSky': ['sky_type'],
        'GeometryNodeClamp': ['clamp_type'],
        'GeometryNodeImageTexture': ['interpolation', 'extension'],
        'GeometryNodeNormalMap': ['space', 'uv_map'],
        'GeometryNodeTangent': ['direction_type', 'axis'],
        'GeometryNodeMapping': ['vector_type'],
        'GeometryNodeUVMap': ['from_instancer', 'uv_map'],
        'GeometryNodeVertexColor': ['layer_name'],
        'GeometryNodeWireframe': ['use_pixel_size'],
        'GeometryNodeBevel': ['samples'],
        'GeometryNodeDisplacement': ['space'],
        'GeometryNodeVectorDisplacement': ['space'],
        'GeometryNodeOutputMaterial': ['target'],
        'GeometryNodeScript': ['mode', 'script', 'filepath', 'use_auto_update'],
        'GeometryNodeLightFalloff': ['falloff_type'],
        'GeometryNodeAmbientOcclusion': ['samples', 'inside', 'only_local'],
        'GeometryNodeSubsurfaceScattering': ['falloff'],
        'GeometryNodeBsdfPrincipled': ['distribution', 'subsurface_method'],
        'GeometryNodeTonemap': ['tonemap_type'],
        'GeometryNodeLensdist': ['use_projector', 'use_jitter', 'use_fit'],
        'GeometryNodeGlare': ['glare_type', 'quality'],
        'GeometryNodeDefocus': ['use_zbuffer', 'f_stop', 'blur_max', 'threshold', 'use_preview'],
        'GeometryNodeDilateErode': ['mode'],
        'GeometryNodeFilter': ['filter_type'],
        'GeometryNodeBlur': ['filter_type', 'use_variable_size', 'use_extended_bounds'],
        'GeometryNodeMask': ['use_feather', 'use_motion_blur', 'motion_blur_samples'],
        'GeometryNodeKeying': ['blur_pre', 'blur_post', 'dilate', 'edge_kernel_radius', 
                               'edge_kernel_tolerance', 'clip_black', 'clip_white'],
        'GeometryNodeChannelMatte': ['color_space', 'matte_channel'],
        'GeometryNodeDistanceMatte': ['channel'],
        'GeometryNodeColorSpill': ['channel', 'limit_method', 'limit_channel'],
        'GeometryNodeTrackPos': ['position', 'frame_relative'],
        'GeometryNodeTransform': ['filter_type'],
        'GeometryNodeCombineColor': ['mode'],
        'GeometryNodeSeparateColor': ['mode'],
        'GeometryNodeSetAlpha': ['mode'],
        'GeometryNodeScale': ['space'],
        'GeometryNodeFlip': ['axis'],
        'GeometryNodeCrop': ['use_crop_size'],
        'GeometryNodeStabilize2D': ['filter_type'],
        'GeometryNodeMovieDistortion': ['distortion_type'],
        'GeometryNodeCryptomatte': ['matte_id'],
        'GeometryNodeCryptomatteV2': ['matte_id'],
        'GeometryNodeOutputFile': ['base_path'],
        'GeometryNodeRLayers': ['scene', 'layer'],
        'GeometryNodeImage': ['image'],
        'GeometryNodeTexture': ['texture'],
        'GeometryNodeMath': ['operation', 'use_clamp'],
        'GeometryNodeVectorMath': ['operation'],
        'GeometryNodeMix': ['blend_type', 'clamp_factor', 'clamp_result', 'data_type', 'factor_mode'],
        'GeometryNodeClamp': ['clamp_type'],
        'GeometryNodeMapRange': ['clamp', 'data_type', 'interpolation_type'],
        'GeometryNodeNormalMap': ['space', 'uv_map'],
        'GeometryNodeTangent': ['direction_type', 'axis'],
        'GeometryNodeTexImage': ['projection', 'interpolation', 'extension'],
        'GeometryNodeTexEnvironment': ['projection', 'interpolation'],
        'GeometryNodeScript': ['mode', 'script', 'filepath', 'use_auto_update'],
        'GeometryNodeGroup': [],  # Empty list = no special priority, use RNA default order
    }
    
    @classmethod
    def discover_properties(cls, node: bpy.types.Node) -> OrderedDict:
        """
        Discover all serializable RNA properties for a node.
        Returns OrderedDict preserving dependency-aware order.
        """
        properties = OrderedDict()
        bl_idname = node.bl_idname
        
        # Get RNA properties
        if not hasattr(node, 'bl_rna') or not hasattr(node.bl_rna, 'properties'):
            return properties
            
        rna_props = node.bl_rna.properties
        
        # Build property info dict
        prop_infos = []
        for prop_id in rna_props.keys():
            if prop_id in cls.BLACKLIST or prop_id in cls.SEPARATELY_HANDLED:
                continue
                
            prop = rna_props[prop_id]
            if prop.is_readonly:
                continue
                
            prop_info = cls._inspect_property(node, prop_id, prop)
            if prop_info:
                prop_infos.append((prop_id, prop_info))
        
        # Sort by priority if defined for this node type
        priority_order = cls.LOAD_PRIORITY.get(bl_idname, [])
        if priority_order:
            # Create priority mapping
            priority_map = {name: idx for idx, name in enumerate(priority_order)}
            # Sort: prioritized first (by priority list order), then others by RNA order
            prop_infos.sort(key=lambda x: (priority_map.get(x[0], 9999), x[0]))
        
        for prop_id, prop_info in prop_infos:
            properties[prop_id] = prop_info
            
        return properties
    
    @classmethod
    def _inspect_property(cls, node: bpy.types.Node, prop_id: str, 
                          prop: bpy.types.Property) -> Optional[Dict[str, Any]]:
        """Inspect a single RNA property and return serializable info."""
        
        prop_type = prop.type  # 'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM', 'POINTER', 'COLLECTION'
        
        try:
            value = getattr(node, prop_id)
        except (AttributeError, RuntimeError) as e:
            print(f"[WARN] Cannot read {node.bl_idname}.{prop_id}: {e}")
            return None
        
        if value is None and prop_type != 'POINTER':
            return None
            
        # Handle COLLECTION: skip (inputs/outputs handled separately)
        if prop_type == 'COLLECTION':
            return None
            
        # Handle POINTER
        if prop_type == 'POINTER':
            return cls._serialize_pointer(node, prop_id, value)
            
        # Handle ENUM
        if prop_type == 'ENUM':
            return cls._serialize_enum(node, prop_id, value, prop)
            
        # Handle basic types
        if prop_type in ('BOOLEAN', 'INT', 'FLOAT', 'STRING'):
            return {
                "type": prop_type.lower(),
                "value": value,
            }
            
        # Handle arrays (FLOAT_ARRAY, INT_ARRAY, BOOL_ARRAY)
        if 'ARRAY' in prop_type:
            array_len = prop.array_length
            is_float = 'FLOAT' in prop_type
            subtype = getattr(prop, 'subtype', 'NONE')
            
            # Detect vector/color/rotation/matrix by subtype and length
            if subtype in ('COLOR', 'COLOR_GAMMA') and array_len == 4:
                return {"type": "color", "value": list(value), "subtype": subtype}
            elif subtype in ('COLOR', 'COLOR_GAMMA') and array_len == 3:
                return {"type": "vector", "value": list(value), "subtype": subtype}
            elif subtype in ('TRANSLATION', 'DIRECTION', 'VELOCITY', 'ACCELERATION', 
                           'XYZ', 'EULER', 'QUATERNION', 'AXISANGLE'):
                return {"type": "vector", "value": list(value), "subtype": subtype}
            elif subtype == 'MATRIX' and array_len == 16:
                return {"type": "matrix", "value": [list(value[i:i+4]) for i in range(0, 16, 4)]}
            elif subtype == 'MATRIX' and array_len == 9:
                return {"type": "matrix3x3", "value": [list(value[i:i+3]) for i in range(0, 9, 3)]}
            else:
                # Generic array
                return {
                    "type": "float_array" if is_float else "int_array",
                    "value": list(value),
                    "length": array_len,
                    "subtype": subtype,
                }
        
        # Safety net: convert mathutils types to plain Python
        if isinstance(value, (mathutils.Vector, mathutils.Color, mathutils.Euler, mathutils.Quaternion)):
            return {"type": "vector", "value": list(value)}
        if isinstance(value, mathutils.Matrix):
            return {"type": "matrix", "value": [list(row) for row in value]}

        # Unknown type - attempt generic serialization
        print(f"[WARN] Unknown property type {prop_type} for {node.bl_idname}.{prop_id}")
        try:
            return {"type": "unknown", "value": str(value)}
        except:
            return None
    
    @classmethod
    def _serialize_enum(cls, node: bpy.types.Node, prop_id: str, 
                        value: str, prop: bpy.types.EnumProperty) -> Dict[str, Any]:
        """Serialize enum with full option list for downgrade handling."""
        enum_items = []
        if hasattr(prop, 'enum_items'):
            enum_items = [item.identifier for item in prop.enum_items]
        
        return {
            "type": "enum",
            "value": value,
            "enum_items": enum_items,  # Full list for cross-version compatibility
            "enum_descriptions": {
                item.identifier: item.description 
                for item in getattr(prop, 'enum_items', [])
            } if hasattr(prop, 'enum_items') else {},
        }
    
    @classmethod
    def _serialize_pointer(cls, node: bpy.types.Node, prop_id: str,
                           value: Any) -> Optional[Dict[str, Any]]:
        """Serialize POINTER property."""
        if value is None:
            return None
            
        # Check if it's a Blender ID reference
        if isinstance(value, bpy.types.ID):
            id_type = value.__class__.__name__
            return {
                "type": "id_reference",
                "value": value.name,
                "id_type": id_type,
            }
        
        # Check special types
        special_handler = cls.SPECIAL_POINTERS.get(node.bl_idname, {}).get(prop_id)
        if special_handler == 'color_ramp' and hasattr(value, 'elements'):
            return {
                "type": "color_ramp",
                "value": cls._serialize_color_ramp(value),
            }
        elif special_handler == 'curve_mapping' and hasattr(value, 'curves'):
            return {
                "type": "curve_mapping", 
                "value": cls._serialize_curve_mapping(value),
            }
        elif special_handler == 'bake_items' and hasattr(value, '__iter__'):
            return {
                "type": "bake_items",
                "value": cls._serialize_bake_items(value),
            }
        elif special_handler == 'zone_internal':
            return {
                "type": "zone_internal",
                "value": cls._serialize_zone_internal(value),
            }
        
        # Try generic recursive serialization for unknown POINTER
        try:
            if hasattr(value, 'bl_rna') and hasattr(value.bl_rna, 'properties'):
                generic_props = {}
                for sub_prop_id in value.bl_rna.properties.keys():
                    if sub_prop_id.startswith('_'):
                        continue
                    sub_prop = value.bl_rna.properties[sub_prop_id]
                    if sub_prop.is_readonly:
                        continue
                    sub_info = cls._inspect_property(value, sub_prop_id, sub_prop)
                    if sub_info:
                        generic_props[sub_prop_id] = sub_info
                if generic_props:
                    return {
                        "type": "generic_pointer",
                        "value": generic_props,
                        "class_name": value.__class__.__name__,
                    }
        except Exception as e:
            print(f"[WARN] Generic pointer serialization failed for {node.bl_idname}.{prop_id}: {e}")
        
        return None
    
    @classmethod
    def _serialize_color_ramp(cls, ramp) -> Dict[str, Any]:
        """Serialize ColorRamp structure."""
        return {
            "interpolation": ramp.interpolation,
            "elements": [
                {
                    "position": round(elem.position, 6),
                    "color": [round(c, 6) for c in elem.color],
                }
                for elem in ramp.elements
            ],
            "color_mode": getattr(ramp, 'color_mode', 'RGB'),
        }
    
    @classmethod
    def _serialize_curve_mapping(cls, mapping) -> Dict[str, Any]:
        """Serialize CurveMapping structure."""
        curves_data = []
        for curve in mapping.curves:
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
            "black_level": [round(v, 6) for v in mapping.black_level],
            "white_level": [round(v, 6) for v in mapping.white_level],
            "clip_min_x": round(mapping.clip_min_x, 6),
            "clip_min_y": round(mapping.clip_min_y, 6),
            "clip_max_x": round(mapping.clip_max_x, 6),
            "clip_max_y": round(mapping.clip_max_y, 6),
            "use_clip": mapping.use_clip,
        }
    
    @classmethod
    def _serialize_bake_items(cls, items) -> List[Dict[str, Any]]:
        """Serialize BakeItems collection."""
        result = []
        for item in items:
            result.append({
                "name": item.name,
                "socket_type": getattr(item, 'socket_type', ''),
            })
        return result
    
    @classmethod
    def _serialize_zone_internal(cls, zone_tree) -> Dict[str, Any]:
        """Serialize zone internal node tree reference."""
        if zone_tree is None:
            return None
        return {
            "name": zone_tree.name,
            "type": zone_tree.bl_idname,
        }
    
    @classmethod
    def apply_properties(cls, node: bpy.types.Node, properties: Dict[str, Any]) -> None:
        """Apply serialized properties to node with dependency-aware ordering."""
        bl_idname = node.bl_idname
        
        # Get priority order
        priority_order = cls.LOAD_PRIORITY.get(bl_idname, [])
        priority_set = set(priority_order)
        
        # Sort properties: prioritized first, then alphabetical
        sorted_props = sorted(
            properties.items(),
            key=lambda x: (priority_order.index(x[0]) if x[0] in priority_set else 9999, x[0])
        )
        
        for prop_id, prop_info in sorted_props:
            cls._apply_single_property(node, prop_id, prop_info)
    
    @classmethod
    def _apply_single_property(cls, node: bpy.types.Node, prop_id: str,
                                prop_info: Dict[str, Any]) -> None:
        """Apply a single property with full error handling and downgrade support."""
        
        if not hasattr(node, prop_id):
            print(f"[WARN] Node {node.bl_idname} missing property: {prop_id}")
            return
            
        prop_type = prop_info.get("type", "string")
        value = prop_info.get("value")
        
        if value is None and prop_type != "id_reference":
            return
        
        try:
            if prop_type == "id_reference":
                cls._apply_id_reference(node, prop_id, prop_info)
            elif prop_type == "enum":
                cls._apply_enum(node, prop_id, prop_info)
            elif prop_type == "color_ramp":
                cls._apply_color_ramp(node, prop_id, prop_info)
            elif prop_type == "curve_mapping":
                cls._apply_curve_mapping(node, prop_id, prop_info)
            elif prop_type == "bake_items":
                cls._apply_bake_items(node, prop_id, prop_info)
            elif prop_type == "zone_internal":
                cls._apply_zone_internal(node, prop_id, prop_info)
            elif prop_type == "generic_pointer":
                cls._apply_generic_pointer(node, prop_id, prop_info)
            elif prop_type in ("color", "vector"):
                setattr(node, prop_id, tuple(float(v) for v in value))
            elif prop_type == "matrix":
                # 4x4 matrix
                for i, row in enumerate(value):
                    for j, v in enumerate(row):
                        node[prop_id][i][j] = float(v)
            elif prop_type == "matrix3x3":
                for i, row in enumerate(value):
                    for j, v in enumerate(row):
                        node[prop_id][i][j] = float(v)
            elif prop_type in ("float_array", "int_array"):
                # Try direct assignment first
                try:
                    setattr(node, prop_id, [float(v) if prop_type == "float_array" else int(v) for v in value])
                except TypeError:
                    # Some array properties don't support list assignment, iterate
                    arr = getattr(node, prop_id)
                    for i, v in enumerate(value):
                        arr[i] = float(v) if prop_type == "float_array" else int(v)
            elif prop_type == "vector2":
                setattr(node, prop_id, tuple(float(v) for v in value))
            elif prop_type == "bool":
                setattr(node, prop_id, bool(value))
            elif prop_type == "int":
                setattr(node, prop_id, int(value))
            elif prop_type == "float":
                setattr(node, prop_id, float(value))
            elif prop_type == "string":
                setattr(node, prop_id, str(value))
            elif prop_type == "enum":
                # Handled above
                pass
            elif prop_type == "unknown":
                print(f"[WARN] Skipping unknown type property {node.bl_idname}.{prop_id}")
            else:
                # Generic fallback
                setattr(node, prop_id, value)
                
        except Exception as e:
            print(f"[ERROR] Failed to set {node.bl_idname}.{prop_id}: {e}")
    
    @classmethod
    def _apply_enum(cls, node: bpy.types.Node, prop_id: str, prop_info: Dict[str, Any]) -> None:
        """Apply enum with cross-version downgrade support."""
        target_value = prop_info.get("value", "")
        saved_items = prop_info.get("enum_items", [])
        
        if not hasattr(node, prop_id):
            return
            
        # Check if exact value exists
        current_prop = node.bl_rna.properties.get(prop_id)
        if not current_prop or not hasattr(current_prop, 'enum_items'):
            # Fallback direct set
            try:
                setattr(node, prop_id, target_value)
            except Exception as e:
                print(f"[WARN] Direct enum set failed for {node.bl_idname}.{prop_id}: {e}")
            return
        
        current_items = [item.identifier for item in current_prop.enum_items]
        
        if target_value in current_items:
            setattr(node, prop_id, target_value)
            return
        
        # Downgrade handling: value no longer exists in current version
        print(f"[WARN] Enum value '{target_value}' not found in {node.bl_idname}.{prop_id}")
        print(f"  Available: {current_items}")
        print(f"  Saved options: {saved_items}")
        
        # Strategy 1: Case-insensitive exact match
        target_upper = target_value.upper()
        for item in current_items:
            if item.upper() == target_upper:
                setattr(node, prop_id, item)
                print(f"  -> Mapped to {item} (case-insensitive match)")
                return
        
        # Strategy 2: Substring match (saved item contained in current, or vice versa)
        for saved in saved_items:
            saved_upper = saved.upper()
            for item in current_items:
                if saved_upper in item.upper() or item.upper() in saved_upper:
                    setattr(node, prop_id, item)
                    print(f"  -> Mapped to {item} (substring match from {saved})")
                    return
        
        # Strategy 3: Use first available as default
        if current_items:
            default = current_items[0]
            setattr(node, prop_id, default)
            print(f"  -> Fallback to default {default}")
    
    @classmethod
    def _apply_id_reference(cls, node: bpy.types.Node, prop_id: str,
                             prop_info: Dict[str, Any]) -> None:
        """Apply ID reference with collection lookup."""
        value_name = prop_info.get("value", "")
        id_type = prop_info.get("id_type", "")
        
        if not value_name:
            return
            
        data_collections = {
            "Image": lambda: bpy.data.images,
            "Material": lambda: bpy.data.materials,
            "Object": lambda: bpy.data.objects,
            "Collection": lambda: bpy.data.collections,
            "Texture": lambda: bpy.data.textures,
            "GeometryNodeTree": lambda: bpy.data.node_groups,
            "ShaderNodeTree": lambda: bpy.data.node_groups,
            "CompositorNodeTree": lambda: bpy.data.node_groups,
            "MovieClip": lambda: bpy.data.movieclips,
            "Action": lambda: bpy.data.actions,
            "Mesh": lambda: bpy.data.meshes,
            "Curve": lambda: bpy.data.curves,
            "Armature": lambda: bpy.data.armatures,
        }
        
        collection_getter = data_collections.get(id_type)
        if not collection_getter:
            print(f"[WARN] Unknown ID type {id_type} for {node.bl_idname}.{prop_id}")
            return
            
        collection = collection_getter()
        if value_name in collection:
            setattr(node, prop_id, collection[value_name])
        else:
            print(f"[WARN] Could not find {id_type} '{value_name}' for {node.bl_idname}.{prop_id}")
    
    @classmethod
    def _apply_color_ramp(cls, node: bpy.types.Node, prop_id: str,
                          prop_info: Dict[str, Any]) -> None:
        """Apply ColorRamp data."""
        if not hasattr(node, prop_id):
            return
            
        ramp_data = prop_info.get("value", {})
        ramp = getattr(node, prop_id)
        
        if not hasattr(ramp, 'elements'):
            return
            
        # Set interpolation
        if "interpolation" in ramp_data:
            try:
                ramp.interpolation = ramp_data["interpolation"]
            except Exception as e:
                print(f"[WARN] Failed to set color ramp interpolation: {e}")
        
        # Set color mode if available
        if "color_mode" in ramp_data and hasattr(ramp, 'color_mode'):
            try:
                ramp.color_mode = ramp_data["color_mode"]
            except Exception as e:
                print(f"[WARN] Failed to set color mode: {e}")
        
        # Adjust element count
        elements_data = ramp_data.get("elements", [])
        while len(ramp.elements) < len(elements_data):
            ramp.elements.new(0.5)
        while len(ramp.elements) > len(elements_data):
            ramp.elements.remove(ramp.elements[-1])
        
        # Apply element data
        for i, elem_data in enumerate(elements_data):
            ramp.elements[i].position = elem_data.get("position", 0.5)
            ramp.elements[i].color = tuple(elem_data.get("color", [0, 0, 0, 1]))
    
    @classmethod
    def _apply_curve_mapping(cls, node: bpy.types.Node, prop_id: str,
                             prop_info: Dict[str, Any]) -> None:
        """Apply CurveMapping data."""
        if not hasattr(node, prop_id):
            return
            
        curve_data = prop_info.get("value", {})
        mapping = getattr(node, prop_id)
        
        if not hasattr(mapping, 'curves'):
            return
        
        curves = curve_data.get("curves", [])
        for i, curve_info in enumerate(curves):
            if i >= len(mapping.curves):
                break
                
            curve = mapping.curves[i]
            points = curve_info.get("points", [])
            
            while len(curve.points) < len(points):
                curve.points.new(0.5, 0.5)
            while len(curve.points) > len(points):
                curve.points.remove(curve.points[-1])
            
            for j, point_info in enumerate(points):
                loc = point_info.get("location", [0.5, 0.5])
                curve.points[j].location = (loc[0], loc[1])
                curve.points[j].handle_type = point_info.get("handle_type", "AUTO")
        
        # Apply levels
        for attr in ["black_level", "white_level", "clip_min_x", "clip_min_y", 
                     "clip_max_x", "clip_max_y", "use_clip"]:
            if attr in curve_data and hasattr(mapping, attr):
                try:
                    if attr in ("black_level", "white_level"):
                        setattr(mapping, attr, tuple(curve_data[attr]))
                    else:
                        setattr(mapping, attr, curve_data[attr])
                except Exception as e:
                    print(f"[WARN] Failed to set curve mapping {attr}: {e}")
        
        mapping.update()
    
    @classmethod
    def _apply_bake_items(cls, node: bpy.types.Node, prop_id: str,
                          prop_info: Dict[str, Any]) -> None:
        """Apply BakeItems data."""
        if not hasattr(node, 'bake_items'):
            return
            
        items_data = prop_info.get("value", [])
        # Bake items are typically auto-generated, just verify structure
        for i, item_data in enumerate(items_data):
            if i < len(node.bake_items):
                item = node.bake_items[i]
                if "name" in item_data:
                    item.name = item_data["name"]
    
    @classmethod
    def _apply_zone_internal(cls, node: bpy.types.Node, prop_id: str,
                              prop_info: Dict[str, Any]) -> None:
        """Apply zone internal tree reference."""
        zone_data = prop_info.get("value", {})
        if not zone_data:
            return
        
        # Zone internal trees are auto-created, just verify
        if hasattr(node, 'zone') and node.zone:
            print(f"[INFO] Zone node {node.name} has internal tree: {node.zone.name}")
    
    @classmethod
    def _apply_generic_pointer(cls, node: bpy.types.Node, prop_id: str,
                                prop_info: Dict[str, Any]) -> None:
        """Apply generic pointer properties recursively."""
        if not hasattr(node, prop_id):
            return
            
        target = getattr(node, prop_id)
        if target is None:
            return
            
        generic_props = prop_info.get("value", {})
        for sub_prop_id, sub_info in generic_props.items():
            cls._apply_single_property(target, sub_prop_id, sub_info)