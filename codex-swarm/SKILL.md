---
name: codex-swarm
description: Run Codex CLI jobs inside subdirectories of the current working directory using JSON-only batch input and optional parallelism. Use when you need to execute codex exec --model gpt-5.2-codex across one or more subdirectories with strict safety checks (no '..', no current dir, cwd boundary enforced).
---

# Codex Swarm

## Overview
Run Codex CLI tasks inside cwd subdirectories only, using structured JSON input and optional parallel execution. Use this skill to orchestrate multiple Codex runs across sibling folders safely.

## Quick Start
Run from the workspace root that should act as the boundary:

```bash
echo '{"jobs":[{"dir":"services/api","task":"Add health check endpoint."},{"dir":"services/worker","task":"Document retry policy."}],"max_parallel":2}' \
  | python3 scripts/codex_swarm.py
```

## Input Schema
Provide JSON via stdin only.

```json
{
  "jobs": [
    {"dir": "relative/path", "task": "..."}
  ],
  "max_parallel": 2
}
```

Rules:
- Require `jobs` as a non-empty array.
- Require each job to include `dir` and `task` as non-empty strings.
- Forbid current directory (`.`) and any `..` segment.
- Forbid absolute paths or `~`-prefixed paths.
- Require `dir` to exist and resolve inside the current working directory.
- Use `max_parallel` as an optional positive integer; default to `min(4, len(jobs))`.

## Behavior
- Resolve each `dir` against `pwd` and reject paths outside.
- Run `codex exec --model gpt-5.2-codex --full-auto --skip-git-repo-check "<task>"` in each target directory.
- Execute jobs in parallel up to `max_parallel`.
- Log `cwd`, job count, each job's resolved dir, command, and exit code to stderr.

## Scripts
- `scripts/codex_swarm.py`: JSON-only runner with safety checks and parallel execution.

## Troubleshooting
- If Codex fails with a permissions error accessing `~/.codex/sessions`, fix ownership and retry:
  - `sudo chown -R $(whoami) /home/<your-user-name>/.codex/sessions`
- If you can't or don't want to use sudo, alternatives:
  - Check current ownership/permissions: `ls -ld /home/<your-user-name>/.codex /home/<your-user-name>/.codex/sessions`
  - Verify your umask isn't too restrictive (e.g. `umask 0022`) before launching Codex again.
  - Recreate the sessions directory (only if it's safe for you to do so): `mv /home/<your-user-name>/.codex/sessions /home/<your-user-name>/.codex/sessions.bak && mkdir -p /home/<your-user-name>/.codex/sessions`
