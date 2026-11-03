"""Exercise the installed wrappers and native Raku tools."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parent.parent


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


run(["nix", "build", ".", "--out-link", "sdk"], cwd=REPO)
sdk = (REPO / "sdk").resolve()
with tempfile.TemporaryDirectory(prefix="zef-conformance-") as temp:
    temp = Path(temp)
    project = temp / "project"
    shutil.copytree(
        REPO / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".zef-purifier", ".precomp"),
    )
    env = os.environ.copy()
    env["PATH"] = str(sdk / "bin") + ":" + env["PATH"]
    # Ambient language paths must not affect locked runs.
    poison = temp / "poison"
    poison.mkdir()
    (poison / "JSON").mkdir()
    (poison / "JSON/Marshal.rakumod").write_text('die "AMBIENT DEPENDENCY USED";\n')
    env["RAKUDOLIB"] = str(poison)
    run([sdk / "bin/zef-purifier", "prefetch"], cwd=project, env=env)
    run(["zef", "install", "."], cwd=project, env=env)
    run(["zef", "test", "."], cwd=project, env=env)
    trace_env = env | {"RAKUDO_MODULE_DEBUG": "1"}
    trace = run(
        ["raku", "-Ilib", "t/basic.rakutest"],
        cwd=project,
        env=trace_env,
        capture_output=True,
        text=True,
    )
    assert "ok 1" in trace.stdout
    assert "Precompiling /nix/store/" not in trace.stderr, trace.stderr
    assert "/repo/precomp" in trace.stderr, trace.stderr
    # Locate a dependency through Rakudo's own repository API.
    location = run(
        [
            "raku",
            "-e",
            'say $*REPO.resolve(CompUnit::DependencySpecification.new(:short-name("JSON::Marshal"))).repo.prefix.Str',
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )
    assert location.stdout.startswith("/nix/store/"), location.stdout
    original = (project / "lib/Purifier/Example.rakumod").read_text()
    (project / "lib/Purifier/Example.rakumod").write_text(original.replace("42", "43"))
    failed = subprocess.run(
        ["raku", "-Ilib", "t/basic.rakutest"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )
    assert failed.returncode != 0 and "not ok" in failed.stdout, failed
    (project / "lib/Purifier/Example.rakumod").write_text(original)
    run(["raku", "-Ilib", "t/basic.rakutest"], cwd=project, env=env)
    companion = project / "zef-purifier.lock.json"
    before = companion.read_bytes()
    run(["zef-purifier", "lock"], cwd=project, env=env)
    assert companion.read_bytes() == before
    external = temp / "external.json"
    companion.rename(external)
    selected = env | {
        "ZEF_PURIFIER_PROJECT": str(project),
        "ZEF_PURIFIER_LOCK": str(external),
    }
    child = run(
        [
            "zef-purifier",
            "--project",
            project,
            "--lock-file",
            external,
            "exec",
            "--",
            "raku",
            "-Ilib",
            "t/basic.rakutest",
        ],
        cwd=project,
        env=selected,
        capture_output=True,
        text=True,
    )
    assert "ok 1" in child.stdout, child
    external.rename(companion)
    meta = project / "META6.json"
    original_meta = meta.read_text()
    meta.write_text(original_meta + "\n")
    stale = subprocess.run(
        ["raku", "-Ilib", "t/basic.rakutest"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )
    assert stale.returncode != 0 and "changed" in stale.stderr, stale
    meta.write_text(original_meta)
    # The source release must install with ordinary zef and execute outside the source tree.
    prepared = run(
        ["zef-purifier", "exec", "--", "env"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )
    consumer_env = dict(
        line.split("=", 1) for line in prepared.stdout.splitlines() if "=" in line
    )
    consumer_env.pop("ZEF_PURIFIER_FROZEN", None)
    release = run(
        ["zef-purifier", "release"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )
    artifact = Path(release.stdout.strip()) / "source.tar.gz"
    assert artifact.is_file()
    fake_gh = temp / "gh"
    fake_gh.write_text(
        "#!/usr/bin/env python3\n"
        "import os,pathlib,shutil,sys\n"
        "if sys.argv[1:3] == ['release','view']: sys.exit(int(os.environ['FAKE_VIEW']))\n"
        "for arg in sys.argv[3:]:\n"
        " p=pathlib.Path(arg)\n"
        " if p.name=='source.tar.gz': shutil.copyfile(p,os.environ['FAKE_ARTIFACT'])\n"
    )
    fake_gh.chmod(0o755)
    for exists in (False, True):
        copied = temp / ("uploaded.tar.gz" if exists else "created.tar.gz")
        run(
            ["zef-purifier", "publish", "--repo", "fixture/project", "--tag", "v1"],
            cwd=project,
            env=env
            | {
                "ZEF_PURIFIER_GH": str(fake_gh),
                "FAKE_VIEW": "0" if exists else "1",
                "FAKE_ARTIFACT": str(copied),
            },
        )
        assert copied.read_bytes() == artifact.read_bytes()
    consumer = temp / "consumer"
    consumer.mkdir()
    (consumer / "repo").mkdir()
    run(
        [
            consumer_env["ZEF_PURIFIER_NATIVE_ZEF"],
            "--/update",
            "--/depends",
            "--/build-depends",
            "--/test-depends",
            "--/test",
            "--install-to=" + str(consumer / "repo"),
            "install",
            artifact,
        ],
        cwd=consumer,
        env=consumer_env,
    )
    result = run(
        [
            consumer_env["ZEF_PURIFIER_NATIVE_RAKU"],
            "-Iinst#" + str(consumer / "repo"),
            "-e",
            "use Purifier::Example; say serialized()",
        ],
        cwd=consumer,
        env=consumer_env,
        capture_output=True,
        text=True,
    )
    assert '"answer":42' in result.stdout, result
    # No-lock fallback preserves the ordinary tool's bytes and status.
    unlocked = temp / "unlocked"
    unlocked.mkdir()
    for tool, command in (
        ("raku", ["-e", 'say "fallback"; note "native stderr"; exit 7']),
        ("zef", ["--version"]),
    ):
        baseline = subprocess.run(
            [str(sdk / "bin/zef-purifier"), "exec", "--", "env"],
            cwd=unlocked,
            env=env,
            capture_output=True,
            text=True,
        )
        native_path = dict(
            line.split("=", 1) for line in baseline.stdout.splitlines() if "=" in line
        )["ZEF_PURIFIER_NATIVE_" + tool.upper()]
        ordinary = subprocess.run(
            [native_path, *command], cwd=unlocked, env=env, capture_output=True
        )
        wrapped = subprocess.run(
            [tool, *command], cwd=unlocked, env=env, capture_output=True
        )
        assert wrapped.returncode == ordinary.returncode
        assert wrapped.stdout == ordinary.stdout
        assert (
            wrapped.stderr
            == b"warning: no zef-purifier lockfile; using ordinary impure resolution\n"
            + ordinary.stderr
        )
print("Raku conformance passed")
