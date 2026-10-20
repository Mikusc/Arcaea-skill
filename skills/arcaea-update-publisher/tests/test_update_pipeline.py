from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
PREPARE = SKILL_ROOT / "scripts" / "prepare_arcaea_update_drafts.py"
PLANNER = SKILL_ROOT / "scripts" / "plan_version_append.py"
RECORDER = SKILL_ROOT / "scripts" / "record_arcaea_publish.py"


def run(*args: str, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([sys.executable, *args], text=True, capture_output=True)
    if expect_ok and result.returncode != 0:
        raise AssertionError(f"command failed: {result.stderr}\n{result.stdout}")
    return result


class UpdatePipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        first = self.workspace / "first.jpg"
        second = self.workspace / "second.jpg"
        first.write_bytes(b"first-image")
        second.write_bytes(b"second-image")
        pages = [
            {
                "data": {
                    "items": [
                        {
                            "id_str": "1001",
                            "type": "DYNAMIC_TYPE_DRAW",
                            "modules": {
                                "module_author": {
                                    "mid": 404145357,
                                    "name": "Arcaea",
                                    "pub_ts": 1787000000,
                                    "pub_time": "2026-08-18",
                                },
                                "module_dynamic": {
                                    "desc": {"text": "Arcaea v6.99 将于2026年8月20日新增新曲「Test Song」"},
                                    "major": {"draw": {"items": [{"src": first.as_uri()}]}},
                                },
                            },
                        },
                        {
                            "id_str": "1002",
                            "type": "DYNAMIC_TYPE_DRAW",
                            "modules": {
                                "module_author": {
                                    "mid": 404145357,
                                    "name": "Arcaea",
                                    "pub_ts": 1787000300,
                                    "pub_time": "2026-08-18",
                                },
                                "module_dynamic": {
                                    "desc": {"text": "「Test Song」预览公开，更新后即可游玩。"},
                                    "major": {"draw": {"items": [{"src": second.as_uri()}]}},
                                },
                            },
                        },
                        {
                            "id_str": "9999",
                            "type": "DYNAMIC_TYPE_WORD",
                            "modules": {
                                "module_author": {"mid": 1, "pub_ts": 1787000400},
                                "module_dynamic": {"desc": {"text": "v6.99 更新"}},
                            },
                        },
                    ]
                }
            }
        ]
        self.raw = self.workspace / "raw.json"
        self.raw.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_prepare_plan_and_verified_record(self) -> None:
        run(
            str(PREPARE),
            "--workspace",
            str(self.workspace),
            "--raw-file",
            str(self.raw),
            "--out-dir",
            "drafts",
        )
        manifest_path = self.workspace / "drafts" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["group_count"], 1)
        self.assertTrue(manifest["draft_ready"])
        self.assertEqual(len(manifest["skipped_author_mismatch"]), 1)
        group = manifest["groups"][0]
        self.assertEqual(group["placeholder_indexes"], [0, 1])
        article = Path(group["content_file"]).read_text(encoding="utf-8")
        self.assertLess(article.index("[(0,0)](@img)"), article.index("原动态 1"))
        self.assertLess(article.index("[(0,1)](@img)"), article.index("原动态 2"))

        registry = {
            "posts": {
                "v6.99": {
                    "guild_id": "g",
                    "channel_id": "c",
                    "feed_id": "old",
                    "create_time": "1",
                    "image_count": 3,
                    "title": "Arcaea v6.99 更新情报",
                    "essence_status": "enabled",
                }
            }
        }
        registry_path = self.workspace / "registry.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        second_group = dict(group)
        second_group["key"] = "v6.99-second-topic"
        second_group["title"] = "Arcaea v6.99 第二组更新情报"
        manifest["groups"].append(second_group)
        manifest["group_count"] = 2
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        run(
            str(PLANNER),
            "--workspace",
            str(self.workspace),
            "--manifest",
            str(manifest_path),
            "--registry",
            "registry.json",
            "--out-dir",
            "plans",
        )
        plan = json.loads((self.workspace / "plans" / "append_plan.json").read_text(encoding="utf-8"))
        self.assertTrue(plan["draft_ready"])
        action = plan["actions"][0]
        self.assertEqual(action["action"], "append_existing")
        self.assertEqual(action["placeholder_offset"], 3)
        self.assertEqual(action["depends_on_group_keys"], [])
        append_text = Path(action["append_markdown_file"]).read_text(encoding="utf-8")
        self.assertIn("[(0,3)](@img)", append_text)
        self.assertIn("[(0,4)](@img)", append_text)
        second_action = plan["actions"][1]
        self.assertEqual(second_action["placeholder_offset"], 5)
        self.assertEqual(second_action["depends_on_group_keys"], [group["key"]])
        second_append_text = Path(second_action["append_markdown_file"]).read_text(encoding="utf-8")
        self.assertIn("[(0,5)](@img)", second_append_text)
        self.assertIn("[(0,6)](@img)", second_append_text)

        record_args = [
            str(RECORDER), "--workspace", str(self.workspace), "--manifest", str(manifest_path),
            "--group-key", group["key"], "--registry", "registry.json", "--state-file", "state.json",
            "--operation", "edit", "--guild-id", "g", "--channel-id", "c", "--feed-id", "old",
            "--create-time", "1", "--share-url", "https://pd.qq.com/s/test", "--is-markdown",
        ]
        rejected = run(*record_args, "--image-count", "5", expect_ok=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse((self.workspace / "state.json").exists())

        # Adding two pictures to a three-picture post must record five, not two.
        wrong_count = run(*record_args, "--image-count", "2", "--verified", expect_ok=False)
        self.assertNotEqual(wrong_count.returncode, 0)
        self.assertIn("total image count", wrong_count.stderr)
        self.assertEqual(json.loads(registry_path.read_text())["posts"]["v6.99"]["image_count"], 3)

        wrong_target = ["another-feed" if value == "old" else value for value in record_args]
        rejected_target = run(*wrong_target, "--image-count", "5", "--verified", expect_ok=False)
        self.assertNotEqual(rejected_target.returncode, 0)
        self.assertIn("target", rejected_target.stderr)

        image_path = Path(group["image_records"][0]["file"])
        original = image_path.read_bytes()
        image_path.write_bytes(b"changed-image")
        changed = run(*record_args, "--image-count", "5", "--verified", expect_ok=False)
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn("image hash", changed.stderr)
        image_path.write_bytes(original)

        run(*record_args, "--image-count", "5", "--verified")
        duplicate = run(*record_args, "--image-count", "7", "--verified", expect_ok=False)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("already recorded", duplicate.stderr)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["handled_ids"], ["1001", "1002"])
        recorded = json.loads(registry_path.read_text(encoding="utf-8"))["posts"]["v6.99"]
        self.assertEqual(recorded["publication_status"], "verified")
        self.assertEqual(recorded["image_count"], 5)
        self.assertEqual(recorded["feed_id"], "old")
        self.assertEqual(recorded["essence_status"], "enabled")
        self.assertNotIn("promotion_status", recorded)

        # A new publication starts at this group's count in an empty registry.
        new_args = [
            "publish" if value == "edit" else "new-registry.json" if value == "registry.json"
            else "new-state.json" if value == "state.json" else value
            for value in record_args
        ]
        run(*new_args, "--image-count", "2", "--verified")
        new_record = json.loads((self.workspace / "new-registry.json").read_text())["posts"]["v6.99"]
        self.assertEqual(new_record["image_count"], 2)

    def test_legacy_mark_handled_fails_closed(self) -> None:
        result = run(
            str(PREPARE),
            "--workspace",
            str(self.workspace),
            "--mark-handled",
            str(self.raw),
            expect_ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("disabled", result.stderr)


if __name__ == "__main__":
    unittest.main()
