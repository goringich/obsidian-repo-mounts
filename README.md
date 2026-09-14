# obsidian-repo-mounts

Manifest-driven bind-mount orchestration for project documentation that must live in three places at once:

- in the source project repo
- inside an Obsidian vault for indexing and wikilinks
- in an optional docs-only Git repository

The files stay the same files. No copies. No export step. No sync daemon rewriting content.

## Why this exists

There are already good tools for adjacent problems:

- Folder Bridge for Obsidian mounts external folders into a vault without copying or symlinking and already covers many desktop and remote mount scenarios.
- Symlink Creator helps create symlinks and junctions from inside Obsidian.

Those tools are useful, but they do not replace the exact repo-first workflow used on this machine:

- one canonical docs directory inside a project repo
- the same inode tree exposed into Obsidian
- the same inode tree exposed into a second docs-only repo
- mount topology treated as infrastructure and tracked in Git

`obsidian-repo-mounts` is intentionally narrower than a general Obsidian mount plugin. It is a Linux-first operator tool for filesystem-level truth.

## Git ownership rule

A bind mount shares the same files; it does not create a copy. Because of that, a target with `kind=obsidian` must be treated as a read/index view from the vault Git repository's perspective.

- The project `source` remains the canonical Git owner.
- The enclosing Obsidian-vault repository must not track files below a `kind=obsidian` mount point.
- An explicit `kind=repo` target may be tracked when a docs-only repository is intentionally part of the topology.
- Never use a normal `git rm` against a live bind mount to fix ownership. Use `git rm -r --cached` plus a vault `.gitignore` entry so the canonical source files remain untouched.

Use `ownership` to fail closed on duplicate vault ownership and `repos` to inspect tracked-file coverage.

## Scope

Current MVP:

- JSON manifest describing one canonical source and one or more bind targets
- `plan` command to render the topology
- `verify` command to validate paths and inode identity
- `fstab` command to generate persistent bind-mount entries
- `repos` command to show git coverage, tracked-file counts, and ownership warnings
- `ownership` command to reject tracked `kind=obsidian` targets
- `manifest-example` command to bootstrap a config

Planned next:

- `systemd` unit generation
- safe install/update flow for `/etc/fstab.d/`
- optional Obsidian note generation for mounted docs maps

## When to use this

Use this project if you want filesystem-level truth across repos and Obsidian.

Do not use this project if you only need Obsidian to see an external folder. In that case, use Folder Bridge first.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
obsidian-repo-mounts manifest-example > mounts.json
obsidian-repo-mounts plan mounts.json
obsidian-repo-mounts verify mounts.json
obsidian-repo-mounts repos mounts.json
obsidian-repo-mounts ownership mounts.json
obsidian-repo-mounts fstab mounts.json
```

A generic example is included in `examples/project-docs.json`.

## Shell-first workflow

On this machine the main operator entrypoint is the `ormounts` shell command.

Short form:

```bash
ormounts ./path_obsidian_vault/project_docs_mount_point ./project_docs
```

Optional third path for a docs-only repo:

```bash
ormounts ./path_obsidian_vault/project_docs_mount_point ./project_docs ./project_docs_repo/docs
```

What the short form does:

- normalizes relative paths into absolute ones
- appends a new topology into the default manifest
- regenerates the local fstab fragment for later review/install

## Example manifest

```json
{
  "vault_root": "/vault",
  "mounts": [
    {
      "name": "project-docs",
      "source": "/projects/acme-app/docs",
      "targets": [
        {
          "path": "/vault/Projects/Acme App/docs",
          "kind": "obsidian"
        },
        {
          "path": "/repos/acme-app-docs/docs",
          "kind": "repo"
        }
      ]
    }
  ]
}
```

### Field meanings

- `vault_root`: optional absolute path to the Obsidian vault root; used for validation and context.
- `mounts`: required non-empty array of shared-doc mount definitions.
- `name`: human-readable identifier for one mount topology.
- `source`: canonical absolute path to the docs directory.
- `targets`: required non-empty array of places where the source directory should appear.
- `targets[].path`: full target path.
- `targets[].kind`: reporting/ownership role such as `obsidian`, `repo`, `mirror`, or `archive`.

You can also print the built-in explanation directly:

```bash
obsidian-repo-mounts explain
```

## Safety model

- This project never edits content files.
- It only reads a manifest and emits topology/ownership information.
- `fstab` output is generated text, not an automatic privileged write.
- Persistent mount installation remains explicit and reviewable.
- `ownership` is read-only; it reports duplicate Git ownership and exits non-zero.
- Fixing an Obsidian ownership conflict must preserve source files: untrack with `git rm -r --cached`, then ignore the mount path in the vault repository.

## Development

```bash
python -m unittest discover -s tests -v
python -m obsidian_repo_mounts.cli manifest-example
```

## License

MIT
