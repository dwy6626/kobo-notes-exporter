# `export-pr` Shortcut Design

## Goal

Add a short project command that runs the existing notes-repository export workflow:

```bash
uv run export-pr [export arguments]
```

The shortcut must preserve the behavior of `scripts/export_to_notes_repo.sh` and forward all trailing arguments unchanged.

## Design

Add `export-pr` to `[project.scripts]` in `pyproject.toml`. The entry point will call a small Python function in the `kobo_notes_exporter` package.

The Python wrapper will:

1. Locate `scripts/export_to_notes_repo.sh` relative to the installed editable project source.
2. Invoke it with Bash and append `sys.argv[1:]` unchanged.
3. Return the subprocess exit code so `uv run export-pr` succeeds or fails exactly as the shell workflow does.

The existing shell script remains the single source of truth for Git, GitHub CLI, Kobo export, branch, commit, push, and pull-request behavior.

## Error Handling

Missing Bash or a missing script will surface as a non-zero command failure. Errors produced by the shell script will continue to be written directly to the terminal without being captured or rewritten by the wrapper.

## Tests

Unit tests will mock subprocess execution and verify:

- the wrapper selects the repository script;
- arguments are forwarded in their original order;
- the shell process exit code is propagated.

The tests will not access a Kobo device, mutate the notes repository, or contact GitHub.

## Documentation

Update `README.md` in Traditional Chinese with the new command and an example showing optional export arguments.

## Validation

Run:

```bash
uv run python -m unittest discover -s tests
uv run python -c "from importlib.metadata import entry_points; assert entry_points(group='console_scripts', name='export-pr')"
```

Do not smoke-test the shortcut by running it: the shell workflow intentionally performs Git and GitHub operations. Automated unit tests validate delegation without external side effects.
