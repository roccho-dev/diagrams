from __future__ import annotations

from typing import Any

Json = dict[str, Any]


def fixtures() -> dict[str, list[Json]]:
    return {
        "01_flow": [
            {"op": "diagram.init", "id": "flow", "kind": "flow", "label": "Flow"},
            {"op": "node.upsert", "id": "start", "kind": "start", "label": "Start", "order": 1},
            {"op": "node.upsert", "id": "work", "kind": "service", "label": "Work", "order": 2},
            {"op": "node.upsert", "id": "end", "kind": "end", "label": "End", "order": 3},
            {"op": "edge.upsert", "id": "e1", "source": "start", "target": "work", "label": "run", "order": 1},
            {"op": "edge.upsert", "id": "e2", "source": "work", "target": "end", "label": "done", "order": 2},
            {"op": "layout.intent", "target": "flow", "intent": "left-to-right", "meta": {"rank": "same"}},
        ],
        "02_swimlane": [
            {"op": "diagram.init", "id": "swim", "kind": "swimlane", "label": "Swimlane"},
            {"op": "group.upsert", "id": "product", "kind": "lane", "label": "Product", "order": 1},
            {"op": "group.upsert", "id": "engineering", "kind": "lane", "label": "Engineering", "order": 2},
            {"op": "node.upsert", "id": "spec", "kind": "task", "label": "Specify", "lane": "product", "order": 1},
            {"op": "node.upsert", "id": "build", "kind": "task", "label": "Build", "lane": "engineering", "order": 2},
            {"op": "edge.upsert", "id": "handoff", "source": "spec", "target": "build", "label": "handoff"},
            {"op": "style.intent", "target": "build", "intent": "emphasis", "meta": {"reason": "delivery"}},
        ],
        "03_sequence": [
            {"op": "diagram.init", "id": "seq", "kind": "sequence", "label": "Sequence"},
            {"op": "node.upsert", "id": "client", "kind": "participant", "label": "Client", "order": 1},
            {"op": "node.upsert", "id": "api", "kind": "participant", "label": "API", "order": 2},
            {"op": "node.upsert", "id": "db", "kind": "participant", "label": "DB", "order": 3},
            {"op": "edge.upsert", "id": "request", "source": "client", "target": "api", "label": "request", "order": 1},
            {"op": "edge.upsert", "id": "query", "source": "api", "target": "db", "label": "query", "order": 2},
        ],
        "04_state": [
            {"op": "diagram.init", "id": "state", "kind": "state", "label": "State"},
            {"op": "node.upsert", "id": "draft", "kind": "state", "label": "Draft", "order": 1},
            {"op": "node.upsert", "id": "accepted", "kind": "state", "label": "Accepted", "order": 2},
            {"op": "edge.upsert", "id": "accept", "kind": "transition", "source": "draft", "target": "accepted", "label": "approve"},
        ],
        "05_timeline": [
            {"op": "diagram.init", "id": "timeline", "kind": "timeline", "label": "Timeline"},
            {"op": "milestone.upsert", "id": "m1", "label": "Start", "start": 1, "order": 1},
            {"op": "milestone.upsert", "id": "m2", "label": "Launch", "start": 5, "order": 2},
            {"op": "edge.upsert", "id": "time", "source": "m1", "target": "m2", "label": "progress"},
        ],
        "06_gantt": [
            {"op": "diagram.init", "id": "gantt", "kind": "gantt", "label": "Gantt"},
            {"op": "group.upsert", "id": "team", "kind": "lane", "label": "Team"},
            {"op": "task.upsert", "id": "t1", "label": "Design", "lane": "team", "start": 0, "end": 3, "order": 1},
            {"op": "task.upsert", "id": "t2", "label": "Ship", "lane": "team", "start": 3, "end": 7, "order": 2},
            {"op": "edge.upsert", "id": "depends", "kind": "depends", "source": "t1", "target": "t2"},
        ],
        "07_erd": [
            {"op": "diagram.init", "id": "erd", "kind": "erd", "label": "ERD"},
            {"op": "entity.upsert", "id": "user", "kind": "table", "label": "users", "columns": [{"name": "id", "type": "uuid"}], "order": 1},
            {"op": "entity.upsert", "id": "order", "kind": "table", "label": "orders", "columns": [{"name": "user_id", "type": "uuid"}], "order": 2},
            {"op": "edge.upsert", "id": "fk", "kind": "relation", "source": "order", "target": "user", "label": "user_id"},
        ],
        "08_architecture": [
            {"op": "diagram.init", "id": "arch", "kind": "architecture", "label": "Architecture"},
            {"op": "group.upsert", "id": "platform", "kind": "container", "label": "Platform"},
            {"op": "node.upsert", "id": "web", "kind": "service", "label": "Web", "group": "platform", "order": 1},
            {"op": "node.upsert", "id": "worker", "kind": "service", "label": "Worker", "group": "platform", "order": 2},
            {"op": "edge.upsert", "id": "job", "kind": "dependency", "source": "web", "target": "worker", "label": "job"},
        ],
        "09_dense_dependency": [
            {"op": "diagram.init", "id": "dense", "kind": "dense_dependency", "label": "Dense dependency"},
            *[{"op": "node.upsert", "id": f"n{i}", "kind": "module", "label": f"N{i}", "order": i} for i in range(1, 7)],
            *[{"op": "edge.upsert", "id": f"d{i}{j}", "kind": "dependency", "source": f"n{i}", "target": f"n{j}"} for i, j in ((1, 3), (1, 4), (2, 4), (2, 5), (3, 6), (4, 6), (5, 6))],
        ],
        "10_nested_ports": [
            {"op": "diagram.init", "id": "ports", "kind": "nested_ports", "label": "Nested ports"},
            {"op": "group.upsert", "id": "outer", "kind": "container", "label": "Outer", "order": 1},
            {"op": "group.upsert", "id": "inner", "kind": "container", "label": "Inner", "group": "outer", "order": 1},
            {"op": "node.upsert", "id": "producer", "kind": "component", "label": "Producer", "group": "inner", "meta": {"ports": ["out"]}},
            {"op": "node.upsert", "id": "consumer", "kind": "component", "label": "Consumer", "group": "outer", "meta": {"ports": ["in"]}},
            {"op": "edge.upsert", "id": "port-edge", "source": "producer", "target": "consumer", "meta": {"sourcePort": "out", "targetPort": "in"}},
        ],
        "11_bpmn": [
            {"op": "diagram.init", "id": "bpmn", "kind": "bpmn", "label": "BPMN"},
            {"op": "group.upsert", "id": "lane", "kind": "lane", "label": "Operations"},
            {"op": "node.upsert", "id": "s", "kind": "start", "label": "Start", "lane": "lane", "order": 1},
            {"op": "node.upsert", "id": "task", "kind": "task", "label": "Task", "lane": "lane", "order": 2},
            {"op": "node.upsert", "id": "gate", "kind": "gateway", "label": "OK?", "lane": "lane", "order": 3},
            {"op": "node.upsert", "id": "e", "kind": "end", "label": "End", "lane": "lane", "order": 4},
            {"op": "edge.upsert", "id": "b1", "source": "s", "target": "task"},
            {"op": "edge.upsert", "id": "b2", "source": "task", "target": "gate"},
            {"op": "edge.upsert", "id": "b3", "source": "gate", "target": "e", "label": "yes"},
        ],
        "12_mindmap": [
            {"op": "diagram.init", "id": "mind", "kind": "mindmap", "label": "Mind map"},
            {"op": "node.upsert", "id": "root", "kind": "root", "label": "Root", "order": 1},
            {"op": "node.upsert", "id": "a", "kind": "branch", "label": "A", "order": 2},
            {"op": "node.upsert", "id": "b", "kind": "branch", "label": "B", "order": 3},
            {"op": "node.upsert", "id": "c", "kind": "branch", "label": "C", "order": 4},
            {"op": "edge.upsert", "id": "ma", "source": "root", "target": "a"},
            {"op": "edge.upsert", "id": "mb", "source": "root", "target": "b"},
            {"op": "edge.upsert", "id": "mc", "source": "root", "target": "c"},
        ],
        "13_venn": [
            {"op": "diagram.init", "id": "venn_expression", "kind": "venn", "label": "Venn: JSONL Diagram Value Overlap", "meta": {"note": "sets are groups; regions are nodes with meta.members"}},
            {"op": "group.upsert", "id": "agent", "kind": "set", "label": "Agent-first", "order": 1},
            {"op": "group.upsert", "id": "governance", "kind": "set", "label": "Governance / Proof", "order": 2},
            {"op": "group.upsert", "id": "design", "kind": "set", "label": "Design Quality", "order": 3},
            {"op": "node.upsert", "id": "agent_only", "kind": "region", "label": "Append UX", "meta": {"members": ["agent"]}, "order": 1},
            {"op": "node.upsert", "id": "governance_only", "kind": "region", "label": "Audit Gate", "meta": {"members": ["governance"]}, "order": 2},
            {"op": "node.upsert", "id": "design_only", "kind": "region", "label": "Visual Tokens", "meta": {"members": ["design"]}, "order": 3},
            {"op": "node.upsert", "id": "agent_governance", "kind": "region", "label": "Safe Automation", "meta": {"members": ["agent", "governance"]}, "order": 4},
            {"op": "node.upsert", "id": "agent_design", "kind": "region", "label": "Readable Output", "meta": {"members": ["agent", "design"]}, "order": 5},
            {"op": "node.upsert", "id": "governance_design", "kind": "region", "label": "Proof UI", "meta": {"members": ["governance", "design"]}, "order": 6},
            {"op": "node.upsert", "id": "core_overlap", "kind": "region", "label": "Valuable Asset", "meta": {"members": ["agent", "governance", "design"]}, "order": 7},
            {"op": "layout.intent", "target": "venn_expression", "intent": "venn-3-set", "meta": {"renderer": "single-svg", "sets": ["agent", "governance", "design"]}},
            {"op": "style.intent", "target": "core_overlap", "intent": "emphasis", "meta": {"reason": "highest-value overlap"}},
        ],
    }
