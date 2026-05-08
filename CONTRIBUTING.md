# Contributing

Thanks for contributing to `blackhole`.

## Development setup

Install development dependencies:

```bash
uv sync --dev
```

Run unit tests:

```bash
uv run pytest -m unit
```

Run integration tests (requires an active Linux FUSE environment):

```bash
uv run pytest -m integration
```

Pytest markers:

- `unit`: pure unit tests
- `integration`: requires real mount behavior

## Commit message policy

Required format:

```text
<type>(<scope>): <summary>

- <bullet>
- <bullet>
```

Hard requirements:

- Allowed `type` values only: `feat|fix|chore|test|revert`
- `scope` is required
- `summary` is required
- Body is required
- Body must be bullet-list-only
- Each bullet must be exactly one line

The CI `checks` workflow also validates commit messages on pull requests.
