#!/usr/bin/env python3
"""Build safe same-version append/new-post plans from an Arcaea v2 manifest.

The script performs no Tencent Channel operation. It preserves the prepared
article's text/image interleaving, offsets placeholders for append actions, and
marks ambiguous date matches for manual review instead of choosing silently.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = 2
MAX_IMAGES = 50
DEFAULT_REGISTRY = "arcaea_update_post_registry.json"
DEFAULT_OUT_DIR = "arcaea_update_append_plans"
REQUIRED_TARGET_FIELDS = ("guild_id", "channel_id", "feed_id", "create_time", "image_count")
DATE_FIELDS = ("date_markers", "related_dates", "release_dates", "event_dates", "update_dates")


def load_json(path: Path, *, missing_ok: bool = False) -> dict:
    if not path.exists():
        if missing_ok:
            return {}
        raise RuntimeError(f"missing JSON file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(text)).strip("-")
    return value[:80] or "draft"


def first_version(group: dict) -> str:
    for value in group.get("versions") or []:
        version = str(value or "").strip().lower()
        if version:
            return version if version.startswith("v") else f"v{version}"
    key = str(group.get("key") or "")
    match = re.search(r"v\d+(?:\.\d+){1,2}", key, flags=re.IGNORECASE)
    return match.group(0).lower() if match else ""


def date_keys_from_text(text: str) -> set[str]:
    keys: set[str] = set()
    for year, month, day in re.findall(r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日", text):
        keys.add(f"{int(month):02d}-{int(day):02d}")
        if year:
            keys.add(f"{int(year):04d}-{int(month):02d}-{int(day):02d}")
    for year, month, day in re.findall(r"(?:(20\d{2})[-/])?(\d{1,2})[-/](\d{1,2})", text):
        keys.add(f"{int(month):02d}-{int(day):02d}")
        if year:
            keys.add(f"{int(year):04d}-{int(month):02d}-{int(day):02d}")
    return keys


def group_date_keys(group: dict) -> set[str]:
    values = [str(group.get("title") or ""), str(group.get("key") or "")]
    values.extend(str(value or "") for value in group.get("matched") or [])
    content_path = Path(str(group.get("content_file") or "")).expanduser()
    if content_path.is_file():
        values.append(content_path.read_text(encoding="utf-8", errors="ignore"))
    keys: set[str] = set()
    for value in values:
        keys.update(date_keys_from_text(value))
    return keys


def target_date_keys(target: dict) -> set[str]:
    values = [str(target.get("title") or "")]
    for field in DATE_FIELDS:
        value = target.get(field)
        if isinstance(value, list):
            values.extend(str(item or "") for item in value)
        elif value:
            values.append(str(value))
    keys: set[str] = set()
    for value in values:
        keys.update(date_keys_from_text(value))
    return keys


def date_keys_overlap(left: set[str], right: set[str]) -> set[str]:
    overlap = left & right
    if overlap:
        return overlap
    left_md = {value[-5:] for value in left if re.search(r"\d{2}-\d{2}$", value)}
    right_md = {value[-5:] for value in right if re.search(r"\d{2}-\d{2}$", value)}
    return left_md & right_md


def registry_posts(registry: dict) -> dict[str, dict]:
    posts = registry.get("posts") or {}
    if isinstance(posts, list):
        return {
            str(post.get("version") or "").lower(): post
            for post in posts
            if isinstance(post, dict) and post.get("version")
        }
    if not isinstance(posts, dict):
        return {}
    return {str(key).lower(): value for key, value in posts.items() if isinstance(value, dict)}


def date_match_candidates(group: dict, posts: dict[str, dict]) -> list[dict]:
    group_dates = group_date_keys(group)
    candidates: list[dict] = []
    if not group_dates:
        return candidates
    for key, target in posts.items():
        overlap = date_keys_overlap(group_dates, target_date_keys(target))
        if overlap:
            candidates.append({"key": key, "target": target, "overlap": sorted(overlap)})
    return sorted(candidates, key=lambda item: item["key"])


def offset_placeholders(markdown: str, offset: int) -> str:
    return re.sub(
        r"\[\(0,(\d+)\)\]\(@img\)",
        lambda match: f"[(0,{offset + int(match.group(1))})](@img)",
        markdown,
    )


def build_append_block(group: dict, image_offset: int, include_heading: bool = True) -> str:
    content_path = Path(str(group.get("content_file") or "")).expanduser()
    if not content_path.is_file():
        raise RuntimeError(f"missing group Markdown: {content_path}")
    body = content_path.read_text(encoding="utf-8").strip()
    body = offset_placeholders(body, image_offset)
    lines = ["", "---", ""]
    if include_heading:
        lines.extend([f"## 追加：{str(group.get('title') or '更新情报').strip()}", ""])
    lines.append(body)
    return "\n".join(lines).rstrip() + "\n"


def validate_group(group: dict) -> list[str]:
    errors = [str(error) for error in group.get("errors") or []]
    if not group.get("validation_passed", group.get("draft_ready", False)):
        errors.append("group validation did not pass")
    content_path = Path(str(group.get("content_file") or "")).expanduser()
    if not content_path.is_file():
        errors.append(f"missing content file: {content_path}")
    elif group.get("content_sha256") and sha256_file(content_path) != group["content_sha256"]:
        errors.append("content file hash no longer matches manifest")
    image_files = [Path(str(path)).expanduser() for path in group.get("image_files") or []]
    if int(group.get("image_count") or len(image_files)) != len(image_files):
        errors.append("manifest image_count does not match image_files")
    for path in image_files:
        if not path.is_file():
            errors.append(f"missing image file: {path}")
    return list(dict.fromkeys(errors))


def target_identity(target: dict) -> str:
    """Return a stable per-post key for cumulative placeholder planning."""
    fields = ("guild_id", "channel_id", "feed_id", "create_time")
    return "|".join(str(target.get(field) or "") for field in fields)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build safe same-version Arcaea update plans")
    parser.add_argument("--workspace", default=".", help="ArcaeaChannel workspace")
    parser.add_argument("--manifest", required=True, help="Manifest from prepare_arcaea_update_drafts.py")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Registry relative to workspace")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Output directory relative to workspace")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()
    registry_path = (workspace / args.registry).resolve()
    out_dir = (workspace / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_json(manifest_path)
    if int(manifest.get("schema_version") or 0) != SCHEMA_VERSION:
        raise RuntimeError("append planner requires Arcaea manifest schema_version=2")
    posts = registry_posts(load_json(registry_path, missing_ok=True))
    plan = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "manifest": str(manifest_path),
        "registry": str(registry_path),
        "actions": [],
        "draft_ready": False,
        "requires_manual_review": False,
        "errors": [],
        "warnings": [],
    }
    target_sequences: dict[str, dict] = {}
    new_version_groups: dict[str, str] = {}

    for group in manifest.get("groups") or []:
        group_key = str(group.get("key") or "")
        version = first_version(group)
        errors = validate_group(group)
        warnings = [str(value) for value in group.get("warnings") or []]
        requires_manual_review = bool(group.get("requires_manual_review"))
        target = posts.get(version) if version else None
        match_reason = "version" if target else ""
        candidate_keys: list[str] = []
        if not target:
            candidates = date_match_candidates(group, posts)
            candidate_keys = [candidate["key"] for candidate in candidates]
            if len(candidates) == 1:
                target = candidates[0]["target"]
                match_reason = f"date_overlap:{','.join(candidates[0]['overlap'])}"
                requires_manual_review = True
                warnings.append("target matched by date instead of explicit version")
            elif len(candidates) > 1:
                requires_manual_review = True
                warnings.append("multiple registry posts match the source dates")

        action = {
            "group_key": group_key,
            "title": group.get("title"),
            "version": version,
            "match_reason": match_reason,
            "target_candidates": candidate_keys,
            "source_ids": group.get("source_ids") or [],
            "source_links": group.get("source_links") or [],
            "content_file": group.get("content_file"),
            "content_sha256": group.get("content_sha256"),
            "image_count": int(group.get("image_count") or 0),
            "image_files": group.get("image_files") or [],
            "requires_manual_review": requires_manual_review,
            "errors": errors,
            "warnings": list(dict.fromkeys(warnings)),
        }
        if target:
            missing_fields = [field for field in REQUIRED_TARGET_FIELDS if target.get(field) in (None, "")]
            if missing_fields:
                errors.append(f"registry target is missing fields: {', '.join(missing_fields)}")
            append_path = out_dir / f"{safe_name(group_key or version)}.append.md"
            if not errors:
                identity = target_identity(target)
                sequence = target_sequences.setdefault(
                    identity,
                    {
                        "next_image_offset": int(target.get("image_count") or 0),
                        "group_keys": [],
                        "has_manual_review": False,
                    },
                )
                dependencies = list(sequence["group_keys"])
                image_offset = int(sequence["next_image_offset"])
                if sequence["has_manual_review"]:
                    requires_manual_review = True
                    action["warnings"].append(
                        "a preceding action for this post requires manual review"
                    )
                action["placeholder_offset"] = image_offset
                action["depends_on_group_keys"] = dependencies
                action["expected_image_count_after"] = image_offset + action["image_count"]
                if action["expected_image_count_after"] > MAX_IMAGES:
                    errors.append(
                        f"append would exceed Tencent long-post image limit: "
                        f"{action['expected_image_count_after']} > {MAX_IMAGES}"
                    )
                else:
                    append_path.write_text(
                        build_append_block(
                            group,
                            image_offset,
                            include_heading=match_reason == "version",
                        ),
                        encoding="utf-8",
                    )
                    action["append_markdown_file"] = str(append_path)
                sequence["next_image_offset"] = action["expected_image_count_after"]
                sequence["group_keys"].append(group_key)
                sequence["has_manual_review"] = bool(
                    sequence["has_manual_review"] or requires_manual_review
                )
            action["action"] = "append_existing"
            action["target"] = target
        elif len(candidate_keys) > 1:
            action["action"] = "manual_review"
        elif version and version in new_version_groups:
            action["action"] = "replan_after_publish"
            action["depends_on_group_keys"] = [new_version_groups[version]]
            errors.append(
                f"version {version} already has a new-post action; publish and record "
                f"group {new_version_groups[version]}, then rebuild the plan"
            )
        else:
            action["action"] = "new_post"
            if version:
                new_version_groups[version] = group_key

        action["requires_manual_review"] = requires_manual_review
        action["warnings"] = list(dict.fromkeys(action["warnings"]))
        action["eligible_for_publish"] = not errors and not requires_manual_review
        plan["actions"].append(action)
        plan["errors"].extend(f"group {group_key}: {error}" for error in errors)
        plan["warnings"].extend(f"group {group_key}: {warning}" for warning in action["warnings"])

    plan["requires_manual_review"] = any(
        action.get("requires_manual_review") for action in plan["actions"]
    )
    plan["draft_ready"] = bool(plan["actions"]) and not plan["errors"] and all(
        action.get("eligible_for_publish") for action in plan["actions"]
    )
    plan_path = out_dir / "append_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "plan": str(plan_path),
                "action_count": len(plan["actions"]),
                "draft_ready": plan["draft_ready"],
                "requires_manual_review": plan["requires_manual_review"],
                "error_count": len(plan["errors"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
