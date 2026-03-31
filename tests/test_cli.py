from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from obsidian_repo_mounts.cli import (
    build_fstab_lines,
    cmd_add,
    cmd_install,
    find_git_root,
    parse_manifest,
    verify_manifest,
)


class ManifestTests(unittest.TestCase):
    def test_build_fstab_lines(self) -> None:
        manifest = parse_manifest(
            {
                "mounts": [
                    {
                        "name": "demo",
                        "source": "/src/docs",
                        "targets": [
                            {"path": "/vault/demo/docs", "kind": "obsidian"},
                            {"path": "/repo/demo-docs/docs", "kind": "repo"},
                        ],
                    }
                ]
            }
        )

        self.assertEqual(
            build_fstab_lines(manifest),
            [
                "/src/docs /vault/demo/docs none bind 0 0",
                "/src/docs /repo/demo-docs/docs none bind 0 0",
            ],
        )

    def test_verify_manifest_with_same_inode_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            source.mkdir()
            target = root / "target"
            target.symlink_to(source, target_is_directory=True)

            manifest = parse_manifest(
                {
                    "mounts": [
                        {
                            "name": "demo",
                            "source": str(source),
                            "targets": [{"path": str(target), "kind": "obsidian"}],
                        }
                    ]
                }
            )

            ok, messages = verify_manifest(manifest)
            self.assertTrue(ok)
            self.assertTrue(any("inode match" in message for message in messages))

    def test_find_git_root_returns_none_without_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertIsNone(find_git_root(Path(temp_dir)))

    def test_cmd_add_appends_mount(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "mounts.json"
            args = type(
                "Args",
                (),
                {
                    "manifest": str(manifest_path),
                    "vault_root": "/vault",
                    "name": "project-docs",
                    "source": "/projects/acme/docs",
                    "target": [
                        "/vault/Projects/Acme/docs:obsidian",
                        "/repos/acme-docs/docs:repo",
                    ],
                },
            )()

            result = cmd_add(args)
            self.assertEqual(result, 0)
            manifest = parse_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
            self.assertEqual(manifest.mounts[0].name, "project-docs")
            self.assertEqual(len(manifest.mounts[0].targets), 2)

    def test_cmd_install_writes_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "mounts.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "mounts": [
                            {
                                "name": "demo",
                                "source": "/src/docs",
                                "targets": [
                                    {"path": "/vault/demo/docs", "kind": "obsidian"}
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            output_path = Path(temp_dir) / "generated" / "demo.fstab"
            args = type(
                "Args",
                (),
                {"manifest": str(manifest_path), "output": str(output_path)},
            )()

            result = cmd_install(args)
            self.assertEqual(result, 0)
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("/src/docs /vault/demo/docs none bind 0 0", content)


if __name__ == "__main__":
    unittest.main()
