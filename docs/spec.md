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
- a target with `kind=obsidian` is a view of the canonical source and must not also be tracked by the enclosing Obsidian-vault Git repository
- an explicit `kind=repo` target may be tracked by its own repository when a docs-only mirror is intentionally required

The last two rules keep filesystem sharing separate from Git ownership. A bind-mounted Obsidian target and its source are the same files. Tracking that target in the vault repository creates two Git owners for one inode tree, which causes false dirty states, duplicate history, checkout hazards, and secret/privacy gate conflicts.

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

### `repos`

Show git coverage for each source and target path:

- nearest enclosing git repository
- current branch
- origin remote if present
- number of tracked files under the path
- ownership warnings for tracked `kind=obsidian` targets

### `ownership`

Validate Git ownership independently from mount health.

Exit non-zero when a `kind=obsidian` target contains files tracked by the enclosing vault repository. The remediation is to remove that subtree from the vault index with `git rm -r --cached`, add the mount path to the vault `.gitignore`, and keep the canonical source files in the project repository. Never use a normal `git rm` on a live bind mount.

### `manifest-example`

Print a starter manifest for quick editing.

## Non-goals for MVP

- writing to `/etc/fstab`
- automatic mount execution
- GUI
- remote protocols
- conflict resolution for content
