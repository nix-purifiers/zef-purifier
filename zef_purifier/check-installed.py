"""Bind the captured native plan to the installed distribution metadata."""

import json
import sys

expected = json.load(open(sys.argv[1]))["distributions"]
actual = json.load(open(sys.argv[2]))


def identity(meta):
    return tuple(str(meta.get(key, "")) for key in ("name", "version", "auth", "api"))


installed = {identity(meta): meta for meta in actual}
assert len(installed) == len(expected), (
    "Installed distribution set differs from captured graph"
)
for record in expected:
    meta = record["meta"]
    found = installed[identity(meta)]
    for key in ("depends", "build-depends", "test-depends"):
        assert found.get(key, []) == meta.get(key, []), (record["identity"], key)
    assert set(found["provides"]) == set(meta["provides"]), record["identity"]
    for module, path in meta["provides"].items():
        assert set(found["provides"][module]) == {path}, (module, path)
