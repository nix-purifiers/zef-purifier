{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  toolchain,
  nativeZef,
  rakudo,
  gcc,
  sdkVersion,
}:
{
  lock,
  fetchers ? { },
  nativeBuildInputs ? [ ],
}:
let
  checked = purifier.checkLock lock;
  sources = purifier.tree (
    {
      name = "locked-raku-sources";
      entries = checked.entries;
      inherit
        runCommand
        fetchgit
        python3
        writeText
        ;
    }
    // fetchers
  );
  manifest = writeText "zef-capture.json" (builtins.toJSON checked.data);
in
assert checked.problems == [ ];
assert lib.assertMsg (
  checked.data.toolVersions == {
    sdk = sdkVersion;
    rakudo = rakudo.version;
    zef = nativeZef.version;
    gcc = gcc.version;
  }
) "Raku SDK changed; run zef-purifier lock --update";
runCommand "purified-zef-environment"
  {
    nativeBuildInputs = [
      toolchain
      python3
    ]
    ++ nativeBuildInputs;
  }
  ''
    export PATH=${toolchain}/bin:$PATH
    export HOME="$TMPDIR/home" ZEF_CONFIG_TEMPDIR="$TMPDIR/tmp" ZEF_CONFIG_STOREDIR="$TMPDIR/store"
    mkdir -p "$HOME" "$ZEF_CONFIG_TEMPDIR" "$ZEF_CONFIG_STOREDIR" "$out/repo"/{short,dist,sources,resources,bin,precomp}
    ${lib.optionalString (checked.entries != [ ]) ''
      zef --precompile-install --/update --/depends --/build-depends --/test-depends --/test --force-install --install-to="$out/repo" install ${
        lib.escapeShellArgs (map (d: "${sources}/${d.path}") checked.data.distributions)
      }
    ''}
    export RAKUDOLIB="inst#$out/repo"
    raku -e 'say Rakudo::Internals::JSON.to-json(CompUnit::RepositoryRegistry.repository-for-spec(%*ENV<RAKUDOLIB>).installed.grep(*.defined).map(*.meta).grep(*.defined).Array)' > "$TMPDIR/installed.json"
    python3 ${../zef_purifier/check-installed.py} ${manifest} "$TMPDIR/installed.json"
    raku ${./warm.raku} ${manifest}
    cp ${manifest} "$out/capture.json"
    ln -s ${sources} "$out/sources"
  ''
