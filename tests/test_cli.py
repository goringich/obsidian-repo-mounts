from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from obsidian_repo_mounts.cli import build_fstab_lines, parse_manifest, verify_manifest


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


if __name__ == "__main__":
    unittest.main()
