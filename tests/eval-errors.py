"""Lock shape and freshness are checked without import from derivation."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix="zef-evaluation-") as temp:
    root = Path(temp) / "project"
    shutil.copytree(repo / "examples/minimal", root)
    lock = root / "zef-purifier.lock.json"
    original = lock.read_text()
    expression = (
        f"let flake = builtins.getFlake {json.dumps('path:' + str(repo))}; "
        f"in (flake.lib.zef-purifier.readLock {{ src = /. + {json.dumps(str(root))}; }}).problems"
    )

    def problems():
        result = subprocess.run(
            [
                "nix",
                "eval",
                "--impure",
                "--option",
                "allow-import-from-derivation",
                "false",
                "--json",
                "--expr",
                expression,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    assert problems() == []
    data = json.loads(original)
    for change in (
        lambda d: d.update(version=99),
        lambda d: d["entries"][0].update(path="../escape"),
        lambda d: d["entries"][0].update(hash="unhashed"),
        lambda d: d["inputs"]["META6.json"].update(content="changed"),
        lambda d: d["distributions"][0]["meta"].update(
            provides={"escape": "../outside"}
        ),
    ):
        data = json.loads(original)
        change(data)
        lock.write_text(json.dumps(data))
        assert problems()
    lock.unlink()
    assert problems()
    lock.write_text(original)
    meta = root / "META6.json"
    meta.write_text(meta.read_text() + "\n")
    assert problems()
print("Evaluation rejects missing, stale, and malformed locks without IFD")
