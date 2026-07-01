# Nix output

Required output:

```sh
nix build .#jsonl-diagram-core
```

This packages only `src/jsonl_diagram_core` as a core+port library.
Adapter code is intentionally not part of the lib boundary. It remains under `examples/adapters` and `tests/e2e/fixtures/adapters`.

The current execution container does not have `nix`, so the flake is included as the packaging contract and must be evaluated in a Nix-enabled environment.
