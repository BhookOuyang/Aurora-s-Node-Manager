# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""File utilities for pattern storage."""
import hashlib
import io
import json
import re
import zipfile
import tempfile
import shutil
from pathlib import Path

import bpy

from .translations import tr
from . import logger


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
        if isinstance(obj, bytes):
            import base64
            return {"__bytes__": True, "data": base64.b64encode(obj).decode('ascii')}
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

    # Compact transport format (produced by the clipboard codec): decompress it
    # back into the full bundle / single-pattern dict before validating.
    from ..core.codec import is_compact, decode as codec_decode
    if is_compact(data):
        try:
            data = codec_decode(text)
        except Exception as e:
            return _result(False, error=f"Failed to decompress clipboard: {e}")
        if not isinstance(data, dict):
            return _result(False, error="Decompressed clipboard content must be a JSON object")


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


def get_addon_preferences():
    """Get the addon preferences object, or None if unavailable."""
    try:
        prefs = bpy.context.preferences.addons.get(ADDON_ROOT.name)
        if prefs and hasattr(prefs, 'preferences'):
            return prefs.preferences
    except Exception:
        pass
    return None


def get_patterns_dir():
    """Get the patterns storage directory."""
    addon_name = ADDON_ROOT.name
    try:
        prefs = bpy.context.preferences.addons.get(addon_name)
        if (prefs and hasattr(prefs, 'preferences')
                and prefs.preferences.use_custom_path
                and prefs.preferences.patterns_path
                and hashlib.sha256(prefs.preferences.patterns_path.encode()).hexdigest() != "343a717e010922d4cbe116fc4b5315524403a93d9ff8cc03b66a0b3c25fdfcc0"):
            return Path(prefs.preferences.patterns_path)
    except Exception:
        pass
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


LOCAL_PATHS_FIELD = "file_paths"


def strip_local_paths(pattern_data):
    """Remove local file path data from a pattern for sharing.

    Deletes the 'file_paths' special field (absolute paths of referenced
    files) from every node. The reference name (e.g. 'image') is kept.
    """
    if not isinstance(pattern_data, dict):
        return pattern_data
    for node in pattern_data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        special = node.get("special")
        if isinstance(special, dict) and LOCAL_PATHS_FIELD in special:
            special.pop(LOCAL_PATHS_FIELD, None)
    return pattern_data



# Resource packing / scanning.


RESOURCES_ARCHIVE_NAME = "resources.aurpak"
RESOURCES_MANIFEST = "manifest.json"
RESOURCE_TOKEN_PREFIX = "@resource:"

# Pure-data file types a node pattern legitimately references.
WHITELIST_EXTS = {
    'png', 'jpg', 'jpeg', 'bmp', 'tga', 'tif', 'tiff', 'exr', 'hdr',
    'webp', 'dds', 'avif', 'gif',
    'ies',
    'mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', 'mpeg', 'mpg',
    'wav', 'mp3', 'ogg', 'flac', 'aiff', 'aif',
    'obj', 'stl', 'ply', 'csv', 'txt', 'vdb',
}

# File types that must never appear in a shared pattern.
BLACKLIST_EXTS = {
    'py', 'pyc', 'pyo', 'pyd', 'blender', 'blend', 'dll', 'so', 'dylib',
    'exe', 'bat', 'cmd', 'com', 'scr', 'vbs', 'ps1', 'sh', 'elf', 'apk',
    'msi', 'js', 'jse', 'jar', 'class', 'cpl', 'ws', 'msc', 'rb', 'pl',
    'php', 'lnk', 'url', 'hta', 'reg', 'pif', 'gadget', 'app',
}

# Special: not blacklisted, but must be reported (shader source can cause crash).
REPORT_EXTS = {'osl', 'oso'}

# Zip-bomb guards (authoritative gate = actual bytes streamed during read).
MAX_ENTRY_UNCOMPRESSED = 1 << 30            # 1 GiB per resource entry
MAX_TOTAL_UNCOMPRESSED = 4 << 30            # 4 GiB total
MAX_ENTRIES = 10000
MAX_JSON_BYTES = 100 * 1024 * 1024          # 100 MiB for main/group json


# (offset, magic, type) rules matched by LONGEST prefix (offset + len).
_MAGIC_RULES = (
    (0, b'\x89PNG\r\n\x1a\n', 'png'),
    (0, b'\xff\xd8\xff', 'jpg'),
    (0, b'BM', 'bmp'),
    (0, b'GIF8', 'gif'),
    (0, b'II*\x00', 'tif'),
    (0, b'MM\x00*', 'tif'),
    (0, b'RIFF', 'riff'),
    (8, b'WAVE', 'wav'),
    (8, b'AVI ', 'avi'),
    (0, b'FORM', 'form'),
    (8, b'AIFF', 'aiff'),
    (8, b'AIFC', 'aiff'),
    (4, b'ftyp', 'mp4'),
    (8, b'avif', 'avif'),
    (8, b'WEBP', 'webp'),
    (0, b'ID3', 'mp3'),
    (0, b'OggS', 'ogg'),
    (0, b'fLaC', 'flac'),
    (0, b'\x1aE\xdf\xa3', 'mkv'),
    (0, b'\x00\x00\x01\xb8', 'mpeg'),
    (0, b'\x76\x2f\x31\x01', 'exr'),
    (0, b'\x76\x2f\x31\x02', 'exr'),
    (0, b'#?RADIANCE', 'hdr'),
    (0, b'#?RGBE', 'hdr'),
    (0, b'DDS ', 'dds'),
    (0, b'IESNA', 'ies'),
    (0, b'TAGEN', 'ies'),
    (0, b'ply\n', 'ply'),
    (0, b'ply\r\n', 'ply'),
    (0, b'VDB ', 'vdb'),
    (0, b'MZ', 'pe'),
    (0, b'\x7fELF', 'elf'),
    (0, b'#!', 'script'),
    (0, b'PK\x03\x04', 'zip'),
)


def sniff_file_type(head):
    """Classify a file's real type from its magic bytes (content, not name).

    Rules are matched by longest prefix so a specific signature (e.g. ISO
    BMFF ``ftyp``+``avif``) wins over the generic ``ftyp``. Returns a
    canonical lowercase type key, or None if unrecognised.
    """
    if not head:
        return None
    best = None
    best_cover = -1
    for offset, magic, type_key in _MAGIC_RULES:
        if len(head) < offset + len(magic):
            continue
        if head[offset:offset + len(magic)] != magic:
            continue
        cover = offset + len(magic)
        if cover > best_cover:
            best, best_cover = type_key, cover
    if best is not None:
        return best
    # MP3 frame-sync fallback (no fixed magic).
    if len(head) > 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return 'mp3'
    return None


def classify_resource(name, size, sniffed):
    """Classify a resource entry as 'whitelist', 'report' or 'blacklist'.

    Content sniffing takes priority over the entry name so a file named
    ``image.png`` that is really an executable is caught.
    """
    ext = Path(name).suffix.lower().lstrip('.')
    sniffed = (sniffed or '').lower()

    if sniffed in ('pe', 'elf', 'script'):
        return 'blacklist'
    if ext in BLACKLIST_EXTS:
        return 'blacklist'
    if ext in REPORT_EXTS:
        return 'report'
    if ext in WHITELIST_EXTS:
        if sniffed and sniffed not in WHITELIST_EXTS:
            return 'report'
        return 'whitelist'
    if sniffed in WHITELIST_EXTS:
        return 'whitelist'
    return 'report'


def _collect_referenced_paths(pattern_data, group_data_dict):
    """Collect every referenced absolute path across main + group data."""
    paths = set()
    for data in [pattern_data, *group_data_dict.values()]:
        for node in data.get("nodes", []):
            special = node.get("special")
            if isinstance(special, dict) and isinstance(special.get(LOCAL_PATHS_FIELD), dict):
                for v in special[LOCAL_PATHS_FIELD].values():
                    if v:
                        paths.add(str(v))
    return paths


def pack_resources(paths, warnings):
    """Bundle validated resource files into an in-memory ``resources.aurpak``.

    Returns ``(archive_bytes, token_map)`` where ``archive_bytes`` is the
    packaged ``resources.aurpak`` content (or ``None`` when no valid resource
    was packed) and ``token_map`` maps the original absolute path to the
    packaged resource filename. Invalid or missing files are skipped (their
    paths never leak) and appended to ``warnings``.
    """
    entries = []
    manifest = {}
    token_map = {}
    seen = set()
    for i, path in enumerate(sorted(paths)):
        if not path or path in seen:
            continue
        seen.add(path)
        p = Path(path)
        if not p.is_file():
            warnings.append(tr("Referenced file missing, removed: {}").format(p.name))
            continue
        ext = p.suffix.lower().lstrip('.')
        if not ext or (ext not in WHITELIST_EXTS and ext not in REPORT_EXTS):
            label = tr("{} (unknown type)").format(p.name) if not ext else f"{p.name} (.{ext})"
            warnings.append(tr("Unsupported file type, removed: {}").format(label))
            continue
        try:
            with open(p, 'rb') as f:
                data = f.read()
        except Exception:
            warnings.append(tr("Failed to read referenced file, removed: {}").format(p.name))
            continue
        if ext not in REPORT_EXTS:
            # osl/oso are packed as-is (no content checks).
            sniffed = sniff_file_type(data[:32])
            if sniffed in ('pe', 'elf', 'script') or (sniffed and sniffed not in WHITELIST_EXTS):
                warnings.append(tr("Referenced file structure anomaly, removed: {}").format(p.name))
                continue

        stem = sanitize_filename(p.stem)[:40]
        fname = f"{i:04d}_{stem}.{ext}"
        entries.append((fname, data))
        manifest[fname] = {
            "type": ext,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
        token_map[path] = fname

    if not entries:
        return None, token_map
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(RESOURCES_MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False))
        for fname, data in entries:
            zf.writestr(fname, data)
    return buf.getvalue(), token_map


def _rewrite_paths_to_tokens(pattern_data, token_map):
    """Replace absolute paths with ``@resource:`` tokens; drop non-packed ones."""
    for node in pattern_data.get("nodes", []):
        special = node.get("special")
        if not isinstance(special, dict):
            continue
        fp = special.get(LOCAL_PATHS_FIELD)
        if not isinstance(fp, dict):
            continue
        new_fp = {}
        for attr, path in fp.items():
            fname = token_map.get(str(path))
            if fname:
                new_fp[attr] = RESOURCE_TOKEN_PREFIX + fname
        if new_fp:
            special[LOCAL_PATHS_FIELD] = new_fp
        else:
            special.pop(LOCAL_PATHS_FIELD, None)
    return pattern_data


def inject_resource_paths(pattern_data, extract_map):
    """Replace ``@resource:`` tokens with the extracted absolute paths."""
    for node in pattern_data.get("nodes", []):
        special = node.get("special")
        if not isinstance(special, dict):
            continue
        fp = special.get(LOCAL_PATHS_FIELD)
        if not isinstance(fp, dict):
            continue
        new_fp = {}
        for attr, val in fp.items():
            val = str(val)
            if val.startswith(RESOURCE_TOKEN_PREFIX):
                fname = val[len(RESOURCE_TOKEN_PREFIX):]
                target = extract_map.get(fname)
                if target:
                    new_fp[attr] = target
            else:
                new_fp[attr] = val
        if new_fp:
            special[LOCAL_PATHS_FIELD] = new_fp
        else:
            special.pop(LOCAL_PATHS_FIELD, None)
    return pattern_data


def validate_json_paths(main_data, groups_data):
    """Check that every ``file_paths`` value is a ``@resource:`` token.

    A non-token value (e.g. a leaked absolute path) means we cannot tell
    which packaged resource it should reference.

    Returns ``(issues, has_tokens)``.
    """
    issues = []
    has_tokens = False
    for data in [main_data, *(groups_data or {}).values()]:
        for node in data.get("nodes", []):
            special = node.get("special")
            if not isinstance(special, dict):
                continue
            fp = special.get(LOCAL_PATHS_FIELD)
            if not isinstance(fp, dict):
                continue
            for attr, val in fp.items():
                val = str(val)
                if val.startswith(RESOURCE_TOKEN_PREFIX):
                    has_tokens = True
                else:
                    issues.append(f"{attr}: {val}")
    return issues, has_tokens


def _read_json_member(zf, name):
    """Read a JSON zip member, rejecting oversized payloads."""
    info = zf.getinfo(name)
    if info.file_size > MAX_JSON_BYTES:
        raise ValueError(tr("{} too large").format(name))
    with zf.open(name) as f:
        return json.load(f)


def _stream_member_to_temp(outer_zip_path, member_name):
    """Stream a zip member to a temp file (disk, bounded memory)."""
    tmp = tempfile.NamedTemporaryFile(prefix="aurpak_", suffix=".bin", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        with zipfile.ZipFile(outer_zip_path, 'r') as zf, \
                zf.open(member_name) as src, open(tmp_path, 'wb') as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise
    return tmp_path


def _check_zip_bomb(zip_path):
    """Header-only heuristic pre-check (no decompression). Returns (ok, reason)."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ENTRIES:
                return False, tr("Too many entries ({})").format(len(infos))
            total = 0
            for info in infos:
                if info.file_size > MAX_ENTRY_UNCOMPRESSED:
                    return False, tr("Entry decompressed size exceeds limit: {}").format(info.filename)
                total += info.file_size
                if total > MAX_TOTAL_UNCOMPRESSED:
                    return False, tr("Total decompressed size exceeds limit")
    except Exception as e:
        return False, tr("Failed to read resource pack: {}").format(e)
    return True, ""


def _hash_member(zf, name):
    """Stream a member's decompressed bytes; return (digest, size)."""
    h = hashlib.sha256()
    size = 0
    with zf.open(name) as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_ENTRY_UNCOMPRESSED:
                raise ValueError(tr("{} decompressed size exceeds limit").format(name))
            h.update(chunk)
    return h.hexdigest(), size


def _peek_head(zf, name, n=32):
    """Read the first ``n`` decompressed bytes of a member."""
    with zf.open(name) as f:
        return f.read(n)


def _copy_verify_member(zf, name, dest_path, expected_sha):
    """Stream one member to disk, hashing and enforcing caps as we go."""
    h = hashlib.sha256()
    size = 0
    with zf.open(name) as src, open(dest_path, 'wb') as dst:
        while True:
            chunk = src.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_ENTRY_UNCOMPRESSED:
                raise ValueError(tr("{} decompressed size exceeds limit").format(name))
            h.update(chunk)
            dst.write(chunk)
    if h.hexdigest() != expected_sha:
        raise ValueError(tr("{} verification failed").format(name))


def scan_resources(inner_zip_path):
    """Classify every resource inside the pack zip (read from a temp file on disk).

    Returns a dict:
        tamper (bool)   structural mismatch / unreadable / sha mismatch / oversize
        entries (list)  [{name, size, tier, sniffed, sha_valid}]
        manifest (dict or None)
    """
    result = {"tamper": False, "entries": [], "manifest": None}
    try:
        with zipfile.ZipFile(inner_zip_path, 'r') as inner:
            names = inner.namelist()
            manifest = None
            if RESOURCES_MANIFEST in names:
                try:
                    raw = inner.read(RESOURCES_MANIFEST)
                    if len(raw) > MAX_JSON_BYTES:
                        result["tamper"] = True
                    else:
                        manifest = json.loads(raw.decode('utf-8'))
                except Exception:
                    result["tamper"] = True
            if not isinstance(manifest, dict):
                result["tamper"] = True
                manifest = None

            for name in names:
                if name == RESOURCES_MANIFEST:
                    continue
                entry = {
                    "name": name,
                    "size": 0,
                    "tier": classify_resource(name, 0, None),
                    "sniffed": None,
                    "sha_valid": False,
                }
                try:
                    entry["sniffed"] = sniff_file_type(_peek_head(inner, name))
                    entry["tier"] = classify_resource(name, 0, entry["sniffed"])
                except Exception:
                    result["tamper"] = True
                expected = manifest.get(name) if manifest is not None else None
                try:
                    if not isinstance(expected, dict) or not isinstance(expected.get("sha256"), str):
                        result["tamper"] = True
                    else:
                        digest, size = _hash_member(inner, name)
                        entry["size"] = size
                        entry["sha_valid"] = (digest == expected["sha256"])
                        if not entry["sha_valid"]:
                            result["tamper"] = True
                except Exception:
                    result["tamper"] = True
                result["entries"].append(entry)

            if manifest is not None:
                for mname in manifest:
                    if mname not in names:
                        result["tamper"] = True

            result["manifest"] = manifest
    except Exception:
        result["tamper"] = True
    return result


def extract_resources(inner_zip_path, dest_dir, manifest, extra_extract=None):
    """Extract validated resources from the pack zip into ``dest_dir`` (flat).

    ``extra_extract`` is a set of tiers beyond whitelist that may be written
    (e.g. {'report'} or {'report', 'blacklist'}) — set by the operator only
    when the user chose to keep those unexpected files. Entries that fail sha
    integrity are never written (treated as tampered).

    Returns ``(extract_map, warnings, integrity_skipped)``.
    """
    extra_extract = extra_extract or set()
    extract_map = {}
    warnings = []
    integrity_skipped = 0
    dest_dir = Path(dest_dir)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return extract_map, [tr("Cannot create directory: {} ({})").format(dest_dir, e)], 0

    try:
        inner = zipfile.ZipFile(inner_zip_path, 'r')
    except Exception as e:
        return extract_map, [tr("Failed to read resource pack: {}").format(e)], 0

    with inner:
        for name in inner.namelist():
            if name == RESOURCES_MANIFEST:
                continue
            if name != Path(name).name or '..' in name:
                warnings.append(tr("Abnormal resource path, not extracted: {}").format(name))
                continue
            expected = manifest.get(name) if manifest else None
            if not isinstance(expected, dict) or not isinstance(expected.get("sha256"), str):
                warnings.append(tr("Content integrity anomaly (not in manifest), deleted: {}").format(name))
                integrity_skipped += 1
                continue

            sniffed = None
            tier = 'report'
            try:
                sniffed = sniff_file_type(_peek_head(inner, name))
                tier = classify_resource(name, 0, sniffed)
            except Exception:
                warnings.append(tr("Failed to read resource, deleted: {}").format(name))
                integrity_skipped += 1
                continue
            if tier != 'whitelist' and tier not in extra_extract:
                label = tr("Risky file type") if tier == 'blacklist' else tr("Unexpected resource type")
                warnings.append(tr("{}, deleted: {}").format(label, name))
                continue

            target = dest_dir / name
            try:
                _copy_verify_member(inner, name, target, expected["sha256"])
            except Exception as e:
                try:
                    target.unlink()
                except OSError:
                    pass
                warnings.append(tr("Content integrity anomaly (possibly tampered), deleted: {}").format(name))
                integrity_skipped += 1
                continue
            extract_map[name] = str(target.resolve())
    return extract_map, warnings, integrity_skipped


def export_pattern_bundle(pattern_data, group_data_dict, bundle_path, use_pack_resources=False):
    """Export pattern and groups as an .aurpak bundle (ZIP container).

    When ``use_pack_resources`` is True, referenced resource files are
    validated and packed into ``resources.aurpak``; every absolute path is
    replaced with a ``@resource:`` token so no absolute path ever leaves the
    machine. Otherwise local paths are stripped (share-safe).

    Returns ``(bundle_path, warnings)``.
    """
    bundle_path = Path(bundle_path)
    if bundle_path.suffix != '.aurpak':
        bundle_path = bundle_path.with_suffix('.aurpak')

    warnings = []
    archive_bytes = b''
    token_map = {}

    if use_pack_resources:
        paths = _collect_referenced_paths(pattern_data, group_data_dict)
        archive_bytes, token_map = pack_resources(paths, warnings)
        _rewrite_paths_to_tokens(pattern_data, token_map)
        for group_data in group_data_dict.values():
            _rewrite_paths_to_tokens(group_data, token_map)
    else:
        strip_local_paths(pattern_data)
        for group_data in group_data_dict.values():
            strip_local_paths(group_data)

    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        main_json = json.dumps(pattern_data, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)
        zf.writestr("main.json", main_json)

        for group_id, group_data in group_data_dict.items():
            group_json = json.dumps(group_data, indent=2, ensure_ascii=False, cls=AuroraJSONEncoder)
            safe_id = sanitize_filename(group_id)
            zf.writestr(f"group_{safe_id}.json", group_json)

        if archive_bytes:
            zf.writestr(RESOURCES_ARCHIVE_NAME, archive_bytes)

    return bundle_path, warnings


def import_pattern_bundle(bundle_path):
    """Import pattern from an .aurpak or .zip bundle.

    Returns:
        tuple: (main_data, groups_data_dict, resources)

        ``resources`` is None when the bundle has no resource archive and no
        unexpected members, else a dict:
            present (bool)      whether ``resources.aurpak`` exists
            outer_tamper (bool) unexpected members found in the outer zip
            foreign (list)      names of unexpected outer members
            file_count (int)    resource files inside the archive
            total_size (int)    combined size of the resource files
            inner_path (str|None) temp-file path of the streamed pack
            bomb (bool)         pack exceeded the size/entry pre-checks
            bomb_reason (str)   reason when ``bomb`` is True
    """
    try:
        with zipfile.ZipFile(bundle_path, 'r') as zf:
            names = set(zf.namelist())
            if "main.json" not in names:
                return None, None, None

            main_data = _read_json_member(zf, "main.json")

            groups_data = {}
            for name in zf.namelist():
                if name.startswith("group_") and name.endswith(".json"):
                    group_id = name[6:-5]
                    groups_data[group_id] = _read_json_member(zf, name)

            foreign = [
                n for n in names
                if n not in (RESOURCES_ARCHIVE_NAME, "main.json")
                and not (n.startswith("group_") and n.endswith(".json"))
            ]

            res = None
            if RESOURCES_ARCHIVE_NAME in names:
                inner_path = None
                bomb = False
                bomb_reason = ""
                file_count = 0
                total_size = 0
                try:
                    inner_path = _stream_member_to_temp(bundle_path, RESOURCES_ARCHIVE_NAME)
                    ok, reason = _check_zip_bomb(inner_path)
                    if not ok:
                        bomb = True
                        bomb_reason = reason
                    else:
                        with zipfile.ZipFile(inner_path, 'r') as inner:
                            for info in inner.infolist():
                                if info.filename != RESOURCES_MANIFEST:
                                    file_count += 1
                                    total_size += info.file_size
                except Exception:
                    if inner_path is not None:
                        try:
                            Path(inner_path).unlink()
                        except OSError:
                            pass
                        inner_path = None
                res = {
                    "present": True,
                    "outer_tamper": bool(foreign),
                    "foreign": foreign,
                    "file_count": file_count,
                    "total_size": total_size,
                    "inner_path": str(inner_path) if inner_path else None,
                    "bomb": bomb,
                    "bomb_reason": bomb_reason,
}
            elif foreign:
                res = {
                    "present": False,
                    "outer_tamper": True,
                    "foreign": foreign,
                    "file_count": 0,
                    "total_size": 0,
                    "inner_path": None,
                    "bomb": False,
                    "bomb_reason": "",
                }
            
            return main_data, groups_data, res
    except Exception as e:
        logger.error(f"Failed to import bundle: {e}")
        return None, None, None
