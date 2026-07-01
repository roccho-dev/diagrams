# Nix evaluation status

`flake.nix` defines `packages.<system>.jsonl-diagram-core` for core + port output only.

This execution container does not have the `nix` binary, so `nix flake check`, `nix build`, and `nix flake lock` were not executed here. No synthetic `flake.lock` is included.

The package-data side was verified through Python wheel build: `jsonl_diagram_core/schemas/diagram-event.v1.schema.json` is included in the wheel.
