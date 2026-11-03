{ nixpkgsSrc }:
builtins.hashString "sha256" (
  builtins.toJSON {
    nixpkgs = toString nixpkgsSrc;
    patch = builtins.hashFile "sha256" ./zef.patch;
    warm = builtins.hashFile "sha256" ./warm.raku;
    sdk = builtins.hashFile "sha256" ./zef.nix;
    toolchain = builtins.hashFile "sha256" ./toolchain.nix;
  }
)
