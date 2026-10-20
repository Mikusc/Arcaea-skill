from __future__ import annotations

import binascii
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
BUILDER = SKILL_ROOT / "scripts" / "build_pack_publish_plan.py"
RECORDER = SKILL_ROOT / "scripts" / "record_pack_publish.py"


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int) -> None:
    row = b"\x00" + (b"\x40\x80\xc0" * width)
    raw = row * height
    payload = b"\x89PNG\r\n\x1a\n"
    payload += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    payload += png_chunk(b"IDAT", zlib.compress(raw, 9))
    payload += png_chunk(b"IEND", b"")
    path.write_bytes(payload)


def run(*args: str, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([sys.executable, *args], text=True, capture_output=True)
    if expect_ok and result.returncode != 0:
        raise AssertionError(f"command failed: {result.stderr}\n{result.stdout}")
    return result


class PackPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.cover = self.workspace / "cover.png"
        self.song = self.workspace / "song.png"
        write_png(self.cover, 640, 360)
        write_png(self.song, 512, 512)
        self.draft = self.workspace / "pack.md"
        self.draft.write_text(
            "> 以下内容涉及测试曲包。\n\n"
            "[(0,0)](@img)\n\n"
            "测试曲包于 `v9.9` 加入。\n\n"
            "## 曲目信息\n\n"
            "| 曲目 | 曲师 | 难度 | 定数 |\n| --- | --- | --- | --- |\n| Test | Artist | `9` | `9.0` |\n\n"
            "## 曲目逐首介绍\n\n### 1. Test\n\n[(0,1)](@img)\n\n**基本信息：** BPM `180`。\n\n"
            "## 购买与基本信息\n\n价格 `500`。\n\n"
            "## 解锁与推进逻辑\n\n购买 -> 游玩。\n",
            encoding="utf-8",
        )
        self.plan = self.workspace / "plan.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build_valid_plan(self) -> dict:
        run(
            str(BUILDER),
            "--title",
            "Test曲包介绍",
            "--guild-id",
            "g",
            "--channel-id",
            "c",
            "--draft",
            str(self.draft),
            "--image",
            str(self.cover),
            "--image-role",
            "official_bilibili_cover",
            "--image",
            str(self.song),
            "--image-role",
            "song",
            "--source",
            "https://www.bilibili.com/video/BVTEST|官方预览",
            "--out",
            str(self.plan),
        )
        return json.loads(self.plan.read_text(encoding="utf-8"))

    def test_valid_plan_and_verified_record(self) -> None:
        plan = self.build_valid_plan()
        self.assertTrue(plan["draft_ready"])
        self.assertEqual(plan["placeholder_indexes"], [0, 1])
        self.assertEqual([(image["width"], image["height"]) for image in plan["images"]], [(640, 360), (512, 512)])

        rejected = run(
            str(RECORDER),
            "--workspace",
            str(self.workspace),
            "--plan",
            str(self.plan),
            "--guild-id",
            "g",
            "--channel-id",
            "c",
            "--feed-id",
            "f",
            "--create-time",
            "1",
            "--share-url",
            "https://pd.qq.com/s/test",
            "--image-count",
            "2",
            "--is-markdown",
            expect_ok=False,
        )
        self.assertNotEqual(rejected.returncode, 0)

        run(
            str(RECORDER),
            "--workspace",
            str(self.workspace),
            "--plan",
            str(self.plan),
            "--guild-id",
            "g",
            "--channel-id",
            "c",
            "--feed-id",
            "f",
            "--create-time",
            "1",
            "--share-url",
            "https://pd.qq.com/s/test",
            "--image-count",
            "2",
            "--is-markdown",
            "--verified",
        )
        registry = json.loads((self.workspace / "pack_intro_post_registry.json").read_text(encoding="utf-8"))
        entry = registry["posts"]["Test曲包介绍"]
        self.assertEqual(entry["publication_status"], "verified")
        self.assertEqual(entry["promotion_status"], "not_attempted")

    def test_target_must_be_supplied(self) -> None:
        result = run(str(BUILDER), "--title", "Test", "--draft", str(self.draft), expect_ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--guild-id", result.stderr)
        self.assertFalse(self.plan.exists())

    def test_record_rejects_wrong_target(self) -> None:
        self.build_valid_plan()
        result = run(
            str(RECORDER), "--workspace", str(self.workspace), "--plan", str(self.plan),
            "--guild-id", "another-guild", "--channel-id", "c", "--feed-id", "f",
            "--create-time", "1", "--share-url", "https://pd.qq.com/s/test",
            "--image-count", "2", "--is-markdown", "--verified", expect_ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target", result.stderr)
        self.assertFalse((self.workspace / "pack_intro_post_registry.json").exists())

    def test_placeholder_mismatch_is_blocking(self) -> None:
        self.draft.write_text(self.draft.read_text(encoding="utf-8").replace("[(0,1)](@img)", "[(0,3)](@img)"), encoding="utf-8")
        plan = self.build_valid_plan()
        self.assertFalse(plan["validation_passed"])
        self.assertFalse(plan["draft_ready"])
        self.assertTrue(any("placeholders" in error for error in plan["errors"]))

    def test_record_edit_requires_existing_post_identity(self) -> None:
        self.build_valid_plan()
        registry_path = self.workspace / "pack_intro_post_registry.json"
        existing = {
            "guild_id": "g", "channel_id": "c", "feed_id": "original",
            "create_time": "1", "promotion_status": "promoted",
        }
        registry_text = json.dumps({"posts": {"Test曲包介绍": existing}})
        record_args = [
            str(RECORDER), "--workspace", str(self.workspace), "--plan", str(self.plan),
            "--operation", "edit", "--guild-id", "g", "--channel-id", "c",
            "--feed-id", "original", "--create-time", "1",
            "--share-url", "https://pd.qq.com/s/test", "--image-count", "2",
            "--is-markdown", "--verified",
        ]
        missing = run(*record_args, expect_ok=False)
        self.assertNotEqual(missing.returncode, 0)
        self.assertFalse(registry_path.exists())
        for field, value in (("feed_id", "different"), ("create_time", "2"),
                             ("guild_id", "other-guild"), ("channel_id", "other-board")):
            with self.subTest(field=field):
                mismatched = dict(existing, **{field: value})
                before = json.dumps({"posts": {"Test曲包介绍": mismatched}})
                registry_path.write_text(before)
                result = run(*record_args, expect_ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("target does not match registry", result.stderr)
                self.assertEqual(registry_path.read_text(), before)

        registry_path.write_text(registry_text)
        run(*record_args)
        recorded = json.loads(registry_path.read_text())["posts"]["Test曲包介绍"]
        self.assertEqual(recorded["feed_id"], "original")
        self.assertEqual(recorded["create_time"], "1")
        self.assertEqual(recorded["promotion_status"], "promoted")
        self.assertEqual(recorded["publication_operation"], "edit")

    def test_publish_cannot_overwrite_existing_pack_record(self) -> None:
        self.build_valid_plan()
        registry_path = self.workspace / "pack_intro_post_registry.json"
        before = json.dumps({"posts": {"Test曲包介绍": {
            "guild_id": "g", "channel_id": "c", "feed_id": "original",
            "create_time": "1", "promotion_status": "promoted",
        }}})
        registry_path.write_text(before)
        result = run(
            str(RECORDER), "--workspace", str(self.workspace), "--plan", str(self.plan),
            "--operation", "publish", "--guild-id", "g", "--channel-id", "c",
            "--feed-id", "new-post", "--create-time", "2",
            "--share-url", "https://pd.qq.com/s/test", "--image-count", "2",
            "--is-markdown", "--verified", expect_ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("existing pack record", result.stderr)
        self.assertEqual(registry_path.read_text(), before)

    def test_record_rejects_changed_draft_hash(self) -> None:
        self.build_valid_plan()
        self.draft.write_text(self.draft.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
        result = run(
            str(RECORDER),
            "--workspace",
            str(self.workspace),
            "--plan",
            str(self.plan),
            "--guild-id",
            "g",
            "--channel-id",
            "c",
            "--feed-id",
            "f",
            "--create-time",
            "1",
            "--share-url",
            "https://pd.qq.com/s/test",
            "--image-count",
            "2",
            "--is-markdown",
            "--verified",
            expect_ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hash", result.stderr)


if __name__ == "__main__":
    unittest.main()
