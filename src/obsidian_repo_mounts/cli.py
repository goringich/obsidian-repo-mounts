from __future__ import annotations

import argparse
import json
import os
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


def _require_absolute(path: str, field_name: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ManifestError(f"{field_name} must be an absolute path: {path}")
    return candidate


def load_manifest(path: str | Path) -> Manifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_manifest(raw)


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


def cmd_manifest_example(_: argparse.Namespace) -> int:
    print(json.dumps(EXAMPLE_MANIFEST, ensure_ascii=False, indent=2))
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

    for name, help_text, func in (
        ("plan", "Render the manifest topology.", cmd_plan),
        ("verify", "Check path existence and inode identity.", cmd_verify),
        ("fstab", "Generate bind-mount entries for /etc/fstab.", cmd_fstab),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("manifest", help="Path to manifest JSON.")
        sub.set_defaults(func=func)

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
