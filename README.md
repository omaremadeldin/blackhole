# blackhole

`blackhole` is a Linux FUSE filesystem overlay that gives you **immutable
reads** and **zero-persistence writes**.

- Reads come from a configured source (or optional override source).
- Writes appear successful to callers but are discarded (blackholed), depending
  on mode.
- Can run in foreground or be registered as a systemd user service.

## What it does

`blackhole` supports two mount modes:

1. **Directory mode** (`mount dir`)
   - Mount a directory view backed by `--source-dir`
   - Optional `--override-dir` takes precedence per relative path
   - Writes/truncates are discarded
   - create/mkdir/unlink/rmdir are synthetic/ephemeral (in-memory only)

2. **Single-file mode** (`mount file`)
   - Mount at the target file’s parent directory and blackhole only the target
     file path
   - Optional `--override-file` replaces reads for the target file
   - Sibling files in the same directory are passthrough to the real filesystem

---

## Requirements

- Linux
- Python **3.13+**
- FUSE userspace support (`fusepy` is used by the package)
- For service workflows: `systemd --user` and `fusermount3`

---

## Installation

### With `uv` (recommended)

```bash
uv sync
uv pip install -e .
```

### With `pip`

```bash
pip install .
```

After installation, the CLI entrypoint is:

```bash
blackhole
```

---

## CLI

```bash
blackhole mount file --target <file> [--override-file <file>] [--persistent] [--service-name <name>]
blackhole mount dir  --mount-point <dir> --source-dir <dir> [--override-dir <dir>] [--persistent] [--service-name <name>]
blackhole install-service
blackhole unmount <name>
```

### Notes

- `--service-name` requires `--persistent`.
- Paths are resolved to absolute paths.
- Legacy mount flags are rejected by the parser.

---

## Usage Examples

## 1) Directory mode (pure blackhole writes)

```bash
blackhole mount dir \
  --mount-point /tmp/mnt \
  --source-dir /srv/data
```

Behavior:

- Reading `/tmp/mnt/file.txt` reads from `/srv/data/file.txt`
- Writing `/tmp/mnt/file.txt` reports success but does not modify
  `/srv/data/file.txt`

## 2) Directory mode with override

```bash
blackhole mount dir \
  --mount-point /tmp/mnt \
  --source-dir /srv/data \
  --override-dir /srv/override
```

Behavior:

- If `/srv/override/path/to/x` exists, reads use it
- Otherwise reads fall back to `/srv/data/path/to/x`

## 3) Single-file mode

```bash
blackhole mount file --target /tmp/mnt/target.txt
```

Behavior:

- `/tmp/mnt/target.txt` is blackholed for writes
- Other files in `/tmp/mnt` are passthrough and can be modified normally

## 4) Single-file mode with override file

```bash
blackhole mount file \
  --target /tmp/mnt/target.txt \
  --override-file /tmp/source.txt
```

Behavior:

- Reads of `target.txt` come from `/tmp/source.txt`
- Writes to `target.txt` are discarded
- Override file is not mutated by writes through mount

---

## Persistent mode (systemd user service)

Persistent mode registers a `blackhole@.service` user unit instance and exits.

### Step 1: Install the service template

```bash
blackhole install-service
```

Installs to:

```text
~/.config/systemd/user/blackhole@.service
```

### Step 2: Register a persistent mount

```bash
blackhole mount dir \
  --mount-point /tmp/mnt \
  --source-dir /srv/data \
  --persistent \
  --service-name my-mount
```

This writes:

```text
~/.config/blackhole/my-mount.env
```

Then runs:

- `systemctl --user enable blackhole@my-mount.service`
- `systemctl --user start blackhole@my-mount.service`

### Step 3: Remove a registered service

```bash
blackhole unmount my-mount
```

This stops/disables the unit, removes its env file, and daemon-reloads the user
manager.

---

## Safety and behavior guarantees

- Directory mode blocks path traversal outside source/override roots.
- Writes/truncates in blackholed paths return success without persistence.
- Synthetic create/mkdir/unlink/rmdir state exists only in memory for the life
  of the process.
- Mount runs foreground with deterministic options:
  - `foreground=True`
  - `allow_other=False`
  - `nonempty=True` in single-file mode

---

## Logging

Structured logs are emitted with format:

```text
%(asctime)s %(levelname)s %(name)s event=%(message)s
```

Key events include startup mode, service install/register/unmount, mount
start/stop, and discarded writes/truncates.

---

## Contributing

For development setup, test commands, and commit message requirements, see
[`CONTRIBUTING.md`](CONTRIBUTING.md).
