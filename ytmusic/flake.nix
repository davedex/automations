{
  description = "YTMusic Automation Environment";

  inputs = {
    # Pinning to a specific stable release ensures reproducibility and caches it locally
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forEachSupportedSystem = f: nixpkgs.lib.genAttrs supportedSystems (system: f {
        pkgs = import nixpkgs { inherit system; };
      });
    in
    {
      devShells = forEachSupportedSystem ({ pkgs }: {
        default = pkgs.mkShell {
          packages = [
            pkgs.python312Packages.python
            # Add any other required python packages here, e.g.:
            # pkgs.python312Packages.requests
          ];
        };
      });
    };
}
