from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

JsonObj = dict[str, Any]


@runtime_checkable
class EventSourcePort(Protocol):
    def read_events(self) -> list[JsonObj]: ...


@runtime_checkable
class TokenizerPort(Protocol):
    def tokenize(self, events: list[JsonObj]) -> list[JsonObj]: ...


@runtime_checkable
class ReducerPort(Protocol):
    def reduce(self, tokens: list[JsonObj]) -> JsonObj: ...


@runtime_checkable
class D2CompilePort(Protocol):
    def compile_d2(self, dvm: JsonObj) -> str: ...


@runtime_checkable
class LayoutPort(Protocol):
    def layout(self, dvm: JsonObj) -> JsonObj: ...


@runtime_checkable
class SvgRenderPort(Protocol):
    def render_svg(self, dvm: JsonObj, layout: JsonObj | None = None) -> str: ...


@runtime_checkable
class ProofGatePort(Protocol):
    def verify(self, root: str) -> JsonObj: ...
