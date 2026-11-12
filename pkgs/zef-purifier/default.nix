{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  toolchain,
  nativeZef,
  rakudo,
  gcc,
  cacert,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "zef-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/zef-purifier"
    cp -r zef_purifier nix lib-overlays pkgs "$out/lib/zef-purifier/"
    install -m755 bin/zef-purifier "$out/bin/zef-purifier"
    substituteInPlace "$out/lib/zef-purifier/nix/realize.nix" \
      --replace-fail '@nixpkgs@' '${nixpkgsSrc}' \
      --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/zef-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          toolchain
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set ZEF_PURIFIER_NATIVE_ZEF ${nativeZef}/bin/zef \
      --set ZEF_PURIFIER_NATIVE_RAKU ${rakudo}/bin/raku \
      --set ZEF_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set ZEF_PURIFIER_RAKUDO_VERSION ${rakudo.version} \
      --set ZEF_PURIFIER_ZEF_VERSION ${nativeZef.version} \
      --set ZEF_PURIFIER_GCC_VERSION ${gcc.version} \
      --set ZEF_PURIFIER_SDK "$out" \
      --set ZEF_PURIFIER_TOOLCHAIN ${toolchain}
    for tool in zef raku; do
      makeWrapper "$out/bin/zef-purifier" "$out/bin/$tool" --add-flags "--native --tool=$tool --"
    done
    for program in ${toolchain}/bin/*; do
      name=$(basename "$program")
      if [ ! -e "$out/bin/$name" ]; then ln -s "$program" "$out/bin/$name"; fi
    done
  '';
  meta = {
    description = "Native Raku workflow with locked Nix-resolved dependencies";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "zef-purifier";
  };
}
