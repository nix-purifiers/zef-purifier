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
  binutils,
  stdenv,
}:
{
  src,
  lockFile ? src + "/zef-purifier.lock.json",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  buildCommand ? "if [ -f Build.rakumod ] || [ -f Build.pm6 ]; then zef build .; fi",
  checkCommand ? "for test in t/*.rakutest; do raku -Ilib \"$test\"; done",
  installCommand ? null,
  nativeLibraries ? { },
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
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } { inherit src lockFile; }
  );
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
  capturedMeta = writeText "zef-original-META6.json" lock.data.inputs."META6.json".content;
  specifications = writeText "zef-native-resources.json" (builtins.toJSON nativeLibraries);
  relative =
    value:
    builtins.isString value
    && value != ""
    && !(lib.hasPrefix "/" value)
    && !(builtins.elem ".." (lib.splitString "/" value));
  symbol = value: builtins.isString value && builtins.match "[A-Za-z_][A-Za-z0-9_]*" value != null;
  validLibrary =
    name: spec:
    symbol name
    && builtins.isAttrs spec
    &&
      builtins.attrNames (
        builtins.removeAttrs spec [
          "resource"
          "library"
          "header"
          "exports"
        ]
      ) == [ ]
    && relative (spec.resource or null)
    && relative (spec.library or null)
    && (!(spec ? header) || spec.header == null || relative spec.header)
    && builtins.isList (spec.exports or null)
    && spec.exports != [ ]
    && builtins.all symbol spec.exports;
  project =
    runCommand "purified-raku-project" { nativeBuildInputs = [ toolchain ] ++ nativeBuildInputs; }
      ''
        export PATH=${toolchain}/bin:$PATH HOME="$TMPDIR/home" RAKUDOLIB="inst#${environment}/repo"
        mkdir -p "$HOME" work "$out"
        cp -pr ${source}/. work/
        chmod -R u+w work
        cd work
        ${lib.optionalString (installCommand == null || nativeLibraries != { }) ''
          cmp META6.json ${capturedMeta}
        ''}
        ${buildCommand}
        ${lib.optionalString doCheck checkCommand}
        ${lib.optionalString (installCommand == null || nativeLibraries != { }) ''
          cmp META6.json ${capturedMeta}
          ${rakudo}/bin/raku -Iinst#${nativeZef} ${./resource-metadata.raku} "$PWD" > "$TMPDIR/zef-native-metadata.json"
        ''}
        ${
          if installCommand == null then
            ''
              cp -r lib META6.json "$out/"
              ${python3}/bin/python3 ${./install-resources.py} "$PWD" "$out" "$TMPDIR/zef-native-metadata.json"
            ''
          else
            installCommand
        }
        ${lib.optionalString (nativeLibraries != { }) ''
          cmp META6.json "$out/META6.json"
          ${python3}/bin/python3 ${./verify-native-resources.py} "$PWD" "$out" \
            "$TMPDIR/zef-native-metadata.json" ${specifications} ${binutils}/bin/nm ${stdenv.hostPlatform.system} ${source}
        ''}
      '';
  projections = lib.optionalAttrs (nativeLibraries != { }) (
    purifier.nativeProjections {
      producer = project;
      libraries = lib.mapAttrs (_: spec: spec.library) nativeLibraries;
      includeDirectories = lib.unique (
        lib.mapAttrsToList (_: spec: dirOf spec.header) (
          lib.filterAttrs (_: spec: (spec.header or null) != null) nativeLibraries
        )
      );
      targetMetadata = lib.mapAttrs (_: spec: {
        abi = "c";
        inherit (spec) resource exports;
        package = builtins.fromJSON lock.data.inputs."META6.json".content;
        toolVersions = lock.data.toolVersions;
      }) nativeLibraries;
      system = stdenv.hostPlatform.system;
      inherit runCommand python3;
    }
  );
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
assert lib.assertMsg (lib.all (name: validLibrary name nativeLibraries.${name}) (
  builtins.attrNames nativeLibraries
)) "Zef native libraries require resource, library, callable exports and optional resource header";
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
  inherit release projections;
  fetches = lock.entries;
}
