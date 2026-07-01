from __future__ import annotations
from collections import deque
from typing import Any, Iterable

JsonObj = dict[str, Any]

def project_network_to_dag(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> JsonObj:
    node_list = sorted(set(nodes))
    adj = {n: set() for n in node_list}
    edge_list = [(a, b) for a, b in edges]
    for a, b in edge_list:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    root = max(sorted(adj), key=lambda n: (len(adj[n]), -node_list.index(n) if n in node_list else 0)) if adj else None
    depth = {root: 0} if root is not None else {}
    q = deque([root] if root is not None else [])
    while q:
        cur = q.popleft()
        for nxt in sorted(adj[cur]):
            if nxt not in depth:
                depth[nxt] = depth[cur] + 1
                q.append(nxt)
    oriented = []
    feedback = []
    for a, b in edge_list:
        da, db = depth.get(a, 0), depth.get(b, 0)
        if da < db:
            oriented.append((a, b))
        elif db < da:
            oriented.append((b, a))
        else:
            src, dst = sorted([a, b])
            oriented.append((src, dst))
            feedback.append((a, b))
    return {"schema":"NetworkProjection.v1", "root": root, "depth": depth, "orientedEdges": oriented, "feedbackCandidates": feedback, "dagProjectionSafe": len(feedback) == 0}
