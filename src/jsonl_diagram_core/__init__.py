"""JSONL diagram core and port contracts."""
from .io import canonical_json, read_jsonl, sha256_text, write_jsonl
from .schema import EVENT_RULES, EventValidationError, validate_event, validate_events
from .tokenizer import tokenize_event, tokenize_events
from .reducer import reduce_tokens
from .proof import build_proof, sha256_file

__all__ = [
    "EVENT_RULES",
    "EventValidationError",
    "build_proof",
    "canonical_json",
    "read_jsonl",
    "reduce_tokens",
    "sha256_file",
    "sha256_text",
    "tokenize_event",
    "tokenize_events",
    "validate_event",
    "validate_events",
    "write_jsonl",
]
