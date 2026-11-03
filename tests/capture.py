"""Native relocking, updates, and an SDK-only dependency graph."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
subprocess.run(["nix", "build", ".", "--out-link", "sdk"], cwd=repo, check=True)
sdk = (repo / "sdk").resolve()
env = os.environ.copy()
env["PATH"] = str(sdk / "bin") + ":" + env["PATH"]


def command(root, *args):
    subprocess.run(
        [str(sdk / "bin/zef-purifier"), "--project", str(root), *args],
        env=env,
        check=True,
    )


with tempfile.TemporaryDirectory(prefix="zef-native-capture-") as temp:
    root = Path(temp) / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".zef-purifier", ".precomp"),
    )
    meta = root / "META6.json"
    data = json.loads(meta.read_text())
    data["test-depends"] = ["Test", "JSON::Fast:ver<0.20>"]
    meta.write_text(json.dumps(data, indent=2) + "\n")
    command(root, "lock", "--update")
    lock = root / "zef-purifier.lock.json"
    pinned = json.loads(lock.read_text())
    assert any(
        d["meta"]["name"] == "JSON::Fast" and d["meta"]["version"] == "0.20"
        for d in pinned["distributions"]
    ), pinned
    command(root, "prefetch")
    subprocess.run(["raku", "-Ilib", "t/basic.rakutest"], cwd=root, env=env, check=True)
    data["test-depends"] = ["Test", "JSON::Fast"]
    meta.write_text(json.dumps(data, indent=2) + "\n")
    command(root, "lock", "--update")
    upgraded = json.loads(lock.read_text())
    assert any(
        d["meta"]["name"] == "JSON::Fast" and d["meta"]["version"] != "0.20"
        for d in upgraded["distributions"]
    )
    command(root, "prefetch")
    # Test is supplied by the pinned Rakudo SDK, not fetched from an ecosystem mirror.
    data["depends"] = []
    data["test-depends"] = ["Test"]
    meta.write_text(json.dumps(data, indent=2) + "\n")
    command(root, "lock", "--update")
    empty = json.loads(lock.read_text())
    assert empty["entries"] == [] and empty["distributions"] == []
    command(root, "prefetch")
    subprocess.run(
        ["raku", "-e", 'use Test; ok 1, "SDK core dependency"; done-testing'],
        cwd=root,
        env=env,
        check=True,
    )
print("Native capture, update, and empty graph passed")
