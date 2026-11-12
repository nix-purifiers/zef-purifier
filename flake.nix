{
  description = "Locked, Nix-resolved Raku dependencies";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        zef-purifier = final.lib.makeScope final.newScope (scope: {
          nativeZef = scope.callPackage ./nix/zef.nix { };
          toolchain = scope.callPackage ./nix/toolchain.nix { };
          sdkVersion = import ./nix/sdk-version.nix { nixpkgsSrc = nixpkgs; };
          cli = scope.callPackage ./pkgs/zef-purifier/default.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildZefProject = scope.callPackage ./pkgs/build-zef-project/default.nix {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).zef-purifier.cli;
        cli = self.packages.${system}.default;
        sdk = (pkgsFor system).zef-purifier.toolchain;
      });
      lib.zef-purifier = import ./lib-overlays/default { lib = nixpkgs.lib; };
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/zef-purifier";
          meta.description = "Lock Raku dependencies";
        };
      });
      checks = forAll (
        system:
        let
          build = (pkgsFor system).zef-purifier.buildZefProject { src = ./examples/minimal; };
        in
        {
          inherit (build.packages) environment project;
          release = build.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
