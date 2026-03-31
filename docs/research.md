# Research

## Local history found

The existing machine already uses the target architecture.

Confirmed locally on 2026-03-31:

- one project-owned `docs/` directory
- one Obsidian-visible mount target inside the vault
- one docs-only repository mount target

The three locations currently resolve to the same inode directory, and `/etc/fstab` already contains persistent bind mounts for the Obsidian path and the docs-only repo path.

That means the core idea is proven locally without needing copies or exporters.

## Existing tools

### Folder Bridge

Source:

- https://github.com/tescolopio/Obsidian_FolderBridge

Why it matters:

- actively developed
- available as an Obsidian community plugin
- explicitly targets external folders inside a vault without copying
- supports local folders plus remote backends

Why it is not the whole answer for this workflow:

- it is Obsidian-centric, not repo-centric
- its mount definitions live in plugin settings / TOC files, not as infrastructure shared across repo workflows
- it does not create a real second working tree for a docs-only Git repo
- it does not manage bind-mount truth outside Obsidian

Conclusion:

- best ready-made answer for "show external folders inside Obsidian"
- not a full answer for "one docs tree across project repo + Obsidian + docs-only repo"

### Symlink Creator

Source:

- https://github.com/pteridin/obsidian_symlink_plugin

Why it matters:

- simple plugin for creating symlinks/junctions from Obsidian
- useful for lighter workflows

Why it is not the preferred basis here:

- symlinks are not the same as bind mounts
- cross-filesystem and platform behavior is less deterministic
- repo-first multi-working-tree topology remains manual

Conclusion:

- useful helper
- not the target model for this machine

### Obsidian forum history

Source:

- https://forum.obsidian.md/t/ability-to-index-add-external-folders-from-across-computer/22574

What it shows:

- long-standing user demand for indexing external folders
- symlinks were discussed as a workaround
- there were historical cautions around crossing filesystem boundaries

Conclusion:

- the problem is real and old
- users still need operationally clean solutions

## Product gap

The open gap is a narrow but real one:

- Linux-first
- Git-aware
- repo-first
- explicit source-of-truth model
- bind mounts as infrastructure, not as hidden plugin state

That is the exact niche for `obsidian-repo-mounts`.

## Product direction

This project should stay deliberately focused:

- do not compete with Folder Bridge on remote protocols and in-app UI
- own the manifest, verification, and persistent bind-mount topology problem
- become the operator layer for teams or solo developers who treat docs as code and want Obsidian as an indexer, not as the source of truth
