{
  project,
  companion,
  target ? "environment",
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  nativeZef = pkgs.callPackage ./zef.nix { };
  toolchain = pkgs.callPackage ./toolchain.nix { inherit nativeZef; };
  sdkVersion = import ./sdk-version.nix { inherit nixpkgsSrc; };
  args = {
    src = /. + project;
    lockFile = /. + companion;
  };
  lock = import ../lib-overlays/default/read-lock.nix { inherit (pkgs) lib; } args;
  packages = pkgs.callPackage ../pkgs/build-zef-project/default.nix {
    inherit
      purifier
      nativeZef
      toolchain
      sdkVersion
      ;
  } args;
in
if target == "environment" then
  pkgs.callPackage ../pkgs/build-zef-project/environment.nix {
    inherit
      purifier
      nativeZef
      toolchain
      sdkVersion
      ;
  } { inherit lock; }
else if target == "release" then
  packages.release
else
  throw "zef-purifier: unknown target"
