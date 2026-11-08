"""Enhanced memory with relationships and graph visualization."""

import json
import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
from runtime import data_path

MEMORY_PATH = data_path("memory.json")
MEMORY_HISTORY_PATH = data_path("memory_history.json")


def load_memory_history():
    try:
        data = json.loads(MEMORY_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def record_memory_change(action, key, value=""):
    history = load_memory_history()
    history.append({"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "action": str(action), "key": str(key), "value": str(value)[:300]})
    MEMORY_HISTORY_PATH.write_text(json.dumps(history[-500:], ensure_ascii=False, indent=2), encoding="utf-8")


def load_memory_graph() -> Dict[str, Any]:
    """Load memory with graph structure. Falls back to flat format."""
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"facts": {}, "relations": []}
    
    if not isinstance(data, dict):
        return {"facts": {}, "relations": []}
    
    # A legacy memory may itself contain keys named ``facts`` or ``relations``.
    # It is a graph only when those reserved fields have graph-shaped values.
    is_graph = isinstance(data.get("facts"), dict) and isinstance(data.get("relations"), list)
    # One intermediate build serialized the graph dictionaries as strings.
    # Recover those safely with literal_eval (never eval).
    if isinstance(data.get("facts"), str):
        try:
            parsed_facts = ast.literal_eval(data["facts"])
        except (ValueError, SyntaxError):
            parsed_facts = None
        if isinstance(parsed_facts, dict):
            data["facts"] = parsed_facts
            parsed_relations = data.get("relations")
            if isinstance(parsed_relations, str):
                try:
                    parsed_relations = ast.literal_eval(parsed_relations)
                except (ValueError, SyntaxError):
                    parsed_relations = []
            data["relations"] = parsed_relations if isinstance(parsed_relations, list) else []
            is_graph = True
    if is_graph:
        # Keep only well-formed fact records. This also protects the graph
        # from malformed entries left by older experimental formats.
        normalized = {}
        for key, value in data["facts"].items():
            if isinstance(value, dict):
                normalized[str(key)] = {
                    "key": str(value.get("key") or key),
                    "value": str(value.get("value", "")),
                    "type": str(value.get("type") or _infer_fact_type(str(key))),
                    "tags": value.get("tags") if isinstance(value.get("tags"), list) else [],
                    "timestamp": value.get("timestamp"),
                }
            else:
                normalized[str(key)] = {
                    "key": str(key), "value": str(value),
                    "type": _infer_fact_type(str(key)), "tags": [], "timestamp": None,
                }
        data["facts"] = normalized
        return data
    else:
        # Some intermediate versions wrote a graph-shaped ``facts`` mapping
        # but left ``relations`` as a string. Treat that mapping as facts,
        # rather than turning the whole mapping into one giant node.
        nested_facts = data.get("facts")
        if isinstance(nested_facts, dict) and nested_facts and all(
            isinstance(item, dict) and ("value" in item or "key" in item)
            for item in nested_facts.values()
        ):
            facts = {}
            for key, item in nested_facts.items():
                facts[str(key)] = {
                    "key": str(item.get("key") or key),
                    "value": str(item.get("value", "")),
                    "type": str(item.get("type") or _infer_fact_type(str(key))),
                    "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
                    "timestamp": item.get("timestamp"),
                }
            return {"facts": facts, "relations": []}
        facts = {}
        for key, value in data.items():
            facts[key] = {
                "key": key,
                "value": str(value),
                "type": _infer_fact_type(key),
                "tags": [],
                "timestamp": None,
            }
        return {"facts": facts, "relations": []}
    
    # Validate graph format
    if not isinstance(data.get("facts"), dict):
        data["facts"] = {}
    if not isinstance(data.get("relations"), list):
        data["relations"] = []
    
    return data


def save_memory_graph(graph: Dict[str, Any]) -> None:
    """Save memory graph to file."""
    MEMORY_PATH.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_fact(key: str) -> bool:
    """Delete a fact and relations pointing to it."""
    graph = load_memory_graph()
    facts = graph.get("facts", {})
    if key not in facts:
        # Legacy flat memory is handled by the normal memory loader below.
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(data, dict) or key not in data:
            return False
        del data[key]
        MEMORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        record_memory_change("deleted", key)
        return True
    del facts[key]
    graph["relations"] = [
        relation for relation in graph.get("relations", [])
        if relation.get("from") != key and relation.get("to") != key
    ]
    save_memory_graph(graph)
    record_memory_change("deleted", key)
    return True


def add_fact(graph: Dict[str, Any], key: str, value: str, tags: List[str] = None) -> None:
    """Add or update a fact in the graph."""
    if not isinstance(graph.get("facts"), dict):
        graph["facts"] = {}
    
    key = str(key).strip()
    value = str(value).strip()
    if not key or not value:
        return
    
    graph["facts"][key] = {
        "key": key,
        "value": value,
        "type": _infer_fact_type(key),
        "tags": tags or [],
        "timestamp": None,
    }


def add_relation(graph: Dict[str, Any], from_key: str, to_key: str, relation_type: str = "related") -> None:
    """Add a relation between two facts."""
    if not isinstance(graph.get("relations"), list):
        graph["relations"] = []
    
    from_key = str(from_key).strip()
    to_key = str(to_key).strip()
    if not from_key or not to_key or from_key == to_key:
        return
    
    # Avoid duplicate relations
    for rel in graph["relations"]:
        if rel.get("from") == from_key and rel.get("to") == to_key and rel.get("type") == relation_type:
            return
    
    graph["relations"].append({
        "from": from_key,
        "to": to_key,
        "type": relation_type,
    })


def get_fact_nodes() -> List[Dict[str, Any]]:
    """Return facts as graph nodes for visualization."""
    graph = load_memory_graph()
    nodes = []
    for key, fact in graph.get("facts", {}).items():
        nodes.append({
            "id": key,
            "key": key,
            "label": fact.get("value", ""),
            "type": fact.get("type", "fact"),
            "tags": fact.get("tags", []),
        })
    return nodes


def get_relations() -> List[Dict[str, str]]:
    """Return relations as graph edges for visualization."""
    graph = load_memory_graph()
    relations = list(graph.get("relations", []))
    keys = list(graph.get("facts", {}).keys())
    existing = {(r.get("from"), r.get("to")) for r in relations}
    # Legacy memories have no explicit edges. Connect every fact to the user
    # hub so the graph still communicates how the memory is organized.
    if keys and not any(r.get("from") == "__user__" or r.get("to") == "__user__" for r in relations):
        relations.extend(
            {"from": "__user__", "to": key, "type": "knows"}
            for key in keys
            if ("__user__", key) not in existing
        )
    return relations


def _infer_fact_type(key: str) -> str:
    """Infer the type of a fact from its key."""
    key_lower = key.lower()
    if any(word in key_lower for word in ("name", "имя")):
        return "person"
    if any(word in key_lower for word in ("city", "место", "город")):
        return "location"
    if any(word in key_lower for word in ("hobby", "хобби", "интерес")):
        return "interest"
    if any(word in key_lower for word in ("favorite", "люб", "предпочит")):
        return "preference"
    if any(word in key_lower for word in ("job", "работ", "профессия")):
        return "work"
    return "fact"
