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

## Scope

Current MVP:

- JSON manifest describing one canonical source and one or more bind targets
- `plan` command to render the topology
- `verify` command to validate paths and inode identity
- `fstab` command to generate persistent bind-mount entries
- `repos` command to show git coverage and remote presence for source/targets
- `manifest-example` command to bootstrap a config

Planned next:

- `systemd` unit generation
- safe install/update flow for `/etc/fstab.d/`
- repo health checks and source-of-truth warnings
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
obsidian-repo-mounts fstab mounts.json
obsidian-repo-mounts repos mounts.json
```

A generic example is included in [examples/project-docs.json](/home/goringich/obsidian-repo-mounts/examples/project-docs.json).

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
- `source`: canonical absolute path to the docs directory you consider the source of truth.
- `targets`: required non-empty array of places where that same directory should appear.
- `targets[].path`: absolute target path for the bind mount.
- `targets[].kind`: optional reporting label such as `obsidian` or `repo`.

You can also print the built-in explanation directly:

```bash
obsidian-repo-mounts explain
```

## Market check

Research and positioning live in [docs/research.md](/home/goringich/obsidian-repo-mounts/docs/research.md).

Short version:

- Folder Bridge is the strongest existing solution if the goal is "external folders inside Obsidian without copies".
- Symlink Creator exists, but symlinks are a different operational model and come with caveats.
- There does not appear to be an established repo-first tool focused on bind-mounted documentation across project repo, vault, and docs-only repo.

That gap is what this project targets.

## Safety model

- This project never edits content files.
- It only reads a manifest and emits topology information.
- `fstab` output is generated text, not an automatic privileged write.
- Persistent mount installation should remain explicit and reviewable.

## Development

```bash
python -m unittest discover -s tests -v
python -m obsidian_repo_mounts.cli manifest-example
```

## License

MIT
