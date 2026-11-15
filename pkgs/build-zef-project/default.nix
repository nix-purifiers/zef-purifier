{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  nativeZef,
  toolchain,
  rakudo,
  gcc,
  sdkVersion,
  gnutar,
  gzip,
}:
{
  src,
  lockFile ? src + "/zef-purifier.lock.json",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  buildCommand ? "if [ -f Build.rakumod ] || [ -f Build.pm6 ]; then zef build .; fi",
  checkCommand ? "for test in t/*.rakutest; do raku -Ilib \"$test\"; done",
  installCommand ? "cp -r lib META6.json \"$out/\"",
  doCheck ? true,
  srcFilter ?
    path: type:
    !(builtins.elem (baseNameOf path) [
      ".git"
      ".zef-purifier"
      ".precomp"
      "result"
      "__pycache__"
    ]),
}:
let
  lock = purifier.checkLock (import ../../lib-overlays/default/read-lock.nix { inherit lib; } { inherit src lockFile; });
  environment = import ./environment.nix {
    inherit
      lib
      runCommand
      fetchgit
      python3
      writeText
      purifier
      nativeZef
      toolchain
      rakudo
      gcc
      sdkVersion
      ;
  } { inherit lock fetchers nativeBuildInputs; };
  source = lib.cleanSourceWith {
    inherit src;
    filter = srcFilter;
  };
  project =
    runCommand "purified-raku-project" { nativeBuildInputs = [ toolchain ] ++ nativeBuildInputs; }
      ''
        export PATH=${toolchain}/bin:$PATH HOME="$TMPDIR/home" RAKUDOLIB="inst#${environment}/repo"
        mkdir -p "$HOME" work "$out"
        cp -pr ${source}/. work/
        chmod -R u+w work
        cd work
        ${buildCommand}
        ${lib.optionalString doCheck checkCommand}
        ${installCommand}
      '';
  release =
    runCommand "raku-project-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        set -o pipefail
        mkdir -p "$out" source
        cp -r ${source}/. source/
        chmod -R u+w source
        cp ${lockFile} source/zef-purifier.lock.json
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -cf - source | gzip -n > "$out/source.tar.gz"
      '';
in
assert lock.problems == [ ];
assert lib.assertMsg (
  lock.data.toolVersions == {
    sdk = sdkVersion;
    rakudo = rakudo.version;
    zef = nativeZef.version;
    gcc = gcc.version;
  }
) "Raku SDK changed; run zef-purifier lock --update";
{
  packages = {
    default = project;
    inherit project environment;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
