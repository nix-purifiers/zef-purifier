"""Bind declared native artifacts to the SDK's actual resource mapping."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

source, output, metadata, specifications, nm, system, original_inputs = sys.argv[1:]
source, output = Path(source).resolve(), Path(output).resolve()
meta = json.loads(Path(metadata).read_text())
specs = json.loads(Path(specifications).read_text())
files = meta.get("files", {})
declared = {"resources/" + name for name in meta.get("resources", [])}
records = {}
for name, spec in specs.items():
    key = "resources/" + spec["resource"]
    assert key in declared and files.get(key) == spec["library"], "Resource/library selector mismatch"
    original = (source / spec["library"]).resolve(strict=True)
    installed = (output / spec["library"]).resolve(strict=True)
    assert original.is_relative_to(source) and installed.is_relative_to(output), "Foreign resource owner"
    assert original.read_bytes() == installed.read_bytes(), "Installed native resource changed"
    elf = installed.read_bytes()
    assert elf[:4] == b"\x7fELF", "Expected native ELF resource"
    endian = "<" if elf[5] == 1 else ">"
    machine = struct.unpack_from(endian + "H", elf, 18)[0]
    assert machine == {"x86_64-linux": 62, "aarch64-linux": 183}[system], "Foreign native architecture"
    symbols = subprocess.check_output([nm, "-D", "--defined-only", str(installed)], text=True)
    callable_symbols = {line.split()[-1] for line in symbols.splitlines()
                        if len(line.split()) >= 3 and line.split()[-2] in ("T", "W")}
    assert set(spec["exports"]).issubset(callable_symbols), "Missing callable native export"
    header = spec.get("header")
    if header:
        assert header in [files[key] for key in declared], "Header is not a declared native resource"
        before, after = (source / header).resolve(strict=True), (output / header).resolve(strict=True)
        assert before.is_relative_to(source) and after.is_relative_to(output), "Foreign header owner"
        assert before.read_bytes() == after.read_bytes(), "Installed header changed"
    env = {key: value for key, value in os.environ.items() if not key.startswith("LD_")}
    subprocess.run([sys.executable, "-c", "import ctypes,sys; ctypes.CDLL(sys.argv[1])", str(installed)],
                   env=env, check=True)
    records[name] = {**spec, "nativePath": str(installed),
                     "sha256": hashlib.sha256(elf).hexdigest(),
                     "headerSha256": hashlib.sha256((output / header).read_bytes()).hexdigest() if header else None,
                     "nativeResourceKey": key}
support = output / "nix-support/zef-native"
support.mkdir(parents=True, exist_ok=True)
authored = {}
after_build = {}
for original in sorted(Path(original_inputs).rglob("*")):
    if original.is_file():
        relative = original.relative_to(original_inputs)
        authored[str(relative)] = hashlib.sha256(original.read_bytes()).hexdigest()
        current = source / relative
        after_build[str(relative)] = hashlib.sha256(current.read_bytes()).hexdigest() if current.is_file() else None
(support / "verified-resources.json").write_text(json.dumps({"sdkMetadata": meta, "libraries": records,
                                                           "authoredInputs": authored, "postBuildInputs": after_build},
                                                          sort_keys=True, indent=2) + "\n")
