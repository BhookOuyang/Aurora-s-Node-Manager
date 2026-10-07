# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""Reversible clipboard codec for AuroraSNodeManager patterns.

Three reversible layers applied on top of the full JSON pattern format:

  L3  structural compaction  : verbose keys -> short keys, long UUIDs -> short
                               sequential ids, fixed-structure lists compacted.
  L2  default-diff storage   : for each distinct bl_idname a throwaway temp node
                               is created once; only values that differ from the
                               fresh-node defaults are stored. Expand rebuilds the
                               full record from ``defaults union diff``.
  L1  transport compression  : compact JSON -> zlib -> base64 (clipboard needs
                               plain text).

Encode:  full dict -> L3 -> L2 -> L1 -> clipboard string (JSON wrapper)
Decode:  clipboard string -> L1 -> L2 -> L3 -> full dict

The compact payload is marked with ``{"_aurora_c1": 1, "data": "..."}`` so older
clipboard bundles (and single patterns) keep pasting unchanged.
"""
import base64
import json
import uuid
import zlib

import bpy

from .serializer import PatternSerializer
from .zone_handler import ZoneHandler


# Format markers
COMPACT_MAGIC_KEY = "_aurora_c1"
COMPACT_MAGIC_VERSION = 1
BUNDLE_KEY = "_aurora_bundle"

# Node types whose sockets come from a runtime interface / pairing and therefore cannot be diffed against a fresh temp node's sockets.
_NO_SOCKET_DIFF = {
    "ShaderNodeGroup", "GeometryNodeGroup", "CompositorNodeGroup",
}


def _is_group_node(bl_idname):
    return bl_idname in _NO_SOCKET_DIFF


def _is_zone_node(bl_idname):
    return ZoneHandler.is_zone_node(bl_idname)



# L3 key tables (short keys may be reused across record kinds; the enclosing structure always disambiguates them).
_PATTERN = {
    "format_version": "f", "meta": "m", "nodes": "n",
    "links": "l", "interface": "i",
}
_META = {
    "name": "n", "description": "d", "author": "a", "version": "v",
    "created": "c", "blender_version": "b", "node_tree_type": "t",
    "is_subgroup": "s", "tags": "x", "locale": "l", "is_locked": "k",
}
_NODE = {
    "uuid": "u", "bl_idname": "b", "label": "l", "location": "o",
    "dimensions": "d", "mute": "m", "hide": "h", "properties": "r",
    "inputs": "i", "outputs": "e", "special": "s",
    "parent_frame": "f", "location_relative": "t",
}
_SOCKET = {"name": "n", "identifier": "i", "type": "t", "default_value": "v"}
_PROP = {
    "type": "t", "value": "v", "subtype": "s", "length": "l",
    "enum_items": "e", "id_type": "d", "class_name": "c",
}
_INTERFACE = {"inputs": "i", "outputs": "o"}
_INTERFACE_SOCKET = {
    "name": "n", "identifier": "i", "in_out": "e", "type": "t", "subtype": "s",
    "default_value": "v", "min_value": "mn", "max_value": "mx",
    "description": "d", "hide_value": "hv", "hide_in_modifier": "hm",
    "force_non_field": "fn", "default_attribute_name": "an",
}
_SPECIAL = {
    "color_ramp": "c", "curve_mapping": "u", "zone": "z", "group": "g",
    "image": "i", "material": "m", "file_paths": "f", "capture_items": "p",
}
_COLOR_RAMP = {"interpolation": "i", "elements": "e", "color_mode": "m"}
_RAMP_ELEMENT = {"position": "p", "color": "c"}
_CURVE_MAPPING = {
    "curves": "c", "black_level": "b", "white_level": "w",
    "clip_min_x": "cx", "clip_min_y": "cy", "clip_max_x": "Cx",
    "clip_max_y": "Cy", "use_clip": "u",
}
_CURVE = {"points": "p"}
_CURVE_POINT = {"location": "l", "handle_type": "h"}
_GROUP_REF = {"group_id": "id", "group_name": "n", "inputs": "i"}
_GROUP_INPUT = {"name": "n", "identifier": "i", "value": "v"}
_ZONE = {
    "zone_type": "t", "has_internal_tree": "h", "internal_data": "d",
    "state_items": "s", "bake_items": "b",
}
_ZONE_ITEM = {"name": "n", "socket_type": "s", "data_type": "d"}
_CAPTURE_ITEM = {"name": "n", "socket_type": "s", "data_type": "d"}



# Generic key mapping helpers
def _shorten(data, table):
    if not isinstance(data, dict):
        return data
    return {table.get(k, k): v for k, v in data.items()}


def _lengthen(data, table):
    if not isinstance(data, dict):
        return data
    rev = {v: k for k, v in table.items()}
    return {rev.get(k, k): v for k, v in data.items()}


def _value_eq(a, b):
    """Recursive equality for serialized values (lists, dicts, scalars)."""
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(_value_eq(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_value_eq(a[k], b[k]) for k in a)
    return a == b


class _JsonEncoder(json.JSONEncoder):
    """JSON encoder handling mathutils types (kept local to avoid import cycle)."""

    def default(self, obj):
        try:
            import mathutils
            if isinstance(obj, (mathutils.Vector, mathutils.Color,
                                mathutils.Euler, mathutils.Quaternion)):
                return list(obj)
            if isinstance(obj, mathutils.Matrix):
                return [list(row) for row in obj]
        except Exception:
            pass
        return super().default(obj)



# L2 default-diff: throwaway temp nodes for fresh-node defaults
class _DefaultPool:
    """Creates cached serialized default records for node types.

    One temp node per distinct bl_idname is created inside a single throwaway
    node group of the pattern's tree type; the group is removed in ``dispose``.
    Node types that cannot be created (or whose defaults cannot be read) are
    remembered so callers fall back to storing the full record.
    """

    def __init__(self, tree_type):
        self.tree_type = tree_type or "ShaderNodeTree"
        self.tree = None
        self.cache = {}
        self.failed = set()

    def _ensure_tree(self):
        if self.tree is None:
            try:
                name = "__aurora_defaults__" + uuid.uuid4().hex[:8]
                self.tree = bpy.data.node_groups.new(name, self.tree_type)
            except Exception:
                self.tree = None
        return self.tree

    def get_default(self, bl_idname):
        if bl_idname in self.cache:
            return self.cache[bl_idname]
        if bl_idname in self.failed:
            return None
        tree = self._ensure_tree()
        if tree is None:
            self.failed.add(bl_idname)
            return None
        temp_node = None
        try:
            temp_node = tree.nodes.new(type=bl_idname)
            record = PatternSerializer()._serialize_node(temp_node, {temp_node: "<default>"})
            special = record.get("special", {})
            for key in ("zone", "group", "image", "material", "file_paths",
                        "capture_items"):
                special.pop(key, None)
            record["special"] = special
            self.cache[bl_idname] = record
            return record
        except Exception:
            self.failed.add(bl_idname)
            return None
        finally:
            if temp_node is not None:
                try:
                    tree.nodes.remove(temp_node)
                except Exception:
                    pass

    def dispose(self):
        if self.tree is not None:
            try:
                bpy.data.node_groups.remove(self.tree)
            except Exception:
                pass
            self.tree = None



# L2 diff / merge helpers
def _diff_properties(stored_props, default_props):
    """Return compact property dict holding only entries changed vs defaults."""
    if not isinstance(stored_props, dict):
        return stored_props if stored_props else {}
    default_props = default_props or {}
    out = {}
    for key, entry in stored_props.items():
        def_entry = default_props.get(key)
        if not isinstance(entry, dict):
            continue
        if isinstance(def_entry, dict):
            if _value_eq(entry.get("value"), def_entry.get("value")):
                continue  # equals default -> drop entirely
            reduced = dict(entry)
            reduced.pop("enum_descriptions", None)
            if reduced.get("type") == "enum":
                d_items = def_entry.get("enum_items")
                if d_items is not None and _value_eq(reduced.get("enum_items"), d_items):
                    reduced.pop("enum_items", None)  # inherits from default
            out[key] = reduced
        else:
            reduced = dict(entry)
            reduced.pop("enum_descriptions", None)
            out[key] = reduced
    return out


def _merge_properties(prop_compact, default_props):
    """Rebuild full property dict from defaults union stored diffs."""
    out = {}
    for key, entry in (prop_compact or {}).items():
        if not isinstance(entry, dict):
            out[key] = entry
            continue
        full_entry = _lengthen(entry, _PROP)
        if full_entry.get("type") == "enum":
            def_entry = default_props.get(key)
            if "enum_items" not in full_entry and isinstance(def_entry, dict):
                items = def_entry.get("enum_items")
                if items is not None:
                    full_entry["enum_items"] = items
            full_entry["enum_descriptions"] = _regenerate_enum_desc(def_entry)
        out[key] = full_entry
    return out


def _regenerate_enum_desc(def_entry):
    if isinstance(def_entry, dict):
        desc = def_entry.get("enum_descriptions")
        if isinstance(desc, dict):
            return desc
    return {}


def _diff_sockets(stored_sockets, default_sockets, allow_diff):
    """Return positional socket diff list (aligned by index), or None if empty."""
    if not stored_sockets:
        return None
    default_sockets = default_sockets or []
    n_def = len(default_sockets)
    out = []
    for idx, s in enumerate(stored_sockets):
        if not isinstance(s, dict):
            out.append(None)
            continue
        if "default_value" not in s:
            out.append(None)  # linked / unset socket: nothing to store
            continue
        d = default_sockets[idx] if idx < n_def else None
        if allow_diff and isinstance(d, dict):
            same_id = (s.get("identifier") == d.get("identifier")
                       and s.get("type") == d.get("type")
                       and s.get("name") == d.get("name"))
            if same_id and _value_eq(s.get("default_value"), d.get("default_value")):
                out.append(None)
                continue
            if same_id:
                out.append({"v": s["default_value"]})
                continue
        entry = {}
        if "name" in s:
            entry["n"] = s["name"]
        if "identifier" in s:
            entry["i"] = s["identifier"]
        if "type" in s:
            entry["t"] = s["type"]
        entry["v"] = s["default_value"]
        out.append(entry)
    if not any(x is not None for x in out):
        return None
    return out


def _merge_sockets(default_sockets, diff_sockets, is_group):
    """Rebuild full socket list from defaults union stored diffs."""
    default_sockets = default_sockets or []
    if not diff_sockets:
        recs = []
        for s in default_sockets:
            r = dict(s)
            r.pop("default_value", None)
            recs.append(r)
        return recs
    out = []
    n_def = len(default_sockets)
    for idx, entry in enumerate(diff_sockets):
        if entry is None:
            if idx < n_def:
                r = dict(default_sockets[idx])
                r.pop("default_value", None)
                out.append(r)
            else:
                out.append({})
            continue
        if is_group or idx >= n_def:
            rec = {"index": idx}
            if "n" in entry:
                rec["name"] = entry["n"]
            if "i" in entry:
                rec["identifier"] = entry["i"]
            if "t" in entry:
                rec["type"] = entry["t"]
            if "v" in entry:
                rec["default_value"] = entry["v"]
            out.append(rec)
        else:
            rec = dict(default_sockets[idx])
            if "n" in entry:
                rec["name"] = entry["n"]
            if "i" in entry:
                rec["identifier"] = entry["i"]
            if "t" in entry:
                rec["type"] = entry["t"]
            if "v" in entry:
                rec["default_value"] = entry["v"]
            out.append(rec)
    return out


def _full_socket_short(s):
    out = {}
    if "name" in s:
        out["n"] = s["name"]
    if "identifier" in s:
        out["i"] = s["identifier"]
    if "type" in s:
        out["t"] = s["type"]
    if "default_value" in s:
        out["v"] = s["default_value"]
    return out


def _diff_special(stored_special, default_special):
    """Diff special block; color_ramp / curve_mapping are dropped when equal."""
    if not stored_special:
        return None
    out = {}
    for k, v in stored_special.items():
        dv = default_special.get(k)
        if k in ("color_ramp", "curve_mapping") and dv is not None and _value_eq(v, dv):
            continue
        out[k] = v
    return out or None


def _merge_special(compact_special, default_special):
    merged = {}
    for k, v in compact_special.items():
        lk = _lengthen({k: None}, _SPECIAL).popitem()[0]
        if k == "c":
            merged[lk] = _lengthen_color_ramp(v)
        elif k == "u":
            merged[lk] = _lengthen_curve_mapping(v)
        elif k == "z":
            merged[lk] = _lengthen_zone(v)
        elif k == "g":
            merged[lk] = _lengthen_group_ref(v)
        elif k == "p":
            merged[lk] = [_lengthen(item, _CAPTURE_ITEM) for item in v]
        else:
            merged[lk] = v
    for k, v in (default_special or {}).items():
        if k not in merged:
            merged[k] = v
    return merged or None



# L3 special-structure shorten / lengthen
def _shorten_color_ramp(ramp):
    out = {}
    for k, v in ramp.items():
        sk = _COLOR_RAMP.get(k, k)
        if k == "elements" and isinstance(v, list):
            out[sk] = [_shorten(e, _RAMP_ELEMENT) for e in v]
        else:
            out[sk] = v
    return out


def _lengthen_color_ramp(ramp):
    out = {}
    for k, v in ramp.items():
        lk = _lengthen({k: None}, _COLOR_RAMP).popitem()[0]
        if k == "e" and isinstance(v, list):
            out[lk] = [_lengthen(e, _RAMP_ELEMENT) for e in v]
        else:
            out[lk] = v
    return out


def _shorten_curve_mapping(cm):
    out = {}
    for k, v in cm.items():
        sk = _CURVE_MAPPING.get(k, k)
        if k == "curves" and isinstance(v, list):
            curves = []
            for c in v:
                if isinstance(c, dict) and isinstance(c.get("points"), list):
                    curves.append({"p": [_shorten(pt, _CURVE_POINT) for pt in c["points"]]})
                else:
                    curves.append(c)
            out[sk] = curves
        else:
            out[sk] = v
    return out


def _lengthen_curve_mapping(cm):
    out = {}
    for k, v in cm.items():
        lk = _lengthen({k: None}, _CURVE_MAPPING).popitem()[0]
        if k == "c" and isinstance(v, list):
            curves = []
            for c in v:
                if isinstance(c, dict) and isinstance(c.get("p"), list):
                    curves.append({"points": [_lengthen(pt, _CURVE_POINT) for pt in c["p"]]})
                else:
                    curves.append(c)
            out[lk] = curves
        else:
            out[lk] = v
    return out


def _shorten_group_ref(g):
    out = {}
    for k, v in g.items():
        sk = _GROUP_REF.get(k, k)
        if k == "inputs" and isinstance(v, list):
            out[sk] = [_shorten(item, _GROUP_INPUT) for item in v]
        elif k == "inputs" and isinstance(v, dict):
            out[sk] = {name: _shorten(val, _GROUP_INPUT) for name, val in v.items()}
        else:
            out[sk] = v
    return out


def _lengthen_group_ref(g):
    out = {}
    for k, v in g.items():
        lk = _lengthen({k: None}, _GROUP_REF).popitem()[0]
        if k == "i" and isinstance(v, list):
            out[lk] = [_lengthen(item, _GROUP_INPUT) for item in v]
        elif k == "i" and isinstance(v, dict):
            out[lk] = {name: _lengthen(val, _GROUP_INPUT) for name, val in v.items()}
        else:
            out[lk] = v
    return out


def _shorten_zone(zone):
    out = {}
    for k, v in zone.items():
        sk = _ZONE.get(k, k)
        if k == "internal_data" and isinstance(v, dict):
            out[sk] = _encode_pattern(v)
        elif k in ("state_items", "bake_items") and isinstance(v, list):
            out[sk] = [_shorten(item, _ZONE_ITEM) for item in v]
        else:
            out[sk] = v
    return out


def _lengthen_zone(zone):
    out = {}
    for k, v in zone.items():
        lk = _lengthen({k: None}, _ZONE).popitem()[0]
        if k == "d" and isinstance(v, dict):
            out[lk] = _decode_pattern(v)
        elif k in ("s", "b") and isinstance(v, list):
            out[lk] = [_lengthen(item, _ZONE_ITEM) for item in v]
        else:
            out[lk] = v
    return out


def _shorten_special(special):
    out = {}
    for k, v in special.items():
        sk = _SPECIAL.get(k, k)
        if k == "color_ramp" and isinstance(v, dict):
            out[sk] = _shorten_color_ramp(v)
        elif k == "curve_mapping" and isinstance(v, dict):
            out[sk] = _shorten_curve_mapping(v)
        elif k == "zone" and isinstance(v, dict):
            out[sk] = _shorten_zone(v)
        elif k == "group" and isinstance(v, dict):
            out[sk] = _shorten_group_ref(v)
        elif k == "capture_items" and isinstance(v, list):
            out[sk] = [_shorten(item, _CAPTURE_ITEM) for item in v]
        else:
            out[sk] = v
    return out



# Node encode / decode
def _encode_node(node, uuid_map, pool):
    bl = node.get("bl_idname", "")
    compact = {"b": bl}
    if "uuid" in node:
        compact["u"] = uuid_map.get(node["uuid"], node["uuid"])
    elif "id" in node:
        compact["u"] = uuid_map.get(node["id"], node["id"])

    default = pool.get_default(bl) if pool else None
    socket_diff = default is not None and not _is_group_node(bl) and not _is_zone_node(bl)

    if default is not None:
        if node.get("label"):
            compact["l"] = node["label"]
        if "location" in node and not _value_eq(node["location"], default.get("location")):
            compact["o"] = node["location"]
        if "dimensions" in node and not _value_eq(node["dimensions"], default.get("dimensions")):
            compact["d"] = node["dimensions"]
        if node.get("mute"):
            compact["m"] = True
        if node.get("hide"):
            compact["h"] = True
        if node.get("properties"):
            diff = _diff_properties(node["properties"], default.get("properties") or {})
            if diff:
                compact["r"] = {k: _shorten(v, _PROP) for k, v in diff.items()}
        in_diff = _diff_sockets(node.get("inputs") or [], default.get("inputs") or [], socket_diff)
        out_diff = _diff_sockets(node.get("outputs") or [], default.get("outputs") or [], socket_diff)
        if in_diff:
            compact["i"] = in_diff
        if out_diff:
            compact["e"] = out_diff
        if node.get("special"):
            sdiff = _diff_special(node["special"], default.get("special") or {})
            if sdiff:
                compact["s"] = _shorten_special(sdiff)
    else:
        if node.get("label"):
            compact["l"] = node["label"]
        if "location" in node:
            compact["o"] = node["location"]
        if "dimensions" in node:
            compact["d"] = node["dimensions"]
        if node.get("mute"):
            compact["m"] = True
        if node.get("hide"):
            compact["h"] = True
        if node.get("properties"):
            compact["r"] = {k: _shorten(v, _PROP) for k, v in node["properties"].items()}
        if node.get("inputs"):
            compact["i"] = [_full_socket_short(s) for s in node["inputs"]]
        if node.get("outputs"):
            compact["e"] = [_full_socket_short(s) for s in node["outputs"]]
        if node.get("special"):
            compact["s"] = _shorten_special(node["special"])

    if "parent_frame" in node:
        compact["f"] = uuid_map.get(node["parent_frame"], node["parent_frame"])
        if "location_relative" in node:
            compact["t"] = node["location_relative"]

    return compact


def _decode_node(nc, id_map, pool):
    bl = nc.get("b", "")
    default = pool.get_default(bl) if pool else None
    is_group = _is_group_node(bl) or _is_zone_node(bl)

    full = {
        "uuid": id_map.get(nc.get("u"), nc.get("u", "")),
        "bl_idname": bl,
        "label": nc.get("l") if "l" in nc else (default.get("label", "") if default else ""),
        "location": nc.get("o") if "o" in nc else (default.get("location", [0, 0]) if default else [0, 0]),
        "dimensions": nc.get("d") if "d" in nc else (default.get("dimensions", [100, 100]) if default else [100, 100]),
        "mute": nc.get("m", default.get("mute", False) if default else False),
        "hide": nc.get("h", default.get("hide", False) if default else False),
    }

    full["properties"] = _merge_properties(nc.get("r"), (default or {}).get("properties") or {})
    full["inputs"] = _merge_sockets((default or {}).get("inputs") or [], nc.get("i"), is_group)
    full["outputs"] = _merge_sockets((default or {}).get("outputs") or [], nc.get("e"), is_group)

    if "s" in nc:
        merged = _merge_special(nc["s"], (default or {}).get("special") or {})
        if merged:
            full["special"] = merged

    if "f" in nc:
        full["parent_frame"] = id_map.get(nc["f"], nc["f"])
        if "t" in nc:
            full["location_relative"] = nc["t"]

    return full



# Link encode / decode
def _encode_link(link, uuid_map):
    from_uuid = link.get("from_uuid") or link.get("from", "").split(".")[0]
    to_uuid = link.get("to_uuid") or link.get("to", "").split(".")[0]
    return {
        "f": uuid_map.get(from_uuid, from_uuid),
        "a": [link.get("from_socket_id", ""), link.get("from_socket_name", ""),
              link.get("from_socket_index", -1)],
        "t": uuid_map.get(to_uuid, to_uuid),
        "b": [link.get("to_socket_id", ""), link.get("to_socket_name", ""),
              link.get("to_socket_index", -1)],
    }


def _decode_link(link, id_map):
    a = link.get("a") or []
    b = link.get("b") or []
    return {
        "from_uuid": id_map.get(link.get("f"), link.get("f", "")),
        "from_socket_id": a[0] if len(a) > 0 else "",
        "from_socket_name": a[1] if len(a) > 1 else "",
        "from_socket_index": a[2] if len(a) > 2 else -1,
        "to_uuid": id_map.get(link.get("t"), link.get("t", "")),
        "to_socket_id": b[0] if len(b) > 0 else "",
        "to_socket_name": b[1] if len(b) > 1 else "",
        "to_socket_index": b[2] if len(b) > 2 else -1,
    }



# Interface encode / decode
def _encode_interface(interface):
    if not isinstance(interface, dict):
        return interface
    out = {}
    for key, value in interface.items():
        sk = _INTERFACE.get(key, key)
        if key in ("inputs", "outputs") and isinstance(value, list):
            out[sk] = [_shorten(s, _INTERFACE_SOCKET) for s in value]
        else:
            out[sk] = value
    return out


def _decode_interface(interface):
    if not isinstance(interface, dict):
        return interface
    out = {}
    for key, value in interface.items():
        lk = _lengthen({key: None}, _INTERFACE).popitem()[0]
        if key in ("i", "o") and isinstance(value, list):
            out[lk] = [_lengthen(s, _INTERFACE_SOCKET) for s in value]
        else:
            out[lk] = value
    return out



# Pattern (main / group file) encode / decode
def _encode_pattern(pattern):
    nodes = pattern.get("nodes") or []
    uuid_map = {}
    for i, n in enumerate(nodes):
        key = n.get("uuid") if isinstance(n, dict) else None
        uuid_map[key] = "n%d" % i

    pool = _DefaultPool((pattern.get("meta") or {}).get("node_tree_type"))
    try:
        out = {"f": pattern.get("format_version", "1.0.0")}
        if "meta" in pattern:
            out["m"] = _shorten(pattern["meta"], _META)
        out["n"] = [_encode_node(n, uuid_map, pool) for n in nodes]
        out["l"] = [_encode_link(l, uuid_map) for l in (pattern.get("links") or [])]
        if "interface" in pattern:
            out["i"] = _encode_interface(pattern["interface"])
    finally:
        pool.dispose()
    return out


def _decode_pattern(compact):
    nodes_c = compact.get("n") or []
    id_map = {}
    for i in range(len(nodes_c)):
        id_map["n%d" % i] = str(uuid.uuid4())

    meta_c = compact.get("m")
    tree_type = None
    if isinstance(meta_c, dict):
        tree_type = meta_c.get("t")

    pool = _DefaultPool(tree_type)
    try:
        pattern = {"format_version": compact.get("f", "1.0.0")}
        if "m" in compact:
            pattern["meta"] = _lengthen(compact["m"], _META)
        pattern["nodes"] = [_decode_node(nc, id_map, pool) for nc in nodes_c]
        pattern["links"] = [_decode_link(l, id_map) for l in (compact.get("l") or [])]
        if "i" in compact:
            pattern["interface"] = _decode_interface(compact["i"])
    finally:
        pool.dispose()
    return pattern



# Bundle level
def _encode_bundle(data):
    if isinstance(data, dict) and data.get(BUNDLE_KEY) is True:
        out = {BUNDLE_KEY: True, "main": _encode_pattern(data["main"])}
        if "groups" in data:
            out["groups"] = {gid: _encode_pattern(g) for gid, g in data["groups"].items()}
        return out
    return _encode_pattern(data)


def _decode_bundle(compact):
    if isinstance(compact, dict) and compact.get(BUNDLE_KEY) is True:
        out = {BUNDLE_KEY: True, "main": _decode_pattern(compact["main"])}
        if "groups" in compact:
            out["groups"] = {gid: _decode_pattern(g) for gid, g in compact["groups"].items()}
        return out
    return _decode_pattern(compact)



# L1 transport (zlib + base64)
def _to_transport(compact):
    text = json.dumps(compact, separators=(",", ":"), ensure_ascii=False, cls=_JsonEncoder)
    payload = zlib.compress(text.encode("utf-8"), 9)
    b64 = base64.b64encode(payload).decode("ascii")
    return {COMPACT_MAGIC_KEY: COMPACT_MAGIC_VERSION, "data": b64}


def _from_transport(wrapper):
    payload = base64.b64decode(wrapper.get("data", ""))
    text = zlib.decompress(payload).decode("utf-8")
    return json.loads(text)



# Public API
def is_compact(data):
    """True if a parsed clipboard object is the compact transport wrapper."""
    return isinstance(data, dict) and data.get(COMPACT_MAGIC_KEY) == COMPACT_MAGIC_VERSION


def encode(data):
    """Compress a bundle or single pattern dict into a clipboard JSON string."""
    compact = _encode_bundle(data)
    wrapper = _to_transport(compact)
    return json.dumps(wrapper, separators=(",", ":"), ensure_ascii=False)


def decode(text):
    """Expand a compact clipboard JSON string back into a full bundle/pattern."""
    wrapper = json.loads(text)
    if not is_compact(wrapper):
        raise ValueError("Clipboard content is not a compact Aurora pattern")
    compact = _from_transport(wrapper)
    return _decode_bundle(compact)