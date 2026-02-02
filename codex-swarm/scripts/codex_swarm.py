#!/usr/bin/env python3
import json
import os
import shlex
import subprocess
import sys
import threading
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


def run_job(index, total, target, task, lock):
    cmd = [
        "codex",
        "exec",
        "--model",
        "gpt-5.2-codex",
        "--full-auto",
        "--skip-git-repo-check",
        task,
    ]
    with lock:
        eprint(f"[job {index}/{total}] dir={target}")
        eprint(f"[job {index}/{total}] cmd={log_command(cmd)}")
    proc = subprocess.run(cmd, cwd=str(target))
    rc = proc.returncode
    with lock:
        eprint(f"[job {index}/{total}] exit={rc}")
    return rc


def main():
    data = load_input()
    jobs, max_parallel = validate_jobs(data)
    cwd = Path.cwd().resolve()
    eprint(f"[codex-swarm] cwd={cwd}")
    eprint(f"[codex-swarm] jobs={len(jobs)} max_parallel={max_parallel}")

    resolved = []
    for idx, job in enumerate(jobs, start=1):
        dir_raw, task = validate_job(job)
        target = resolve_dir(dir_raw, cwd)
        resolved.append((idx, target, task))

    lock = threading.Lock()
    overall_rc = 0
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = [
            executor.submit(run_job, idx, len(resolved), target, task, lock)
            for idx, target, task in resolved
        ]
        for future in as_completed(futures):
            rc = future.result()
            if rc != 0:
                overall_rc = 1
    sys.exit(overall_rc)


if __name__ == "__main__":
    main()
