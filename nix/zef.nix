{
  zef,
  rakudo,
  python3,
}:
zef.overrideAttrs (old: {
  patches = (old.patches or [ ]) ++ [ ./zef.patch ];
  postInstall =
    (old.postInstall or "")
    + "\n"
    + ''
      export HOME="$TMPDIR/home" RAKUDOLIB="inst#$out"
      mkdir -p "$HOME"
      ${python3}/bin/python3 -c 'import json,os; json.dump([{"meta":json.load(open("META6.json"))}],open(os.environ["TMPDIR"]+"/sdk-meta.json","w"))'
      ${rakudo}/bin/raku ${./warm.raku} "$TMPDIR/sdk-meta.json"
    '';
})
