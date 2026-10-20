#!/usr/bin/env python3
"""Record a verified, hash-matching Arcaea pack-intro publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = 2
DEFAULT_REGISTRY = "pack_intro_post_registry.json"


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


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def verify_plan(plan: dict, args: argparse.Namespace) -> None:
    if int(plan.get("schema_version") or 0) != SCHEMA_VERSION:
        raise RuntimeError("recording requires pack publish plan schema_version=2")
    if plan.get("errors") or not plan.get("validation_passed"):
        raise RuntimeError(f"refusing to record a plan with validation errors: {plan.get('errors')}")
    if plan.get("requires_manual_review") and not args.manual_review_approved:
        raise RuntimeError("refusing to record: plan requires --manual-review-approved")
    target = plan.get("target") or {}
    if not target.get("guild_id") or not target.get("channel_id"):
        raise RuntimeError("refusing to record: publish plan has no target IDs")
    if (args.guild_id, args.channel_id) != (target["guild_id"], target["channel_id"]):
        raise RuntimeError("refusing to record: verified target does not match publish plan")
    if not args.is_markdown:
        raise RuntimeError("refusing to record: --is-markdown is required")
    if args.image_count != int(plan.get("image_count") or 0):
        raise RuntimeError(
            f"verified image count does not match plan: {args.image_count} != {plan.get('image_count')}"
        )
    draft = Path(str(plan.get("draft") or "")).expanduser()
    if not draft.is_file() or sha256_file(draft) != str(plan.get("draft_sha256") or ""):
        raise RuntimeError("refusing to record: draft hash no longer matches publish plan")
    for image in plan.get("images") or []:
        path = Path(str(image.get("file") or "")).expanduser()
        if not path.is_file() or sha256_file(path) != str(image.get("sha256") or ""):
            raise RuntimeError(f"refusing to record: image hash no longer matches publish plan: {path}")


def record(args: argparse.Namespace) -> dict:
    if not args.verified:
        raise RuntimeError("refusing to record: --verified is required after timeline and detail checks")
    workspace = Path(args.workspace).expanduser().resolve()
    plan_path = Path(args.plan).expanduser().resolve()
    registry_path = (workspace / args.registry).resolve()
    plan = load_json(plan_path)
    verify_plan(plan, args)

    title = str(plan.get("title") or "").strip()
    key = (args.registry_key or title).strip()
    if not key:
        raise RuntimeError("cannot determine registry key")
    verified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    registry = load_json(registry_path, missing_ok=True)
    posts = registry.get("posts")
    if not isinstance(posts, dict):
        posts = {}
    existing = posts.get(key) if isinstance(posts.get(key), dict) else {}
    if args.operation == "edit":
        target_fields = ("guild_id", "channel_id", "feed_id", "create_time")
        if not existing or any(
            str(existing.get(field) or "") != str(getattr(args, field)) for field in target_fields
        ):
            raise RuntimeError("refusing to record edit: verified target does not match registry")
    elif existing:
        raise RuntimeError("refusing to replace an existing pack record: use edit for the same post")
    entry = dict(existing)
    entry.update(
        {
            "title": title,
            "guild_id": args.guild_id,
            "channel_id": args.channel_id,
            "feed_id": args.feed_id,
            "create_time": args.create_time,
            "share_url": args.share_url,
            "publish_mode": "markdown",
            "is_markdown": True,
            "image_count": args.image_count,
            "image_roles": [image.get("role") for image in plan.get("images") or []],
            "source_links": [source.get("url") for source in plan.get("sources") or []],
            "draft": plan.get("draft"),
            "draft_sha256": plan.get("draft_sha256"),
            "publish_plan": str(plan_path),
            "publish_plan_sha256": sha256_file(plan_path),
            "publication_status": "verified",
            "publication_operation": args.operation,
            "publication_verified_at": verified_at,
            "manual_review_approved": bool(args.manual_review_approved),
        }
    )
    has_promotion_history = any(
        field.startswith(("promotion_", "essence_", "top_")) for field in existing
    )
    if "promotion_status" not in entry and not has_promotion_history:
        entry["promotion_status"] = "not_attempted"
    posts[key] = entry
    registry["schema_version"] = SCHEMA_VERSION
    registry["posts"] = posts
    atomic_write_json(registry_path, registry)
    return {
        "registry": str(registry_path),
        "registry_key": key,
        "title": title,
        "image_count": args.image_count,
        "operation": args.operation,
        "verified_at": verified_at,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a verified Arcaea pack-intro publication")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--registry-key")
    parser.add_argument("--operation", choices=("publish", "edit"), default="publish")
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
