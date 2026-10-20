#!/usr/bin/env python3
"""Record one verified Arcaea publication and mark only its sources handled."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = 2
DEFAULT_STATE = ".arcaea_update_publisher_state.json"
DEFAULT_REGISTRY = "arcaea_update_post_registry.json"


def load_json(path: Path, *, missing_ok: bool = False) -> dict:
    if not path.exists():
        if missing_ok:
            return {}
        raise RuntimeError(f"missing JSON file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return data


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_group(manifest: dict, group_key: str) -> dict:
    matches = [group for group in manifest.get("groups") or [] if str(group.get("key") or "") == group_key]
    if len(matches) != 1:
        raise RuntimeError(f"manifest must contain exactly one group with key {group_key!r}; found {len(matches)}")
    return matches[0]


def first_version(group: dict) -> str:
    for value in group.get("versions") or []:
        version = str(value or "").strip().lower()
        if version:
            return version if version.startswith("v") else f"v{version}"
    return ""


def validate_group(group: dict, args: argparse.Namespace) -> None:
    if group.get("errors"):
        raise RuntimeError(f"refusing to record a group with validation errors: {group['errors']}")
    if not group.get("validation_passed", group.get("draft_ready", False)):
        raise RuntimeError("refusing to record: group validation did not pass")
    if group.get("requires_manual_review") and not args.manual_review_approved:
        raise RuntimeError("refusing to record: group requires --manual-review-approved")
    content_path = Path(str(group.get("content_file") or "")).expanduser()
    if not content_path.is_file():
        raise RuntimeError(f"missing group content file: {content_path}")
    expected_hash = str(group.get("content_sha256") or "")
    if not expected_hash or sha256_file(content_path) != expected_hash:
        raise RuntimeError("refusing to record: content file hash no longer matches manifest")
    for image in group.get("image_records") or []:
        path = Path(str(image.get("file") or "")).expanduser()
        if not path.is_file() or sha256_file(path) != str(image.get("sha256") or ""):
            raise RuntimeError("refusing to record: image hash no longer matches manifest")
    if not args.is_markdown:
        raise RuntimeError("refusing to record: --is-markdown is required")
    if not group.get("source_ids"):
        raise RuntimeError("refusing to record: group has no source IDs")


def record(args: argparse.Namespace) -> dict:
    if not args.verified:
        raise RuntimeError("refusing to record: --verified is required after timeline and detail checks")

    workspace = Path(args.workspace).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()
    registry_path = (workspace / args.registry).resolve()
    state_path = (workspace / args.state_file).resolve()
    manifest = load_json(manifest_path)
    if int(manifest.get("schema_version") or 0) != SCHEMA_VERSION:
        raise RuntimeError("recording requires Arcaea manifest schema_version=2")
    group = select_group(manifest, args.group_key)
    validate_group(group, args)

    version_key = (args.version or first_version(group) or str(group.get("key") or "")).strip().lower()
    if not version_key:
        raise RuntimeError("cannot determine registry key; provide --version")
    verified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source_ids = [str(value) for value in group.get("source_ids") or []]

    registry = load_json(registry_path, missing_ok=True)
    posts = registry.get("posts")
    if not isinstance(posts, dict):
        posts = {}
    existing = posts.get(version_key) if isinstance(posts.get(version_key), dict) else {}
    added_images = int(group.get("image_count") or len(group.get("image_files") or []))
    expected_images = added_images
    if args.operation == "edit":
        target_fields = ("guild_id", "channel_id", "feed_id", "create_time")
        if not existing or any(
            str(existing.get(field) or "") != str(getattr(args, field)) for field in target_fields
        ):
            raise RuntimeError("refusing to record edit: verified target does not match registry")
        if set(source_ids) & set(map(str, existing.get("source_ids") or [])):
            raise RuntimeError("refusing to record edit: sources already recorded; reread before retry")
        expected_images += int(existing.get("image_count") or 0)
    elif existing:
        raise RuntimeError("refusing to replace an existing version record: use edit for an append")
    if args.image_count != expected_images:
        raise RuntimeError(
            f"verified total image count does not match expected post: {args.image_count} != {expected_images}"
        )
    merged_source_ids = list(
        dict.fromkeys([str(value) for value in existing.get("source_ids") or []] + source_ids)
    )
    entry = dict(existing)
    entry.update(
        {
            "version": version_key,
            "title": args.title or group.get("title") or existing.get("title") or "",
            "guild_id": args.guild_id,
            "channel_id": args.channel_id,
            "feed_id": args.feed_id,
            "create_time": args.create_time,
            "share_url": args.share_url,
            "publish_mode": "markdown",
            "is_markdown": True,
            "image_count": args.image_count,
            "content_file": group.get("content_file"),
            "content_sha256": group.get("content_sha256"),
            "source_ids": merged_source_ids,
            "manifest": str(manifest_path),
            "publication_status": "verified",
            "publication_operation": args.operation,
            "publication_verified_at": verified_at,
            "manual_review_approved": bool(args.manual_review_approved),
        }
    )
    has_promotion_history = any(
        key.startswith(("promotion_", "essence_", "top_")) for key in existing
    )
    if "promotion_status" not in entry and not has_promotion_history:
        entry["promotion_status"] = "not_attempted"
    posts[version_key] = entry
    registry["schema_version"] = SCHEMA_VERSION
    registry["posts"] = posts
    atomic_write_json(registry_path, registry)

    state = load_json(state_path, missing_ok=True)
    handled_ids = list(
        dict.fromkeys([str(value) for value in state.get("handled_ids") or []] + source_ids)
    )
    handled_groups = state.get("handled_groups")
    if not isinstance(handled_groups, list):
        handled_groups = []
    handled_groups.append(
        {
            "key": group.get("key"),
            "title": group.get("title"),
            "version": version_key,
            "source_ids": source_ids,
            "operation": args.operation,
            "verified_at": verified_at,
        }
    )
    state.update(
        {
            "schema_version": SCHEMA_VERSION,
            "handled_ids": sorted(handled_ids),
            "handled_groups": handled_groups[-200:],
            "last_marked_at": verified_at,
            "last_verified_manifest": str(manifest_path),
        }
    )
    atomic_write_json(state_path, state)
    return {
        "registry": str(registry_path),
        "state": str(state_path),
        "group_key": group.get("key"),
        "version": version_key,
        "source_count": len(source_ids),
        "image_count": args.image_count,
        "operation": args.operation,
        "verified_at": verified_at,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Record one verified Arcaea Tencent publication")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--group-key", required=True)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--state-file", default=DEFAULT_STATE)
    parser.add_argument("--version")
    parser.add_argument("--operation", choices=("publish", "edit"), default="publish")
    parser.add_argument("--title")
    parser.add_argument("--guild-id", required=True)
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--feed-id", required=True)
    parser.add_argument("--create-time", required=True)
    parser.add_argument("--share-url", required=True)
    parser.add_argument("--image-count", required=True, type=int)
    parser.add_argument("--is-markdown", action="store_true")
    parser.add_argument("--manual-review-approved", action="store_true")
    parser.add_argument("--verified", action="store_true")
    args = parser.parse_args()
    print(json.dumps(record(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
