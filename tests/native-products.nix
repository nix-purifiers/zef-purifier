{
  pkgs,
  src ? ./fixtures/native,
  expected ? 41,
}:
let
  build = pkgs.zef-purifier.buildZefProject {
    inherit src;
    checkCommand = ''raku -Ilib -e 'use Purifier::NativeResource; die "source NativeCall" unless answer(1)==${toString (expected + 1)}' '';
    nativeLibraries.answer = {
      resource = "libraries/native-answer";
      library = "resources/libraries/libnative-answer.so";
      header = "resources/include/native-answer.h";
      exports = [ "native_answer" ];
    };
  };
  producer = build.packages.project;
  projection = build.projections.native;
  python = pkgs.python3.withPackages (p: [ p.cffi ]);
in
pkgs.runCommand "zef-native-resource-consumers"
  {
    nativeBuildInputs = [
      python
      pkgs.rakudo
      pkgs.gcc
      pkgs.jdk21
    ];
    passthru = { inherit producer projection build; };
  }
  ''
    export HOME="$TMPDIR/home"
    mkdir -p "$HOME" "$out"
    raku -I${producer}/lib -e 'use Purifier::NativeResource; for 0..99 -> $value { die "installed NativeCall" unless answer($value)==$value+${toString expected} }; die "overflow" unless answer(0xffffffff)==${toString (expected - 1)}; say "Actual installed Zef NativeCall100/overflow PASS"'
    test "$(cat ${producer}/resources/data/message.txt)" = 'native resource preserved'
    test -x ${producer}/resources/libraries/libnative-answer.so
    python ${./native-consumers.py} ${projection} ${toString expected}
    cc ${./native-consumer.c} -DEXPECTED=${toString expected} \
      -I${producer}/resources/include ${producer}/resources/libraries/libnative-answer.so -o consume
    ./consume
    cp ${./NativeResource.java} NativeResource.java
    javac --enable-preview --release 21 NativeResource.java
    java @${build.projections.java-ffi}/java.args --enable-preview --enable-native-access=ALL-UNNAMED NativeResource ${toString expected}
    cp ${producer}/nix-support/zef-native/verified-resources.json "$out/"
  ''
