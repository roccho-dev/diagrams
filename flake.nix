{
  description = "jsonl-diagram core+port library packaged with Nix; adapters remain examples/fixtures";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (pkgs: {
        jsonl-diagram-core = pkgs.python3Packages.buildPythonPackage {
          pname = "jsonl-diagram-core";
          version = "0.1.0";
          src = self;
          pyproject = true;
          build-system = with pkgs.python3Packages; [ setuptools wheel ];
          pythonImportsCheck = [ "jsonl_diagram_core" ];
          doCheck = true;
          checkPhase = ''
            runHook preCheck
            ${pkgs.python3.interpreter} -m unittest discover -s tests/unit
            runHook postCheck
          '';
          meta = with pkgs.lib; {
            description = "JSONL diagram core and port contracts";
            license = licenses.mit;
            platforms = platforms.all;
          };
        };
      });

      checks = forAllSystems (pkgs: {
        core-unit = self.packages.${pkgs.system}.jsonl-diagram-core;
      });

      apps = forAllSystems (pkgs: {
        jsonl-diagram-core = {
          type = "app";
          program = "${self.packages.${pkgs.system}.jsonl-diagram-core}/bin/jsonl-diagram-core";
        };
      });
    };
}
