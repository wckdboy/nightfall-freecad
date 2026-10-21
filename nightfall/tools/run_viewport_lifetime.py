#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Nightfall Authors
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bound one unmodified-runtime reproduction; retain failures as failures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freecad", type=Path, required=True, help="GUI executable")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--case", choices=("control", "wrap", "qt_escape"), required=True)
    parser.add_argument("--close", choices=("document", "window", "quit"), required=True)
    parser.add_argument("--release-wrapper", action="store_true")
    parser.add_argument("--invalidate-before-close", action="store_true")
    parser.add_argument("--invalidate-on-destroy", action="store_true")
    parser.add_argument("--quit-delay-ms", type=int, choices=(0, 300), default=300)
    args = parser.parse_args()
    macro = Path(__file__).resolve().parents[1] / "tests/ViewportLifetime.FCMacro"
    binary = args.freecad.resolve(strict=True)
    out = args.output_root.resolve() / ("viewport-" + uuid.uuid4().hex)
    out.mkdir(parents=True)
    inputs = {str(path): sha(path) for path in (macro, Path(__file__).resolve(), binary)}
    command = [
        str(binary),
        "--user-cfg",
        str(out / "user.cfg"),
        "--system-cfg",
        str(out / "system.cfg"),
        str(macro),
    ]
    env = {
        key: os.environ[key]
        for key in (
            "PATH",
            "HOME",
            "TMPDIR",
            "LANG",
            "LC_ALL",
            "SHELL",
            "USER",
            "LOGNAME",
            "__CF_USER_TEXT_ENCODING",
        )
        if key in os.environ
    }
    env.update(
        NIGHTFALL_REPRO_OUTPUT=str(out),
        NIGHTFALL_REPRO_CASE=args.case,
        NIGHTFALL_REPRO_CLOSE=args.close,
        NIGHTFALL_REPRO_RELEASE="1" if args.release_wrapper else "0",
        NIGHTFALL_REPRO_INVALIDATE="1" if args.invalidate_before_close else "0",
        NIGHTFALL_REPRO_DESTROY_HOOK="1" if args.invalidate_on_destroy else "0",
        NIGHTFALL_REPRO_QUIT_DELAY=str(args.quit_delay_ms),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONOPTIMIZE="0",
    )
    record = {
        "kind": "nightfall-viewport-lifetime-run",
        "command": command,
        "case": args.case,
        "close": args.close,
        "release_wrapper": args.release_wrapper,
        "invalidate_before_close": args.invalidate_before_close,
        "invalidate_on_destroy": args.invalidate_on_destroy,
        "quit_delay_ms": args.quit_delay_ms,
        "input_sha256": inputs,
        "limit_seconds": 120,
        "inherited_environment_keys": sorted(set(env) & set(os.environ)),
        "scope": "Official GUI runtime, native box, no Nightfall module, no accessibility query",
    }
    start = time.perf_counter()
    with (out / "stdout.log").open("w") as stdout, (out / "stderr.log").open("w") as stderr:
        process = subprocess.Popen(
            command,
            cwd=out,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        record["pid"] = process.pid
        try:
            record["returncode"] = process.wait(timeout=120)
            record["timeout"] = False
        except subprocess.TimeoutExpired:
            record["timeout"] = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            record["returncode"] = process.returncode
    record["elapsed_seconds"] = time.perf_counter() - start
    record["input_changed_during_run"] = any(
        sha(Path(path)) != value for path, value in inputs.items()
    )
    for path in (macro, Path(__file__).resolve()):
        shutil.copy2(path, out / path.name)
    result = out / "reproduction.json"
    report = json.loads(result.read_text()) if result.exists() else {}
    record["passed"] = (
        record["returncode"] == 0
        and not record["timeout"]
        and not record["input_changed_during_run"]
        and report.get("exercise_complete") is True
        and not report.get("error")
    )
    (out / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: record[key]
                for key in (
                    "case",
                    "close",
                    "release_wrapper",
                    "invalidate_before_close",
                    "invalidate_on_destroy",
                    "quit_delay_ms",
                    "returncode",
                    "timeout",
                    "elapsed_seconds",
                    "passed",
                )
            }
            | {"artifact_directory": str(out)},
            indent=2,
        ),
        flush=True,
    )
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
