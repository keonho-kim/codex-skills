# Codex Swarm Rules (Reference)

## Input schema
- JSON only via stdin.
- Required: jobs[] with {dir, task}.
- Optional: max_parallel (positive integer).

## Safety rules
- dir must be a non-empty relative path.
- No "." or ".." segments.
- No absolute paths or "~".
- dir must exist under the current working directory.

## Execution
- Each job runs: codex exec --model gpt-5.2-codex --full-auto --skip-git-repo-check "<task>".
- Runs in parallel up to max_parallel.
