# Spec

## Goal

Define a single declarative manifest for shared documentation trees where one source directory is projected into one or more target directories via bind mounts.

## Manifest shape

Top-level object:

- `vault_root`: optional absolute path to the Obsidian vault
- `mounts`: array of mount definitions

Mount definition:

- `name`: stable identifier
- `source`: canonical absolute path
- `targets`: array of targets

Target definition:

- `path`: absolute path for the bind target
- `kind`: optional label such as `obsidian`, `repo`, or `mirror`

## Invariants

- `source` must be absolute
- every target path must be absolute
- target paths must be unique across the manifest
- source must not equal any target
- inode equality across source and targets indicates a live shared tree

## Commands

### `plan`

Render the mount topology in a human-readable form.

### `verify`

Validate:

- manifest structure
- path existence
- directory type
- inode equality where target paths exist

Exit non-zero if validation fails.

### `fstab`

Generate plain bind-mount lines:

```fstab
/source/path /target/path none bind 0 0
```

This command does not modify the system.

### `manifest-example`

Print a starter manifest for quick editing.

## Non-goals for MVP

- writing to `/etc/fstab`
- automatic mount execution
- GUI
- remote protocols
- conflict resolution for content
