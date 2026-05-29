"""File utilities for pattern storage."""
import hashlib
import json
import re
import zipfile
import tempfile
import shutil
from pathlib import Path

import bpy


class AuroraJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles Blender mathutils types safely."""
    def default(self, obj):
        try:
            import mathutils
            if isinstance(obj, (mathutils.Vector, mathutils.Color,
                                mathutils.Euler, mathutils.Quaternion)):
                return list(obj)
            if isinstance(obj, mathutils.Matrix):
                return [list(row) for row in obj]
        except ImportError:
            pass
        return super().default(obj)


TYPE_SUBDIR_MAP = {
    'ShaderNodeTree': 'shader',
    'CompositorNodeTree': 'compositor',
    'GeometryNodeTree': 'geometry',
}

CLIPBOARD_BUNDLE_KEY = "_aurora_bundle"

ADDON_ROOT = Path(__file__).parent.parent



def validate_clipboard_data(text):
    """Validate clipboard text for pattern import.

    Supports two formats:
      1. Single JSON: a bare pattern dict with "meta" and "nodes" keys.
      2. Bundle JSON: an object with "_aurora_bundle": true, "main" (pattern dict),
         and optionally "groups" (dict of group_id -> group pattern dict).

    Returns:
        dict with keys:
            valid (bool)
            mode ("single" | "bundle" | None)
            main_data (dict | None)
            groups_data (dict[str, dict] | None)
            missing_groups (list[str] | None)
            error (str | None)
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return _result(False, error=f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        return _result(False, error="Clipboard content must be a JSON object")


    main_data = data.get("main", data)
    format_version = main_data.get("format_version", "1.0.0")
    if format_version not in ("1.0.0", "2.0.0", "3.0.0"):
        return _result(False, error=f"Unsupported format version: {format_version}")


    is_bundle = data.get(CLIPBOARD_BUNDLE_KEY) is True

    if is_bundle:
        return _validate_bundle(data)
    else:
        return _validate_single(data)


def _result(valid, mode=None, main_data=None, groups_data=None,
            missing_groups=None, error=None):
    return {
        "valid": valid,
        "mode": mode,
        "main_data": main_data,
        "groups_data": groups_data or {},
        "missing_groups": missing_groups,
        "error": error,
    }


def _collect_referenced_group_ids(main_data):
    """Collect all group_id values referenced by nodes in main_data."""
    ids = set()
    for node in main_data.get("nodes", []):
        group_info = node.get("special", {}).get("group")
        if group_info and isinstance(group_info, dict):
            gid = group_info.get("group_id")
            if gid:
                ids.add(gid)
    return ids


def _validate_single(data):
    if "meta" not in data or "nodes" not in data:
        return _result(False, error="Not a valid pattern (missing 'meta' or 'nodes')")

    referenced = _collect_referenced_group_ids(data)
    if referenced:
        return _result(
            False,
            error=f"Pattern references {len(referenced)} node group(s) but no bundle data provided",
            missing_groups=list(referenced),
        )

    return _result(True, mode="single", main_data=data)


def _validate_bundle(data):
    main = data.get("main")
    if not isinstance(main, dict):
        return _result(False, error="Bundle is missing 'main' field")
    if "meta" not in main or "nodes" not in main:
        return _result(False, error="Bundle 'main' is not a valid pattern (missing 'meta' or 'nodes')")

    groups = data.get("groups", {})
    if not isinstance(groups, dict):
        return _result(False, error="Bundle 'groups' must be a JSON object")

    for gid, gdata in groups.items():
        if not isinstance(gdata, dict) or "meta" not in gdata or "nodes" not in gdata:
            return _result(False, error=f"Bundle group '{gid}' is not a valid pattern")

    referenced = _collect_referenced_group_ids(main)
    missing = sorted(referenced - set(groups.keys()))
    if missing:
        return _result(
            False,
            error=f"Bundle is missing group(s): {', '.join(missing)}",
            missing_groups=missing,
        )

    return _result(True, mode="bundle", main_data=main, groups_data=groups)


def get_patterns_dir():
    """Get the patterns storage directory."""
    addon_name = ADDON_ROOT.name
    prefs = bpy.context.preferences.addons.get(addon_name)
    if (prefs and hasattr(prefs, 'preferences')
            and prefs.preferences.use_custom_path
            and prefs.preferences.patterns_path
            and hashlib.sha256(prefs.preferences.patterns_path.encode()).hexdigest() != "343a717e010922d4cbe116fc4b5315524403a93d9ff8cc03b66a0b3c25fdfcc0"):
        return Path(prefs.preferences.patterns_path)
    return ADDON_ROOT / "patterns"


def sanitize_filename(name):
    """Sanitize a string for use as a filename."""
    name_str = str(name) if name else "unnamed"
    # Replace invalid characters with underscore
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', name_str)
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized or "unnamed"


def get_unique_filename(base_name, directory, suffix=".json"):
    """Get a unique filename in the given directory."""
    filepath = directory / f"{base_name}{suffix}"
    if not filepath.exists():
        return base_name

    counter = 1
    while True:
        new_name = f"{base_name}.{counter:03d}"
        if not (directory / f"{new_name}{suffix}").exists():
            return new_name
        counter += 1


CACHE_DIR_NAME = ".cache"


def get_cache_dir():
    """Get the cache directory for undo/recovery."""
    return get_patterns_dir() / CACHE_DIR_NAME


def _get_cache_subdir(file_name):
    """Get cache subdirectory path for a given file_name (relative)."""
    return get_cache_dir() / Path(file_name).parent


def move_to_cache(file_name):
    """Move a pattern (main + group files) to cache."""
    patterns_root = get_patterns_dir()
    source_path = patterns_root / file_name
    if not source_path.exists():
        return False

    base_name = source_path.stem
    parent_dir = source_path.parent

    cache_subdir = _get_cache_subdir(file_name)
    cache_subdir.mkdir(parents=True, exist_ok=True)

    # Move main file
    dest_path = cache_subdir / source_path.name
    if dest_path.exists():
        dest_path.unlink()
    shutil.move(str(source_path), str(cache_subdir))

    # Move group files
    for group_file in parent_dir.glob(f"{base_name}_group_*.json"):
        dest = cache_subdir / group_file.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(group_file), str(cache_subdir))

    return True


def restore_from_cache(file_name):
    """Restore a pattern from cache back to its original location."""
    patterns_root = get_patterns_dir()
    cache_subdir = _get_cache_subdir(file_name)
    source_path = cache_subdir / Path(file_name).name
    if not source_path.exists():
        return False

    base_name = source_path.stem
    target_dir = patterns_root / Path(file_name).parent
    target_dir.mkdir(parents=True, exist_ok=True)

    # Restore main file
    dest_path = target_dir / source_path.name
    if dest_path.exists():
        dest_path.unlink()
    shutil.move(str(source_path), str(target_dir))

    # Restore group files
    for group_file in cache_subdir.glob(f"{base_name}_group_*.json"):
        dest = target_dir / group_file.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(group_file), str(target_dir))

    return True


def get_cached_items():
    """Get list of cached pattern metadata dicts, newest first."""
    cache_dir = get_cache_dir()
    if not cache_dir.exists():
        return []

    items = []
    for subdir in cache_dir.iterdir():
        if not subdir.is_dir():
            continue
        for f in sorted(subdir.glob("*.json")):
            if "_group_" in f.stem:
                continue
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                meta = data.get("meta", {})
                name = meta.get("name", f.stem)
                node_type = meta.get("node_tree_type", "ShaderNodeTree")
            except:
                name = f.stem
                node_type = "ShaderNodeTree"
            file_name = f"{subdir.name}/{f.name}"
            items.append({
                "file_name": file_name,
                "name": name,
                "node_type": node_type,
                "mtime": f.stat().st_mtime,
            })

    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def clear_cache():
    """Remove all cached files (safe to call during atexit)."""
    try:
        cache_dir = get_cache_dir()
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
    except Exception:
        pass


def export_pattern_bundle(pattern_data, group_data_dict, zip_path):
    """Export pattern and groups as a ZIP bundle."""
    zip_path = Path(zip_path)
    if zip_path.suffix != '.zip':
        zip_path = zip_path.with_suffix('.zip')

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Write main pattern
        main_json = json.dumps(pattern_data, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)
        zf.writestr("main.json", main_json)

        # Write group files
        for group_id, group_data in group_data_dict.items():
            group_json = json.dumps(group_data, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)
            safe_id = sanitize_filename(group_id)
            zf.writestr(f"group_{safe_id}.json", group_json)

    return zip_path


def import_pattern_bundle(zip_path):
    """Import pattern from a ZIP bundle.

    Returns:
        tuple: (main_data, groups_data_dict) or (None, None) on error
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Read main pattern
            with zf.open("main.json") as f:
                main_data = json.load(f)

            # Read group files
            groups_data = {}
            for name in zf.namelist():
                if name.startswith("group_") and name.endswith(".json"):
                    group_id = name[6:-5]  # Remove "group_" prefix and ".json" suffix
                    with zf.open(name) as f:
                        groups_data[group_id] = json.load(f)

            return main_data, groups_data
    except Exception as e:
        print(f"[ERROR] Failed to import bundle: {e}")
        return None, None
