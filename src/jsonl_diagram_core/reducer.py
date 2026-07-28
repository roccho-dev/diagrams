from __future__ import annotations

from typing import Any

from .mxgraph_model import build_model

JsonObj = dict[str, Any]


def reduce_tokens(tokens: list[JsonObj], *, validate: bool = True) -> str:
    """Reduce validated event tokens directly to the sole generated mxGraphModel state."""
    events = [dict(token["payload"]) for token in tokens]
    # build_model performs strict event and reference validation.  The validate
    # argument remains only for source compatibility; bypassing validation is
    # intentionally unsupported by the accepted current-state contract.
    del validate
    return build_model(events)
