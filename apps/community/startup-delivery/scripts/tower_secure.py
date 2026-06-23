#!/usr/bin/env python3
"""Run Tower from a clean staging directory so secrets are never packaged.

Tower's packager includes hidden files from the app directory. This wrapper stages
only the files the app needs, explicitly excluding `.env`, `.venv`, and
bytecode, then invokes `tower --dir <stage>`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOWER_BIN = ROOT / "agent" / ".venv" / "bin" / "tower"


def _ignore(_dir: str, names: list[str]) -> set[str]:
    blocked = {".env", ".venv", "__pycache__", ".DS_Store", ".cache", ".generated"}
    return {name for name in names if name in blocked or name.endswith((".pyc", ".pyo"))}


def _copytree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=_ignore)


def _stage_app(stage: Path) -> None:
    _copytree(ROOT / "agent", stage / "agent")
    (stage / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "tower_run.py", stage / "scripts" / "tower_run.py")
    shutil.copy2(ROOT / "requirements.txt", stage / "requirements.txt")
    shutil.copy2(ROOT / "tower" / "Towerfile", stage / "Towerfile")

    leaked_env = list(stage.rglob(".env"))
    if leaked_env:
        raise RuntimeError(f"Refusing to run: staged .env file(s): {leaked_env}")


def _dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().split(" #", 1)[0].strip().strip('"').strip("'")
    return values


def _env() -> dict[str, str]:
    env = os.environ.copy()
    for key, value in _dotenv_values(ROOT / ".env").items():
        if key not in env:
            env[key] = value
    if (ROOT / "web").exists() and "LANDING_OUTPUT_DIR" not in env:
        env["LANDING_OUTPUT_DIR"] = str(ROOT / "web" / "public" / "deliveries")
    return env


def _with_dir(args: list[str], stage: Path) -> list[str]:
    if not args:
        args = ["run", "--local"]
    if args[0] in {"run", "deploy"} and "--dir" not in args and "-d" not in args:
        return [args[0], "--dir", str(stage), *args[1:]]
    return args


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="startup-delivery-tower-") as tmp:
        stage = Path(tmp)
        _stage_app(stage)
        cmd = [str(TOWER_BIN if TOWER_BIN.exists() else "tower"), *_with_dir(sys.argv[1:], stage)]
        return subprocess.call(cmd, cwd=ROOT, env=_env())


if __name__ == "__main__":
    raise SystemExit(main())
