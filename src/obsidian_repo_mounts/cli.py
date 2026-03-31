from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    path: Path
    kind: str


@dataclass(frozen=True)
class Mount:
    name: str
    source: Path
    targets: tuple[Target, ...]


@dataclass(frozen=True)
class Manifest:
    vault_root: Path | None
    mounts: tuple[Mount, ...]


EXAMPLE_MANIFEST = {
    "vault_root": "/vault",
    "mounts": [
        {
            "name": "project-docs",
            "source": "/projects/acme-app/docs",
            "targets": [
                {
                    "path": "/vault/Projects/Acme App/docs",
                    "kind": "obsidian",
                },
                {
                    "path": "/repos/acme-app-docs/docs",
                    "kind": "repo",
                },
            ],
        }
    ],
}


MANIFEST_HELP = """Manifest fields:

Top level:
  vault_root
    Optional absolute path to the Obsidian vault root.
    Used only for validation/context. It does not change mount behavior by itself.

  mounts
    Required non-empty array of mount definitions.
    Each entry describes one canonical source directory and its bind targets.

Per mount:
  name
    Stable logical identifier for this shared docs topology.
    Used only for reporting and readable output.

  source
    Required absolute path to the canonical docs directory.
    This is the source-of-truth path that should be mounted elsewhere.

  targets
    Required non-empty array of target objects.
    Every target receives the same source directory via a bind mount.

Per target:
  path
    Required absolute path where the source directory should appear.
    Example: a folder inside the Obsidian vault or inside a docs-only repo.

  kind
    Optional label for reporting.
    Recommended values: obsidian, repo, mirror, archive.
    It does not affect mounting logic; it only improves diagnostics.

Command meanings:
  manifest-example
    Print a starter JSON manifest.

  explain
    Print this manifest and command reference.

  plan <manifest>
    Show the declared source -> targets topology.

  verify <manifest>
    Check that paths exist, are directories, and currently resolve to the same inode.

  fstab <manifest>
    Print bind-mount lines suitable for review before adding to /etc/fstab or /etc/fstab.d/.

  repos <manifest>
    Show which git repository contains each source/target path, plus branch and origin.

  add --manifest ... --name ... --source ... --target ... [--target ...]
    Append a new mount definition into a manifest file.
    Each --target uses PATH:KIND format, for example:
      --target /vault/Projects/Acme/docs:obsidian
      --target /repos/acme-docs/docs:repo

  install <manifest> [--output ...]
    Write a local fstab fragment file generated from the manifest.
    This does not touch /etc. It is meant for review and later privileged installation.
"""


def _require_absolute(path: str, field_name: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ManifestError(f"{field_name} must be an absolute path: {path}")
    return candidate


def load_manifest(path: str | Path) -> Manifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_manifest(raw)


def manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mounts": [
            {
                "name": mount.name,
                "source": str(mount.source),
                "targets": [
                    {"path": str(target.path), "kind": target.kind}
                    for target in mount.targets
                ],
            }
            for mount in manifest.mounts
        ]
    }
    if manifest.vault_root is not None:
        payload["vault_root"] = str(manifest.vault_root)
    return payload


def parse_manifest(raw: dict[str, Any]) -> Manifest:
    mounts_raw = raw.get("mounts")
    if not isinstance(mounts_raw, list) or not mounts_raw:
        raise ManifestError("manifest must contain a non-empty 'mounts' array")

    seen_targets: set[Path] = set()
    mounts: list[Mount] = []

    vault_root_raw = raw.get("vault_root")
    vault_root = (
        _require_absolute(vault_root_raw, "vault_root")
        if isinstance(vault_root_raw, str)
        else None
    )

    for entry in mounts_raw:
        if not isinstance(entry, dict):
            raise ManifestError("each mount must be an object")
        name = entry.get("name")
        source_raw = entry.get("source")
        targets_raw = entry.get("targets")
        if not isinstance(name, str) or not name.strip():
            raise ManifestError("each mount needs a non-empty 'name'")
        if not isinstance(source_raw, str):
            raise ManifestError(f"mount '{name}' needs a string 'source'")
        if not isinstance(targets_raw, list) or not targets_raw:
            raise ManifestError(f"mount '{name}' needs a non-empty 'targets' array")

        source = _require_absolute(source_raw, f"mount '{name}' source")
        targets: list[Target] = []
        for target_raw in targets_raw:
            if not isinstance(target_raw, dict):
                raise ManifestError(f"mount '{name}' target must be an object")
            path_raw = target_raw.get("path")
            kind = target_raw.get("kind", "target")
            if not isinstance(path_raw, str):
                raise ManifestError(f"mount '{name}' target needs a string 'path'")
            if not isinstance(kind, str) or not kind.strip():
                raise ManifestError(f"mount '{name}' target kind must be a non-empty string")
            path = _require_absolute(path_raw, f"mount '{name}' target path")
            if path == source:
                raise ManifestError(f"mount '{name}' target cannot equal source: {path}")
            if path in seen_targets:
                raise ManifestError(f"duplicate target path in manifest: {path}")
            seen_targets.add(path)
            targets.append(Target(path=path, kind=kind))
        mounts.append(Mount(name=name, source=source, targets=tuple(targets)))

    return Manifest(vault_root=vault_root, mounts=tuple(mounts))


def build_fstab_lines(manifest: Manifest) -> list[str]:
    lines: list[str] = []
    for mount in manifest.mounts:
        for target in mount.targets:
            lines.append(f"{mount.source} {target.path} none bind 0 0")
    return lines


def inode_signature(path: Path) -> tuple[int, int]:
    stat_result = path.stat()
    return stat_result.st_dev, stat_result.st_ino


def verify_manifest(manifest: Manifest) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True

    if manifest.vault_root is not None and not manifest.vault_root.exists():
        ok = False
        messages.append(f"vault_root missing: {manifest.vault_root}")

    for mount in manifest.mounts:
        if not mount.source.exists():
            ok = False
            messages.append(f"[{mount.name}] source missing: {mount.source}")
            continue
        if not mount.source.is_dir():
            ok = False
            messages.append(f"[{mount.name}] source is not a directory: {mount.source}")
            continue

        source_sig = inode_signature(mount.source)
        messages.append(f"[{mount.name}] source ok: {mount.source}")
        for target in mount.targets:
            if not target.path.exists():
                ok = False
                messages.append(f"[{mount.name}] target missing: {target.path} ({target.kind})")
                continue
            if not target.path.is_dir():
                ok = False
                messages.append(f"[{mount.name}] target is not a directory: {target.path}")
                continue
            target_sig = inode_signature(target.path)
            if target_sig != source_sig:
                ok = False
                messages.append(
                    f"[{mount.name}] inode mismatch: {target.path} ({target.kind})"
                )
            else:
                messages.append(
                    f"[{mount.name}] inode match: {target.path} ({target.kind})"
                )

    return ok, messages


def find_git_root(path: Path) -> Path | None:
    current = path.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def git_value(repo: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def repo_report_for_path(path: Path) -> list[str]:
    repo = find_git_root(path)
    if repo is None:
        return [f"path: {path}", "  repo: none"]

    branch = git_value(repo, "branch", "--show-current") or "(detached)"
    origin = git_value(repo, "remote", "get-url", "origin") or "(no origin)"
    return [
        f"path: {path}",
        f"  repo: {repo}",
        f"  branch: {branch}",
        f"  origin: {origin}",
    ]


def parse_target_spec(spec: str) -> Target:
    if ":" not in spec:
        raise ManifestError(
            f"target spec must use PATH:KIND format, got: {spec}"
        )
    path_raw, kind = spec.rsplit(":", 1)
    if not path_raw or not kind:
        raise ManifestError(f"invalid target spec: {spec}")
    path = _require_absolute(path_raw, "target path")
    return Target(path=path, kind=kind)


def cmd_manifest_example(_: argparse.Namespace) -> int:
    print(json.dumps(EXAMPLE_MANIFEST, ensure_ascii=False, indent=2))
    return 0


def cmd_explain(_: argparse.Namespace) -> int:
    print(MANIFEST_HELP)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    if manifest.vault_root is not None:
        print(f"vault_root: {manifest.vault_root}")
        print()
    for mount in manifest.mounts:
        print(f"[{mount.name}]")
        print(f"source: {mount.source}")
        for target in mount.targets:
            print(f"target: {target.path} ({target.kind})")
        print()
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    ok, messages = verify_manifest(manifest)
    for message in messages:
        print(message)
    return 0 if ok else 1


def cmd_fstab(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    for line in build_fstab_lines(manifest):
        print(line)
    return 0


def cmd_repos(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    for mount in manifest.mounts:
        print(f"[{mount.name}]")
        for line in repo_report_for_path(mount.source):
            print(line)
        for target in mount.targets:
            print(f"target-kind: {target.kind}")
            for line in repo_report_for_path(target.path):
                print(line)
        print()
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if manifest_path.exists():
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        raw = {"mounts": []}
        if args.vault_root is not None:
            raw["vault_root"] = args.vault_root

    mounts_raw = raw.setdefault("mounts", [])
    if not isinstance(mounts_raw, list):
        raise ManifestError("'mounts' must be an array")

    if any(
        isinstance(entry, dict) and entry.get("name") == args.name for entry in mounts_raw
    ):
        raise ManifestError(f"mount name already exists: {args.name}")

    targets = [parse_target_spec(spec) for spec in args.target]
    new_entry = {
        "name": args.name,
        "source": str(_require_absolute(args.source, "source")),
        "targets": [{"path": str(target.path), "kind": target.kind} for target in targets],
    }
    mounts_raw.append(new_entry)
    manifest = parse_manifest(raw)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest_to_dict(manifest), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"updated manifest: {manifest_path}")
    print(f"added mount: {args.name}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# generated by obsidian-repo-mounts install",
        f"# manifest: {Path(args.manifest).resolve()}",
        *build_fstab_lines(manifest),
        "",
    ]
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obsidian-repo-mounts",
        description="Plan and verify repo-first Obsidian bind-mount topologies.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_example = subparsers.add_parser(
        "manifest-example", help="Print a starter manifest."
    )
    manifest_example.set_defaults(func=cmd_manifest_example)

    explain = subparsers.add_parser(
        "explain", help="Explain manifest fields and command meanings."
    )
    explain.set_defaults(func=cmd_explain)

    for name, help_text, func in (
        ("plan", "Render the manifest topology.", cmd_plan),
        ("verify", "Check path existence and inode identity.", cmd_verify),
        ("fstab", "Generate bind-mount entries for /etc/fstab.", cmd_fstab),
        ("repos", "Show git repo coverage for source and target paths.", cmd_repos),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("manifest", help="Path to manifest JSON.")
        sub.set_defaults(func=func)

    add = subparsers.add_parser("add", help="Append a new mount into a manifest.")
    add.add_argument("--manifest", required=True, help="Path to manifest JSON.")
    add.add_argument("--vault-root", help="Optional vault root for new manifests.")
    add.add_argument("--name", required=True, help="Stable mount name.")
    add.add_argument("--source", required=True, help="Canonical source directory.")
    add.add_argument(
        "--target",
        action="append",
        required=True,
        help="Target spec in PATH:KIND form. Repeat for multiple targets.",
    )
    add.set_defaults(func=cmd_add)

    install = subparsers.add_parser(
        "install", help="Write a local fstab fragment generated from a manifest."
    )
    install.add_argument("manifest", help="Path to manifest JSON.")
    install.add_argument(
        "--output",
        required=True,
        help="Output path for the generated fragment file.",
    )
    install.set_defaults(func=cmd_install)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ManifestError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
