# Aurora's Node Manager

> [中文版说明 →](README.md)

A Blender addon for saving, loading and sharing node patterns via JSON serialization. Supports Shader, Compositor and Geometry node trees with cross-version and cross-type compatibility.

## Motivation

I originally just wanted a node manager—rebuilding node setups from scratch got old fast.
Sure, I could save .blend files, but those are huge, and my disk is always begging for space.
JSON is far more lightweight.

And since JSON is plain text, the simplest way to share it is by sending it directly on social media.
That happens to bypass something I've been putting up with for years: cloud drives.
In my region, node sharing mostly relies on cloud drives (I have no idea how it works elsewhere).
But I've always hated them—they aggressively replace your default file handlers and try to hijack your browser.
Yet I'm forced to use them anyway. That "no choice" feeling is just awful.

Sharing node patterns as JSON solves both problems at once: it saves space and avoids cloud drives.
If you're also tired of rebuilding nodes and dealing with cloud drives, give this a try.
(I'm a student, so updates may be slow—please bear with me 🙏)

## Features

- **Save & Load** — Select nodes and save as a named pattern, load anytime with one click.
- **Cross-Type Loading** — Use shader patterns in geometry nodes or compositor, and vice versa.
- **Cross-Version Compatibility** — Works across Blender 3.6+ to 5.x.
- **Pattern Locking** — Lock patterns to prevent accidental overwrites or deletion.
- **ZIP Import/Export** — Export patterns (including nested node groups) as ZIP bundles for easy distribution.
- **Clipboard Sharing** — Copy patterns as JSON bundles and paste them from forum posts or chat messages.
- **Multi-Language UI** — English and Chinese UI out of the box.

## Technical Implementation

- **RNA Property Discovery** — Automatically scans and serializes all node RNA properties at runtime via introspection. No manual property lists to maintain. Supports type inference for bool, int, float, string, enum, color, vector, matrix.
- **UUID Topology System** — Every node gets a persistent UUID. Links use socket identifiers and indices for reliable reconnection. Kahn topological sort ensures correct load order.
- **Smart Enum Compatibility** — When loading patterns from a different Blender version, enum values that no longer exist are automatically matched to the closest available option through priority-based fallback.
- **Index-Priority Socket Matching** — During deserialization, sockets are located by `index` → `identifier` → `name` → `type`, maximizing reconnection success.

## Installation

1. Download the addon ZIP file
2. Blender → Edit → Preferences → Add-ons → Install
3. Select the ZIP file and enable the addon
4. Open the Node Editor, press N to show the Sidebar, and find the **Dear.Aurora** tab

## Usage

The addon provides three panels in the Node Editor sidebar:

### Node Patterns (Main Panel)
- **Category tabs**: Switch between Shader / Compositor / Geometry
- **Save Selected**: Save selected nodes as a named pattern
- **Load**: Load a pattern into the current node tree
- **Overwrite**: Replace an existing pattern with the currently selected nodes
- **Copy**: Copy a pattern to clipboard as JSON bundle
- **Paste**: Import a pattern from clipboard
- **Export/Import**: Export/import patterns as ZIP files
- **Edit**: Edit pattern metadata (name, description, author, tags)
- **Lock/Unlock**: Prevent accidental modifications
- **Delete**: Remove a pattern

### Pattern Info
Shows metadata for the selected pattern: description, author, creation date, version, node/group count, and type.

### Advanced
Serialization options are planned (currently reserved for future versions).

## Compatibility

Tested on Blender 3.6.1, 4.1.1, 4.5.2 LTS, and 5.1.1 LTS.

Both English and Chinese UI languages are supported.

## File Structure

```
aurora_nodes_manager/
├── __init__.py              # Addon entry, preferences
├── core/
│   ├── serializer.py        # Serialization engine
│   ├── deserializer.py      # Deserialization engine (RNA-driven)
│   ├── rna_inspector.py     # RNA property discovery
│   ├── topology.py          # Kahn topological sort
│   ├── properties_db.py     # Legacy wrapper (delegates to RNAInspector)
│   └── zone_handler.py      # Zone node (Simulation/Repeat) handling
├── compat/
│   ├── blender_compat.py    # API compatibility, socket value I/O
│   └── node_mappings.py     # Cross-version and cross-type mappings
├── io_module/
│   └── operators.py         # All operators (save/load/delete/edit/overwrite/lock/migrate/export/import/copy/paste)
├── ui/
│   └── panels.py            # 3 panels: main, info, advanced
└── utils/
    ├── file_utils.py        # File utilities, ZIP bundle handling
    └── translations.py      # zh_CN translation dictionary
```

Patterns are stored as `.json` files in the addon's `patterns/` directory, organized by type (`shader/`, `compositor/`, `geometry/`). Nested node groups are saved as separate `_group_*.json` sidecar files.

## Known Limitations

- Zone nodes (Simulation Zone / Repeat Zone) have known socket loss issues during deserialization. Manual reconnection may be required after loading.
- Custom Python nodes need manual support added.
- Node mappings may not cover all node types. Cross-version loading may produce parameter errors or rendering differences due to API refactoring (worst case: abnormal index values may cause Blender to crash).
- Node layout positions may occasionally drift from the saved positions.
- Clipboard export of very complex node groups may exceed social media character limits. Use ZIP export for large patterns.

## Roadmap

- **JSON compression codec** — Compress pattern data so even large node setups can be shared within social media character limits.

## License

GPLv3
