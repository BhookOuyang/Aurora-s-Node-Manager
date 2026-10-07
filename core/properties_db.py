# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""[DEPRECATED] Node property database - replaced by RNAInspector.
Kept for backward compatibility with v2.0 patterns."""
import bpy
from typing import Dict, Any, Optional


class NodePropertiesDB:
    """Legacy property database. Use RNAInspector for new code."""

    @classmethod
    def discover_properties(cls, node: bpy.types.Node, only_modified: bool = False) -> Dict[str, Any]:
        """Deprecated: Use RNAInspector.discover_properties() instead."""
        from .rna_inspector import RNAInspector
        return RNAInspector.discover_properties(node, only_modified=only_modified)

    @classmethod
    def apply_properties(cls, node: bpy.types.Node, properties: Dict[str, Any]) -> None:
        """Deprecated: Use RNAInspector.apply_properties() instead."""
        from .rna_inspector import RNAInspector
        RNAInspector.apply_properties(node, properties)