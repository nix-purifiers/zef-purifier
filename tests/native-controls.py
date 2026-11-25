"""Reject mismatched native resources using actual owning builds."""
import json
import os
from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parent.parent
core = os.environ.get("ZEF_TEST_CORE_SOURCE")
override = ('.override { purifier = import (/. + ' + json.dumps(core) +
            ' + "/nix/lib") { inherit (p) lib; }; }') if core else ""
prefix = '''let f=builtins.getFlake REPO;
p=import f.inputs.nixpkgs {system=builtins.currentSystem;overlays=[f.overlays.default];};
builder=p.zef-purifier.buildZefProjectOVERRIDE;
src=f.outPath+"/tests/fixtures/native";
base={inherit src;doCheck=false;};
spec={resource="libraries/native-answer";library="resources/libraries/libnative-answer.so";
header="resources/include/native-answer.h";exports=["native_answer"];};
foreign=p.runCommand "zef-foreign-resource-owner" {nativeBuildInputs=[p.gcc];} ''
mkdir -p "$out"
cc -shared -fPIC -I${src}/native ${src}/native/answer.c -o "$out/library.so"
'';
copy="cp -r lib META6.json resources \\\"$out/\\\"";
in '''.replace("REPO", json.dumps(str(repo))).replace("OVERRIDE", override)
cases = [
    ("wrong-library", 'base // {nativeLibraries.answer=spec // {library="resources/data/message.txt";};}',
     "Resource/library selector mismatch"),
    ("missing-export", 'base // {nativeLibraries.answer=spec // {exports=["absent_native_export"];};}',
     "Missing callable native export"),
    ("unowned-header", 'base // {nativeLibraries.answer=spec // {header="native/native-answer.h";};}',
     "Header is not a declared native resource"),
    ("changed-installed", '''base // {nativeLibraries.answer=spec;
      installCommand=copy+"\\nprintf changed >> \\\"$out/resources/libraries/libnative-answer.so\\\"";}''',
     "Installed native resource changed"),
    ("foreign-owner", '''base // {nativeLibraries.answer=spec;
      installCommand=copy+"\\nmv \\\"$out/resources/libraries/libnative-answer.so\\\" \\\"$out/resources/libraries/original.so\\\"\\nln -s ${foreign}/library.so \\\"$out/resources/libraries/libnative-answer.so\\\"";}''',
     "Foreign resource owner"),
]
for name, arguments, diagnostic in cases:
    expression = prefix + "(builder (" + arguments + ")).packages.project"
    result = subprocess.run(["nix", "build", "--impure", "--no-link", "-L", "--expr", expression],
                            capture_output=True, text=True)
    assert result.returncode != 0, (name, "unexpected success")
    assert diagnostic in result.stderr, (name, result.stderr)
    print(json.dumps({"case": name, "exitCode": result.returncode,
                      "diagnostic": result.stderr, "expression": expression}))

# No native selection: retain the existing fully custom extension path.
expression = prefix + '''(builder (base // {
buildCommand="mv META6.json META6.original";
installCommand="printf custom > \\\"$out/sentinel\\\"";
})).packages.project'''
result = subprocess.run(["nix", "build", "--impure", "--no-link", "--print-out-paths", "-L", "--expr", expression],
                        capture_output=True, text=True)
assert result.returncode == 0, result.stderr
output = Path(result.stdout.strip())
assert (output / "sentinel").read_text() == "custom"
print(json.dumps({"case": "custom-installer-without-native-selection", "exitCode": 0,
                  "output": str(output), "diagnostic": result.stderr, "expression": expression}))
