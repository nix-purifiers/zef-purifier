"""Copy native SDK-declared resources without changing META6 or library layout."""
import json
from pathlib import Path, PurePosixPath
import shutil
import sys

source, destination, metadata = map(Path, sys.argv[1:])
root = source.resolve()
meta = json.loads(metadata.read_text())
for logical, physical in meta.get("files", {}).items():
    if not logical.startswith("resources/"):
        continue
    relative = PurePosixPath(physical)
    assert not relative.is_absolute() and ".." not in relative.parts, physical
    assert relative.parts[0] == "resources", physical
    original = (source / physical).resolve(strict=True)
    assert original.is_relative_to(root) and original.is_file(), physical
    output = destination / physical
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, output)
    assert output.read_bytes() == original.read_bytes(), physical
    assert output.stat().st_mode & 0o777 == original.stat().st_mode & 0o777, physical
