"""Topology sorting and dependency analysis for node patterns."""
from collections import defaultdict, deque
from typing import List, Dict, Set, Any


class NodeTopology:
    """Kahn algorithm topological sorting with cycle detection."""

    @staticmethod
    def sort(nodes: List[dict], links: List[dict]) -> List[dict]:
        """Return nodes sorted by dependency order (upstream first)."""
        if not nodes:
            return []

        # Build adjacency list and in-degree map
        graph = defaultdict(list)
        in_degree = {}
        uuid_to_node = {}

        for node in nodes:
            uuid = node.get("uuid", node.get("id", ""))
            if uuid:
                in_degree[uuid] = 0
                uuid_to_node[uuid] = node

        for link in links:
            from_uuid = link.get("from_uuid") or link.get("from", "").split(".")[0]
            to_uuid = link.get("to_uuid") or link.get("to", "").split(".")[0]

            if from_uuid in uuid_to_node and to_uuid in uuid_to_node:
                graph[from_uuid].append(to_uuid)
                in_degree[to_uuid] = in_degree.get(to_uuid, 0) + 1

        # Kahn's algorithm
        queue = deque([uuid for uuid, deg in in_degree.items() if deg == 0])
        sorted_uuids = []

        while queue:
            uuid = queue.popleft()
            sorted_uuids.append(uuid)
            for neighbor in graph.get(uuid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Handle cycles (defensive)
        if len(sorted_uuids) != len(uuid_to_node):
            remaining = [uuid for uuid in uuid_to_node if uuid not in sorted_uuids]
            print(f"[WARNING] Circular dependency detected in nodes: {remaining}")
            # Fallback: append remaining in original order
            for node in nodes:
                uuid = node.get("uuid", node.get("id", ""))
                if uuid in remaining:
                    sorted_uuids.append(uuid)

        return [uuid_to_node[uuid] for uuid in sorted_uuids if uuid in uuid_to_node]

    @staticmethod
    def get_dependencies(nodes: List[dict], links: List[dict]) -> Dict[str, Set[str]]:
        """Get direct upstream dependencies for each node."""
        deps = defaultdict(set)
        for link in links:
            to_uuid = link.get("to_uuid") or link.get("to", "").split(".")[0]
            from_uuid = link.get("from_uuid") or link.get("from", "").split(".")[0]
            if to_uuid and from_uuid:
                deps[to_uuid].add(from_uuid)
        return dict(deps)

    @staticmethod
    def get_all_dependencies(uuid: str, direct_deps: Dict[str, Set[str]]) -> Set[str]:
        """Get all transitive dependencies for a node (recursive)."""
        visited = set()
        stack = [uuid]
        while stack:
            current = stack.pop()
            if current not in visited:
                visited.add(current)
                for dep in direct_deps.get(current, set()):
                    if dep not in visited:
                        stack.append(dep)
        visited.remove(uuid)  # Remove self
        return visited
