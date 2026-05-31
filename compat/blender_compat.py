"""Blender 3.x / 4.x / 5.x API compatibility layer."""
import bpy
from typing import Optional

# Socket type mapping (3.x legacy -> 4.x+ standard)
SOCKET_TYPE_MAP = {
    # 3.x legacy types
    'VALUE': 'NodeSocketFloat',
    'INT': 'NodeSocketInt',
    'BOOLEAN': 'NodeSocketBool',
    'VECTOR': 'NodeSocketVector',
    'ROTATION': 'NodeSocketRotation',
    'MATRIX': 'NodeSocketMatrix',
    'STRING': 'NodeSocketString',
    'RGBA': 'NodeSocketColor',
    'SHADER': 'NodeSocketShader',
    'OBJECT': 'NodeSocketObject',
    'IMAGE': 'NodeSocketImage',
    'GEOMETRY': 'NodeSocketGeometry',
    'COLLECTION': 'NodeSocketCollection',
    'TEXTURE': 'NodeSocketTexture',
    'MATERIAL': 'NodeSocketMaterial',
    # 4.x+ types (pass-through)
    'NodeSocketFloat': 'NodeSocketFloat',
    'NodeSocketInt': 'NodeSocketInt',
    'NodeSocketBool': 'NodeSocketBool',
    'NodeSocketVector': 'NodeSocketVector',
    'NodeSocketRotation': 'NodeSocketRotation',
    'NodeSocketMatrix': 'NodeSocketMatrix',
    'NodeSocketString': 'NodeSocketString',
    'NodeSocketColor': 'NodeSocketColor',
    'NodeSocketShader': 'NodeSocketShader',
    'NodeSocketObject': 'NodeSocketObject',
    'NodeSocketImage': 'NodeSocketImage',
    'NodeSocketGeometry': 'NodeSocketGeometry',
    'NodeSocketCollection': 'NodeSocketCollection',
    'NodeSocketTexture': 'NodeSocketTexture',
    'NodeSocketMaterial': 'NodeSocketMaterial',
    'NodeSocketMenu': 'NodeSocketMenu',
    'NodeSocketVirtual': 'NodeSocketVirtual',
    'NodeSocketClosure': 'NodeSocketClosure',
    'NodeSocketBundle': 'NodeSocketBundle',
    # Float subtypes
    'NodeSocketFloatAngle': 'NodeSocketFloat',
    'NodeSocketFloatColorTemperature': 'NodeSocketFloat',
    'NodeSocketFloatDistance': 'NodeSocketFloat',
    'NodeSocketFloatFactor': 'NodeSocketFloat',
    'NodeSocketFloatFrequency': 'NodeSocketFloat',
    'NodeSocketFloatMass': 'NodeSocketFloat',
    'NodeSocketFloatPercentage': 'NodeSocketFloat',
    'NodeSocketFloatTime': 'NodeSocketFloat',
    'NodeSocketFloatTimeAbsolute': 'NodeSocketFloat',
    'NodeSocketFloatUnsigned': 'NodeSocketFloat',
    'NodeSocketFloatWavelength': 'NodeSocketFloat',
    # Int subtypes
    'NodeSocketIntFactor': 'NodeSocketInt',
    'NodeSocketIntPercentage': 'NodeSocketInt',
    'NodeSocketIntUnsigned': 'NodeSocketInt',
    # Vector subtypes
    'NodeSocketVector2D': 'NodeSocketVector',
    'NodeSocketVector4D': 'NodeSocketVector',
    'NodeSocketVectorAcceleration': 'NodeSocketVector',
    'NodeSocketVectorAcceleration2D': 'NodeSocketVector',
    'NodeSocketVectorAcceleration4D': 'NodeSocketVector',
    'NodeSocketVectorDirection': 'NodeSocketVector',
    'NodeSocketVectorDirection2D': 'NodeSocketVector',
    'NodeSocketVectorDirection4D': 'NodeSocketVector',
    'NodeSocketVectorEuler': 'NodeSocketVector',
    'NodeSocketVectorEuler2D': 'NodeSocketVector',
    'NodeSocketVectorEuler4D': 'NodeSocketVector',
    'NodeSocketVectorFactor': 'NodeSocketVector',
    'NodeSocketVectorFactor2D': 'NodeSocketVector',
    'NodeSocketVectorFactor4D': 'NodeSocketVector',
    'NodeSocketVectorPercentage': 'NodeSocketVector',
    'NodeSocketVectorPercentage2D': 'NodeSocketVector',
    'NodeSocketVectorPercentage4D': 'NodeSocketVector',
    'NodeSocketVectorTranslation': 'NodeSocketVector',
    'NodeSocketVectorTranslation2D': 'NodeSocketVector',
    'NodeSocketVectorTranslation4D': 'NodeSocketVector',
    'NodeSocketVectorVelocity': 'NodeSocketVector',
    'NodeSocketVectorVelocity2D': 'NodeSocketVector',
    'NodeSocketVectorVelocity4D': 'NodeSocketVector',
    'NodeSocketVectorXYZ': 'NodeSocketVector',
    'NodeSocketVectorXYZ2D': 'NodeSocketVector',
    'NodeSocketVectorXYZ4D': 'NodeSocketVector',
    # String subtypes
    'NodeSocketStringFilePath': 'NodeSocketString',
}


def map_socket_type(type_str):
    """Map any socket type string to standard 4.x+ type."""
    if not type_str:
        return 'NodeSocketFloat'
    return SOCKET_TYPE_MAP.get(type_str, type_str)


def get_socket_type_name(socket):
    """Get socket type name, handling 3.x and 4.x+ APIs."""
    # 4.x+ interface sockets have socket_type
    if hasattr(socket, 'socket_type'):
        return socket.socket_type
    # 3.x and node sockets have type
    if hasattr(socket, 'type'):
        return socket.type
    # Fallback to bl_idname
    if hasattr(socket, 'bl_idname'):
        return socket.bl_idname
    return 'NodeSocketFloat'


def get_socket_value_safe(socket):
    """Safely read socket default value."""
    try:
        socket_type = get_socket_type_name(socket)
        mapped = map_socket_type(socket_type)

        value = socket.default_value

        if mapped in ('NodeSocketFloat', 'NodeSocketFloatAngle', 'NodeSocketFloatFactor',
                      'NodeSocketFloatDistance', 'NodeSocketFloatPercentage',
                      'NodeSocketFloatTime', 'NodeSocketFloatUnsigned',
                      'NodeSocketFloatWavelength', 'NodeSocketFloatColorTemperature',
                      'NodeSocketFloatFrequency', 'NodeSocketFloatMass',
                      'NodeSocketFloatTimeAbsolute'):
            return float(value)
        elif mapped == 'NodeSocketInt':
            return int(value)
        elif mapped in ('NodeSocketBool',):
            return bool(value)
        elif mapped in ('NodeSocketVector', 'NodeSocketVector2D', 'NodeSocketVector4D',
                         'NodeSocketVectorAcceleration', 'NodeSocketVectorDirection',
                         'NodeSocketVectorEuler', 'NodeSocketVectorFactor',
                         'NodeSocketVectorPercentage', 'NodeSocketVectorTranslation',
                         'NodeSocketVectorVelocity', 'NodeSocketVectorXYZ'):
            return [float(v) for v in value]
        elif mapped == 'NodeSocketColor':
            return [float(v) for v in value]
        elif mapped == 'NodeSocketString':
            return str(value)
        elif mapped == 'NodeSocketRotation':
            return [float(v) for v in value]
        elif mapped == 'NodeSocketMatrix':
            # Matrix is 4x4, flatten to 16 elements
            return [[float(row[i]) for i in range(4)] for row in value]
        elif mapped == 'NodeSocketObject':
            return value.name if value else ""
        elif mapped == 'NodeSocketMaterial':
            return value.name if value else ""
        elif mapped == 'NodeSocketCollection':
            return value.name if value else ""
        elif mapped == 'NodeSocketImage':
            return value.name if value else ""
        elif mapped == 'NodeSocketTexture':
            return value.name if value else ""
        elif mapped == 'NodeSocketGeometry':
            return None  # Geometry sockets don't have default values
        elif mapped == 'NodeSocketShader':
            return None  # Shader sockets don't have default values
        else:
            # Generic fallback
            if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                return list(value)
            return value
    except Exception as e:
        print(f"[WARN] Failed to read socket value: {e}")
        return None


def set_socket_value_safe(socket, value, source_file="", on_warning=None):
    """Safely set socket default value."""
    if value is None:
        return

    def _warn(msg):
        if on_warning:
            on_warning(msg)
        else:
            print(msg)

    try:
        socket_type = get_socket_type_name(socket)
        mapped = map_socket_type(socket_type)

        if mapped in ('NodeSocketFloat', 'NodeSocketFloatAngle', 'NodeSocketFloatFactor',
                      'NodeSocketFloatDistance', 'NodeSocketFloatPercentage',
                      'NodeSocketFloatTime', 'NodeSocketFloatUnsigned',
                      'NodeSocketFloatWavelength', 'NodeSocketFloatColorTemperature',
                      'NodeSocketFloatFrequency', 'NodeSocketFloatMass',
                      'NodeSocketFloatTimeAbsolute'):
            socket.default_value = float(value)
        elif mapped == 'NodeSocketInt':
            socket.default_value = int(value)
        elif mapped == 'NodeSocketBool':
            socket.default_value = bool(value)
        elif mapped in ('NodeSocketVector', 'NodeSocketVector2D', 'NodeSocketVector4D',
                         'NodeSocketVectorAcceleration', 'NodeSocketVectorDirection',
                         'NodeSocketVectorEuler', 'NodeSocketVectorFactor',
                         'NodeSocketVectorPercentage', 'NodeSocketVectorTranslation',
                         'NodeSocketVectorVelocity', 'NodeSocketVectorXYZ'):
            socket.default_value = tuple(float(v) for v in value)
        elif mapped == 'NodeSocketColor':
            socket.default_value = tuple(float(v) for v in value)
        elif mapped == 'NodeSocketString':
            socket.default_value = str(value)
        elif mapped == 'NodeSocketRotation':
            socket.default_value = tuple(float(v) for v in value)
        elif mapped == 'NodeSocketMatrix':
            if isinstance(value, list) and len(value) == 4:
                for i, row in enumerate(value):
                    for j, v in enumerate(row):
                        socket.default_value[i][j] = float(v)
        elif mapped in ('NodeSocketObject', 'NodeSocketMaterial', 'NodeSocketCollection',
                        'NodeSocketImage', 'NodeSocketTexture'):
            if isinstance(value, str) and value:
                data_collections = {
                    'NodeSocketObject': lambda: bpy.data.objects,
                    'NodeSocketMaterial': lambda: bpy.data.materials,
                    'NodeSocketCollection': lambda: bpy.data.collections,
                    'NodeSocketImage': lambda: bpy.data.images,
                    'NodeSocketTexture': lambda: bpy.data.textures,
                }
                collection_getter = data_collections.get(mapped)
                if collection_getter:
                    collection = collection_getter()
                    if value in collection:
                        socket.default_value = collection[value]
        elif mapped == 'NodeSocketMenu':
            socket.default_value = str(value)
        else:
            try:
                socket.default_value = value
            except Exception:
                node = socket.node
                node_name = node.bl_idname if node else "?"
                socket_name = getattr(socket, 'name', '?')
                file_info = f" in '{source_file}'" if source_file else ""
                _warn(f"[WARN] {node_name}.{socket_name}: failed to set socket value (type: {mapped}){file_info}, please check")

    except Exception as e:
        node = socket.node
        node_name = node.bl_idname if node else "?"
        socket_name = getattr(socket, 'name', '?')
        file_info = f" in '{source_file}'" if source_file else ""
        _warn(f"[WARN] {node_name}.{socket_name}: failed to set socket value{file_info}: {e}")

def get_socket_by_index(node: bpy.types.Node, index: int, is_input: bool) -> Optional[bpy.types.NodeSocket]:
    """Get socket by index with bounds checking."""
    sockets = node.inputs if is_input else node.outputs
    if 0 <= index < len(sockets):
        return sockets[index]
    return None


def get_socket_index(socket: bpy.types.NodeSocket, is_input: bool) -> int:
    """Get socket index within its parent node."""
    node = socket.node
    sockets = node.inputs if is_input else node.outputs
    for i, s in enumerate(sockets):
        if s == socket:
            return i
    return -1