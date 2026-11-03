"""Native zef source capture and isolated Raku sessions."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

LOCK = "zef-purifier.lock.json"
HERE = Path(__file__).resolve().parent.parent


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def native(tool):
    return os.environ["ZEF_PURIFIER_NATIVE_" + tool.upper()]


def versions():
    return {
        key.lower(): os.environ["ZEF_PURIFIER_" + key + "_VERSION"]
        for key in ("SDK", "RAKUDO", "ZEF", "GCC")
    }


def clean_env(home):
    env = os.environ.copy()
    for key in list(env):
        if key != "RAKUDO_MODULE_DEBUG" and key.startswith(
            (
                "RAKUDO",
                "RAKULIB",
                "PERL6LIB",
                "ZEF_CONFIG",
                "ZEF_INSTALL",
                "ZEF_PURIFIER_CAPTURE",
            )
        ):
            env.pop(key)
    for key, leaf in (
        ("HOME", "home"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_CONFIG_HOME", "config"),
        ("ZEF_CONFIG_TEMPDIR", "tmp"),
        ("ZEF_CONFIG_STOREDIR", "store"),
    ):
        path = home / leaf
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    return env


def lock(root, companion, update=False):
    previous = json.loads(companion.read_text()) if companion.exists() else None
    meta = root / "META6.json"
    text = meta.read_text()
    if previous and not update:
        validate(root, previous)
        print(f"Retained {companion}")
        return
    with tempfile.TemporaryDirectory(prefix="zef-purifier-") as temp:
        temp = Path(temp)
        work = temp / "project"
        work.mkdir()
        (work / "META6.json").write_text(text)
        # zef checks root provides when discovering the distribution.
        for source in json.loads(text).get("provides", {}).values():
            source = Path(source)
            if source.is_absolute() or ".." in source.parts:
                raise ValueError("META6 provides must stay inside the project")
            path = work / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Source-only resolution placeholder\n")
        env = clean_env(temp)
        capture = temp / "capture.json"
        env["ZEF_PURIFIER_CAPTURE"] = str(capture)
        archive_dir = Path(str(capture) + ".archives")
        archive_dir.mkdir()
        run(
            [
                native("zef"),
                "--deps-only",
                "--dry",
                "--/build",
                "--/test",
                "--build-depends",
                "--test-depends",
                "install",
                ".",
            ],
            cwd=work,
            env=env,
        )
        records = json.loads(capture.read_text()) if capture.exists() else []
        archives = {}
        for path in archive_dir.glob("*.json"):
            item = json.loads(path.read_text())
            blob = archive_dir / item["file"]
            item["hash"] = (
                "sha256-"
                + base64.b64encode(hashlib.sha256(blob.read_bytes()).digest()).decode()
            )
            archives[item["identity"]] = item
        entries, distributions = [], []
        for i, record in enumerate(records):
            item = archives.get(record["identity"])
            if item is None or not item["url"].startswith("https://"):
                raise ValueError(
                    "Only captured HTTPS distribution archives are currently supported: "
                    + record["identity"]
                )
            path = f"archives/{i:04d}.tar.gz"
            entries.append(
                {"path": path, "url": item["url"], "hash": item["hash"], "mirrors": []}
            )
            distributions.append(
                {
                    "identity": record["identity"],
                    "request": record["request"],
                    "meta": record["meta"],
                    "path": path,
                }
            )
        data = {
            "version": 1,
            "purifier": "zef",
            "toolVersions": versions(),
            "inputs": {
                "META6.json": {
                    "content": text,
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
            },
            "distributions": distributions,
            "entries": entries,
        }
        validate(root, data)
        companion.parent.mkdir(parents=True, exist_ok=True)
        pending = companion.with_name(companion.name + ".tmp")
        pending.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        pending.replace(companion)
    print(f"Locked {len(entries)} distributions in {companion}")


def validate(root, data):
    if data.get("version") != 1 or data.get("purifier") != "zef":
        raise ValueError("Invalid zef-purifier lock")
    if data.get("toolVersions") != versions():
        raise ValueError("Raku SDK changed; run zef-purifier lock --update")
    for name, value in data["inputs"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Invalid input path")
        path = root / name
        if (
            not path.is_relative_to(root)
            or path.resolve() != path
            or not path.is_file()
        ):
            raise ValueError("Project inputs must be regular files inside the project")
        if (
            hashlib.sha256(path.read_bytes()).hexdigest() != value["sha256"]
            or path.read_text() != value["content"]
        ):
            raise ValueError("META6.json changed; run zef-purifier lock --update")


def realize(root, companion, target="environment"):
    state = root / ".zef-purifier"
    state.mkdir(exist_ok=True)
    link = state / target
    run(
        [
            "nix",
            "build",
            "--impure",
            "--file",
            HERE / "nix/realize.nix",
            "--argstr",
            "project",
            root,
            "--argstr",
            "companion",
            companion,
            "--argstr",
            "target",
            target,
            "--out-link",
            link,
        ],
        stdout=sys.stderr,
    )
    sdk_root = state / "sdk"
    run(
        [
            "nix-store",
            "--add-root",
            sdk_root,
            "--indirect",
            "--realise",
            os.environ["ZEF_PURIFIER_SDK"],
        ],
        stdout=sys.stderr,
    )
    return link.resolve()


def locate():
    explicit = os.environ.get("ZEF_PURIFIER_LOCK")
    root = os.environ.get("ZEF_PURIFIER_PROJECT")
    if explicit:
        return Path(root or Path(explicit).parent).resolve(), Path(explicit).resolve()
    for directory in (Path.cwd(), *Path.cwd().parents):
        if (directory / LOCK).exists():
            return directory, directory / LOCK
    return Path.cwd(), Path.cwd() / LOCK


def execute(root, companion, args, tool=None):
    if not companion.exists():
        print(
            "warning: no zef-purifier lockfile; using ordinary impure resolution",
            file=sys.stderr,
        )
        command = [native(tool), *args] if tool else args
        os.execvpe(str(command[0]), [str(x) for x in command], os.environ.copy())
    data = json.loads(companion.read_text())
    validate(root, data)
    environment = realize(root, companion)
    env = clean_env(root / ".zef-purifier/session")
    env["RAKUDOLIB"] = "inst#" + str(environment / "repo")
    env["ZEF_PURIFIER_FROZEN"] = "1"
    env["ZEF_PURIFIER_PROJECT"] = str(root)
    env["ZEF_PURIFIER_LOCK"] = str(companion)
    env["PATH"] = os.environ["ZEF_PURIFIER_SDK"] + "/bin:" + env["PATH"]
    if tool == "zef" and any(
        x in args for x in ("update", "upgrade", "fetch", "nuke", "uninstall")
    ):
        raise ValueError(
            "This command changes dependency resolution; edit META6.json and run lock --update"
        )
    command = [native(tool), *args] if tool else args
    os.execvpe(str(command[0]), [str(x) for x in command], env)


def main():
    try:
        if sys.argv[1:2] == ["--native"]:
            tool = sys.argv[2].split("=", 1)[1]
            root, companion = locate()
            execute(root, companion, sys.argv[4:], tool)
            return
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--project", type=Path, default=Path.cwd())
        parser.add_argument("--lock-file", type=Path)
        sub = parser.add_subparsers(dest="command", required=True)
        p = sub.add_parser("lock")
        p.add_argument("--update", action="store_true")
        sub.add_parser("prefetch")
        sub.add_parser("release")
        p = sub.add_parser("publish")
        p.add_argument("--repo", required=True)
        p.add_argument("--tag", required=True)
        p = sub.add_parser("exec")
        p.add_argument("args", nargs=argparse.REMAINDER)
        args = parser.parse_args()
        root = args.project.resolve()
        companion = (args.lock_file or root / LOCK).resolve()
        if args.command == "lock":
            lock(root, companion, args.update)
        elif args.command == "exec":
            command = args.args[1:] if args.args[:1] == ["--"] else args.args
            if not command:
                raise ValueError("exec requires a command")
            execute(root, companion, command)
        else:
            validate(root, json.loads(companion.read_text()))
            output = realize(
                root,
                companion,
                "release" if args.command in ("release", "publish") else "environment",
            )
            if args.command == "publish":
                gh = os.environ.get("ZEF_PURIFIER_GH", "gh")
                found = subprocess.run(
                    [gh, "release", "view", args.tag, "--repo", args.repo],
                    capture_output=True,
                )
                if found.returncode == 0:
                    run(
                        [
                            gh,
                            "release",
                            "upload",
                            args.tag,
                            output / "source.tar.gz",
                            "--clobber",
                            "--repo",
                            args.repo,
                        ]
                    )
                else:
                    run(
                        [
                            gh,
                            "release",
                            "create",
                            args.tag,
                            output / "source.tar.gz",
                            "--repo",
                            args.repo,
                            "--title",
                            args.tag,
                            "--notes",
                            "Locked Raku project source release",
                        ]
                    )
            else:
                print(output)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"zef-purifier: {error}", file=sys.stderr)
        sys.exit(1)
