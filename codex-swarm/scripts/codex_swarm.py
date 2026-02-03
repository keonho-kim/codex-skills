#!/usr/bin/env python3
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def eprint(*args):
    print(*args, file=sys.stderr, flush=True)


def fail(message, code=2):
    eprint(f"error: {message}")
    sys.exit(code)


def load_input():
    if sys.stdin.isatty():
        fail("no JSON provided on stdin")
    try:
        return json.load(sys.stdin)
    except Exception as exc:
        fail(f"invalid JSON on stdin ({exc})")


def validate_jobs(data):
    if not isinstance(data, dict):
        fail("top-level JSON must be an object")
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        fail("'jobs' must be a non-empty array")
    max_parallel = data.get("max_parallel")
    if max_parallel is None:
        max_parallel = min(4, len(jobs))
    elif not isinstance(max_parallel, int) or max_parallel < 1:
        fail("'max_parallel' must be a positive integer")
    return jobs, max_parallel


def validate_job(job):
    if not isinstance(job, dict):
        fail("each job must be an object with 'dir' and 'task'")
    dir_raw = job.get("dir")
    task = job.get("task")
    if not isinstance(dir_raw, str) or not dir_raw.strip():
        fail("job.dir must be a non-empty string")
    if not isinstance(task, str) or not task.strip():
        fail("job.task must be a non-empty string")
    return dir_raw.strip(), task


def resolve_dir(dir_raw, cwd):
    if dir_raw.startswith("~") or os.path.isabs(dir_raw):
        fail(f"dir '{dir_raw}' must be a relative subdirectory of cwd")
    if dir_raw in (".", "./"):
        fail("dir cannot be current directory")
    parts = Path(dir_raw).parts
    if any(part == ".." for part in parts):
        fail(f"dir '{dir_raw}' must not contain '..'")
    target = (cwd / dir_raw).resolve()
    try:
        target.relative_to(cwd)
    except ValueError:
        fail(f"dir '{dir_raw}' resolves outside cwd")
    if target == cwd:
        fail("dir cannot resolve to cwd")
    if not target.is_dir():
        fail(f"dir '{dir_raw}' does not exist or is not a directory")
    return target


def log_command(cmd):
    return " ".join(shlex.quote(part) for part in cmd)


def make_run_codex_home() -> Path:
    """
    Create a unique base dir under ~/.codex-swarm for this run, using UUID.
    Example: ~/.codex-swarm/run-<uuid>/
      ├─ job-1-<uuid8>/
      ├─ job-2-<uuid8>/
      ...
    """
    root = Path.home() / ".codex-swarm"
    root.mkdir(parents=True, exist_ok=True)

    base = root / f"run-{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=False)
    return base




def use_codex_home_passthrough() -> bool:
    val = os.environ.get("CODEX_HOME_PASSTHROUGH", "").strip().lower()
    if val == "":
        return True
    return val in ("1", "true", "yes")
def run_job(index, total, target, task, lock, base_codex_home: Path | None, codex_home_env: str):
    # Each job gets its own Codex home to avoid session lock contention.
    job_codex_home = None
    if base_codex_home is not None:
        job_codex_home = base_codex_home / f"job-{index}-{uuid.uuid4().hex[:8]}"
        job_codex_home.mkdir(parents=True, exist_ok=True)

    cmd = [
        "codex",
        "exec",
        "--model",
        "gpt-5.2-codex",
        "--full-auto",
		"--skip-git-repo-check",
        task,
    ]

    env = os.environ.copy()
    if job_codex_home is not None:
        env[codex_home_env] = str(job_codex_home)

    with lock:
        eprint(f"[job {index}/{total}] dir={target}")
        eprint(f"[job {index}/{total}] cmd={log_command(cmd)}")
        if job_codex_home is None:
            eprint(f"[job {index}/{total}] {codex_home_env}=<passthrough>")
        else:
            eprint(f"[job {index}/{total}] {codex_home_env}={job_codex_home}")

    proc = subprocess.run(cmd, cwd=str(target), env=env)
    rc = proc.returncode

    with lock:
        eprint(f"[job {index}/{total}] exit={rc}")

    return rc


def main():
    data = load_input()
    jobs, max_parallel = validate_jobs(data)
    cwd = Path.cwd().resolve()

    # Env var name can vary by environment; default to CODEX_HOME.
    # Override via: CODEX_HOME_ENV=YOUR_VAR_NAME
    codex_home_env = os.environ.get("CODEX_HOME_ENV", "CODEX_HOME").strip() or "CODEX_HOME"

    passthrough = use_codex_home_passthrough()
    base_codex_home = None if passthrough else make_run_codex_home()

    eprint(f"[codex-swarm] cwd={cwd}")
    eprint(f"[codex-swarm] jobs={len(jobs)} max_parallel={max_parallel}")
    if base_codex_home is None:
        eprint(f"[codex-swarm] base_codex_home=<passthrough>")
    else:
        eprint(f"[codex-swarm] base_codex_home={base_codex_home}")
    eprint(f"[codex-swarm] codex_home_env={codex_home_env}")

    resolved = []
    for idx, job in enumerate(jobs, start=1):
        dir_raw, task = validate_job(job)
        target = resolve_dir(dir_raw, cwd)
        resolved.append((idx, target, task))

    lock = threading.Lock()
    overall_rc = 0

    try:
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = [
                executor.submit(run_job, idx, len(resolved), target, task, lock, base_codex_home, codex_home_env)
                for idx, target, task in resolved
            ]
            for future in as_completed(futures):
                rc = future.result()
                if rc != 0:
                    overall_rc = 1
    finally:
        # Always cleanup when we created a run home
        if base_codex_home is not None:
            shutil.rmtree(base_codex_home, ignore_errors=True)
            with lock:
                eprint(f"[codex-swarm] cleaned up {base_codex_home}")

    sys.exit(overall_rc)


if __name__ == "__main__":
    main()

