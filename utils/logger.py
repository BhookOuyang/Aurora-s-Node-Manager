# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""Session log engine with code location, full stack traces, and API/type mismatch detection.

Writes one log file per Blender session (``aurora_YYYY-MM-DD_HHMMSS.log``)
into the addon log directory (custom preference, or the user scripts folder).

Features:
  * Code location (file:line:func) on every log line
  * Full stack traces on errors and unhandled exceptions
  * API/type mismatch detection (return type, property type, deprecated API)
  * Automatic snapshots: brief on success, full on error
  * sys.excepthook covers unhandled exceptions outside operators
"""

import os
import sys
import time
import traceback
import re
from datetime import datetime
from pathlib import Path

import bpy

_original_excepthook = None
_session_path = None
_session_file = None

_LOG_PREFIX = "aurora_"
_MAX_SNAPSHOT_NODES = 10
_MAX_ARG_LEN = 120

# Patterns for API/type mismatch detection
_API_MISMATCH_PATTERNS = [
    (re.compile(r"return value must be None"), "operator_return_type"),
    (re.compile(r"expected (?:a )?(\w+) argument"), "type_mismatch"),
    (re.compile(r"takes (\d+) positional argument"), "api_signature"),
    (re.compile(r"got unexpected keyword argument"), "api_signature"),
    (re.compile(r"has no attribute"), "deprecated_api"),
    (re.compile(r"module 'bpy' has no attribute"), "deprecated_api"),
    (re.compile(r"expected (?:a )?float"), "type_mismatch"),
    (re.compile(r"expected (?:an? )?int"), "type_mismatch"),
    (re.compile(r"expected (?:a )?bool"), "type_mismatch"),
    (re.compile(r"expected (?:a )?str"), "type_mismatch"),
    (re.compile(r"unexpected type"), "type_mismatch"),
    (re.compile(r"type mismatch"), "type_mismatch"),
    (re.compile(r"incompatible type"), "type_mismatch"),
]


def _detect_issue_type(exc_text: str) -> str:
    """Detect issue type from exception text."""
    for pattern, issue_type in _API_MISMATCH_PATTERNS:
        if pattern.search(exc_text):
            return issue_type
    return "unknown"


# ---------------------------------------------------------------------------
# Directory / session file
# ---------------------------------------------------------------------------
def log_dir():
    """Resolve the active log directory (custom preference or default)."""
    import bpy
    prefs_path = ""
    try:
        addon = bpy.context.preferences.addons.get(__package__.split('.')[0])
        if addon is not None and hasattr(addon, 'preferences'):
            prefs_path = getattr(addon.preferences, 'log_directory', "") or ""
    except Exception:
        pass
    if prefs_path:
        try:
            return Path(prefs_path)
        except Exception:
            pass
    try:
        return Path(bpy.utils.user_resource('SCRIPTS')) / "aurora_logs"
    except Exception:
        return Path.home() / "aurora_logs"


def log_dir_str():
    """Human-readable current log directory."""
    try:
        return str(log_dir())
    except Exception:
        return ""


def _close_session():
    global _session_file, _session_path
    try:
        if _session_file is not None:
            _session_file.close()
    except Exception:
        pass
    _session_file = None
    _session_path = None


def _ensure_session():
    """Open (or reopen after directory change) the per-session log file."""
    global _session_file, _session_path
    try:
        d = log_dir()
        if _session_path is not None and _session_path.parent == d and _session_file is not None:
            return _session_path
        _close_session()
        d.mkdir(parents=True, exist_ok=True)
        name = time.strftime(f"{_LOG_PREFIX}%Y-%m-%d_%H%M%S.log")
        _session_path = d / name
        _session_file = open(_session_path, "a", encoding="utf-8", newline="\n")
        return _session_path
    except Exception:
        _close_session()
        return None


def _write(level, text):
    """Write a log line with code location prefix."""
    try:
        p = _ensure_session()
        if p is None or _session_file is None:
            return
        # Extract code location from caller stack (skip logger internals)
        frame = sys._getframe(1)
        loc = ""
        while frame:
            filename = frame.f_code.co_filename
            funcname = frame.f_code.co_name
            if not (filename.endswith(('logger.py', '<string>')) or funcname.startswith('_')):
                fname = Path(filename).name
                loc = f"[{fname}:{frame.f_lineno}:{funcname}]"
                break
            frame = frame.f_back
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.")
        ts += f"{datetime.now().microsecond // 1000:03d}"
        prefix = f"[{ts}] [{level}]"
        if loc:
            prefix += f" {loc}"
        _session_file.write(f"{prefix} {text}\n")
        _session_file.flush()
        # Also print to console for debugging
        print(f"{prefix} {text}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------
def _node_tree_name(context):
    try:
        space = getattr(context, 'space_data', None)
        if space is None:
            return ""
        nt = getattr(space, 'node_tree', None)
        if nt is None:
            return ""
        return f"{nt.name}({nt.bl_idname})"
    except Exception:
        return ""


def _plugin_version():
    try:
        from .. import bl_info
        return ".".join(str(v) for v in (bl_info.get("version") or ()))
    except Exception:
        return "?"


def _snapshot_args(operator):
    """Collect operator input args (scrub passwords and path locations)."""
    out = []
    ann = getattr(operator, '__annotations__', None) or {}
    for key in ann:
        try:
            if key.startswith('_'):
                continue
            prop = ann[key]
            if getattr(prop, 'subtype', '') == 'PASSWORD':
                continue
            value = getattr(operator, key, None)
            if value is None or isinstance(value, (list, dict, tuple, set)):
                continue
            if isinstance(value, (bool, int, float)):
                out.append(f"{key}={value}")
                continue
            if not isinstance(value, str):
                continue
            s = value
            if len(s) > _MAX_ARG_LEN:
                s = s[:_MAX_ARG_LEN] + "..."
            if '/' in s or '\\' in s:
                name = os.path.basename(s.replace('\\', '/'))
                ext = os.path.splitext(name)[1].lstrip('.')
                out.append(f"{key}='{name}' (type='{ext}')")
            else:
                out.append(f"{key}={s!r}")
        except Exception:
            continue
    return out


def _brief_snapshot(operator, context, elapsed_ms):
    try:
        op = getattr(operator, 'bl_idname', '?')
        tree = _node_tree_name(context)
        return f"operator={op} node_tree='{tree}' elapsed={elapsed_ms:.1f}ms"
    except Exception as e:
        return f"operator=? (snapshot failed: {e})"


def _full_snapshot(operator, context):
    try:
        op = getattr(operator, 'bl_idname', '?')
        tree = _node_tree_name(context)
        area = ""
        try:
            area_obj = getattr(context, 'area', None)
            area = area_obj.type if area_obj is not None else ""
        except Exception:
            area = ""
        import bpy
        blender_ver = ".".join(str(v) for v in bpy.app.version)
        lines = [f"operator={op} node_tree='{tree}' area={area} "
                 f"blender={blender_ver} plugin={_plugin_version()}"]

        nodes = []
        try:
            space = getattr(context, 'space_data', None)
            nt = getattr(space, 'node_tree', None) if space is not None else None
            if nt is not None:
                for n in nt.nodes:
                    if getattr(n, 'select', False):
                        nodes.append(f"{n.bl_idname}[{n.label or n.name}]")
                        if len(nodes) >= _MAX_SNAPSHOT_NODES:
                            break
        except Exception:
            pass
        if nodes:
            lines.append("selected: " + ", ".join(nodes))

        args = _snapshot_args(operator)
        if args:
            lines.append("args: " + " ".join(args))
        return "\n  ".join(lines)
    except Exception as e:
        return f"operator={getattr(operator, 'bl_idname', '?')} (snapshot failed: {e})"


# ---------------------------------------------------------------------------
# Public log API
# ---------------------------------------------------------------------------
def info(msg, operator=None, context=None, elapsed_ms=0.0):
    try:
        _write("INFO", f"{msg} :: {_brief_snapshot(operator, context, elapsed_ms or 0.0)}")
    except Exception:
        pass


def warning(msg, operator=None, context=None):
    try:
        _write("WARN", f"{msg} :: {_brief_snapshot(operator, context, 0.0)}")
    except Exception:
        pass


def error(msg, operator=None, context=None, exc=None, data=None):
    """Record an error with full snapshot, stack trace, and issue type detection."""
    try:
        snap = _full_snapshot(operator, context)
        lines = [str(msg), "  " + snap]
        if data is not None:
            lines.append("  data: " + str(data)[:800])

        exc_text = ""
        if exc:
            if exc is True:
                tb_lines = traceback.format_exc().splitlines()
            else:
                tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
            exc_text = "\n".join(tb_lines)
            lines.append(exc_text.rstrip())
            # Detect issue type
            issue_type = _detect_issue_type(exc_text)
            if issue_type != "unknown":
                lines.append(f"  [issue_type={issue_type}]")
        _write("ERROR", "\n".join(lines))
    except Exception:
        pass


def exception(msg, operator=None, context=None, data=None):
    """Convenience: log current exception with full traceback."""
    error(msg, operator, context, exc=True, data=data)


# ---------------------------------------------------------------------------
# Operator guard
# ---------------------------------------------------------------------------
def safe_operator(cls):
    """Wrap an operator class: log crashes (full snapshot) and successes (brief
    snapshot); forward every ``report`` message into the log.

    Uses class-level monkey patching for `report` (compatible with Blender 3.6–5.2+).
    """
    orig_execute = getattr(cls, 'execute', None)
    if orig_execute is None:
        return cls

    # Get the original report from the parent class (bpy.types.Operator)
    # Subclasses don't have 'report' directly; it's on the base class.
    orig_report = getattr(bpy.types.Operator, 'report', None)
    if orig_report is None:
        # Fallback: try to get from MRO
        for base in cls.__mro__:
            if 'report' in base.__dict__:
                orig_report = base.__dict__['report']
                break
    if orig_report is None:
        # No report method found, skip patching
        return cls

    def wrapped_report(self, rtype, msg):
        try:
            # Use bpy.context (available during operator execution)
            import bpy
            ctx = bpy.context
            if rtype == {'ERROR'}:
                error(f"[report] {msg}", self, ctx)
            elif rtype == {'WARNING'}:
                warning(f"[report] {msg}", self, ctx)
            elif rtype == {'INFO'}:
                info(f"[report] {msg}", self, ctx)
        except Exception:
            pass
        return orig_report(self, rtype, msg)

    # Replace the class method once (works on all Blender versions)
    cls.report = wrapped_report

    def execute(self, context):
        t0 = time.perf_counter()
        try:
            result = orig_execute(self, context)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if isinstance(result, set) and ('FINISHED' in result or 'RUNNING_MODAL' in result):
                info("operator finished", self, context, elapsed)
            elif result is not None and not isinstance(result, set):
                # Detect wrong return type
                warning(f"operator returned {type(result).__name__}, expected set/None", self, context)
            return result
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000.0
            error(f"Operator {getattr(self, 'bl_idname', '?')} crashed",
                  self, context, exc=e, data={"elapsed_ms": round(elapsed, 1)})
            try:
                # Use the class-level wrapped report (which calls orig_report internally)
                self.report({'ERROR'}, "Internal error, details written to the log file")
            except Exception:
                pass
            return {'CANCELLED'}

    cls.execute = execute
    return cls


# ---------------------------------------------------------------------------
# Unhandled exception hook
# ---------------------------------------------------------------------------
def _handle_excepthook(etype, value, tb):
    try:
        # Use the passed traceback, NOT format_exc() which only works in except blocks
        tb_text = "".join(traceback.format_exception(etype, value, tb))
        error(f"Unhandled exception: {etype.__name__}: {value}", exc=tb_text)
    except Exception:
        pass
    if _original_excepthook is not None:
        try:
            _original_excepthook(etype, value, tb)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Log file management
# ---------------------------------------------------------------------------
def list_logs():
    """Return [(name, path, size, mtime, entry_count)] newest first."""
    out = []
    try:
        d = log_dir()
        for p in sorted(d.glob(f"{_LOG_PREFIX}*.log"),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            st = p.stat()
            entries = 0
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if line.startswith("["):
                            entries += 1
            except Exception:
                pass
            out.append((p.name, str(p), st.st_size, st.st_mtime, entries))
    except Exception:
        pass
    return out


def export_logs(paths, target_path):
    """Merge the given log files into one file (separator headers per source)."""
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as out:
        for p in paths:
            src = Path(p)
            if not src.exists():
                continue
            try:
                mtime = datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                mtime = "?"
            out.write(f"==== {src.name} · {mtime} ====\n")
            with open(src, encoding="utf-8", errors="replace") as f:
                for line in f:
                    out.write(line)
            out.write("\n")
    return str(target)


def clear_logs(paths=None):
    """Delete log files (all when ``paths`` is None). Returns deleted names."""
    deleted = []
    try:
        if paths is None:
            for p in log_dir().glob(f"{_LOG_PREFIX}*.log"):
                try:
                    p.unlink()
                    deleted.append(p.name)
                except Exception:
                    pass
        else:
            for p in paths:
                try:
                    Path(p).unlink()
                    deleted.append(Path(p).name)
                except Exception:
                    pass
    except Exception:
        pass
    return deleted


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def register():
    global _original_excepthook
    if _original_excepthook is None:
        _original_excepthook = sys.excepthook
        sys.excepthook = _handle_excepthook


def unregister():
    global _original_excepthook
    if _original_excepthook is not None:
        sys.excepthook = _original_excepthook
        _original_excepthook = None
    _close_session()