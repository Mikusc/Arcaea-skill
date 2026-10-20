#!/usr/bin/env python3
"""Validate a pack-intro draft and freeze a hash-bound Tencent publish plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = 2
MAX_MARKDOWN_CHARS = 10_000
MAX_IMAGES = 50
PLACEHOLDER_RE = re.compile(r"\[\(0,(\d+)\)\]\(@img\)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    return None


def jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    offset = 2
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(data):
            return None
        length = int.from_bytes(data[offset : offset + 2], "big")
        if length < 2 or offset + length > len(data):
            return None
        if marker in sof_markers and length >= 7:
            height = int.from_bytes(data[offset + 3 : offset + 5], "big")
            width = int.from_bytes(data[offset + 5 : offset + 7], "big")
            return width, height
        offset += length
    return None


def image_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    return png_dimensions(data) or jpeg_dimensions(data)


def parse_source(value: str) -> dict:
    url, separator, label = value.partition("|")
    url = url.strip()
    label = label.strip() if separator else "来源"
    if not url:
        raise RuntimeError("source URL cannot be empty")
    return {"url": url, "label": label or "来源"}


def uncovered_naked_urls(markdown: str) -> list[str]:
    without_links = re.sub(r"\[[^\]]+\]\(https?://[^)]+\)", "", markdown)
    return re.findall(r"https?://[^\s)>]+", without_links)


def build_plan(args: argparse.Namespace) -> dict:
    draft_path = Path(args.draft).expanduser().resolve()
    if not draft_path.is_file():
        raise RuntimeError(f"missing draft: {draft_path}")
    markdown = draft_path.read_text(encoding="utf-8")
    image_paths = [Path(value).expanduser().resolve() for value in args.image]
    roles = [str(value).strip() for value in args.image_role]
    errors: list[str] = []
    warnings: list[str] = []
    manual_review_reasons = [str(value).strip() for value in args.manual_review_reason if str(value).strip()]

    if not args.guild_id.strip() or not args.channel_id.strip():
        errors.append("target guild and channel IDs must be non-empty")
    if not args.title.strip():
        errors.append("title is empty")
    indexes = [int(value) for value in PLACEHOLDER_RE.findall(markdown)]
    expected = list(range(len(image_paths)))
    if indexes != expected:
        errors.append(f"image placeholders are not continuous: found={indexes} expected={expected}")
    if len(markdown) > MAX_MARKDOWN_CHARS:
        errors.append(f"Markdown body exceeds {MAX_MARKDOWN_CHARS} characters: {len(markdown)}")
    if len(image_paths) > MAX_IMAGES:
        errors.append(f"image count exceeds Tencent long-post limit: {len(image_paths)}")
    if re.search(r"^# ", markdown, flags=re.MULTILINE):
        warnings.append("Markdown body contains a top-level H1 that duplicates the Tencent title")
        manual_review_reasons.append("top-level H1 retained for compatibility with an older draft")
    naked_urls = uncovered_naked_urls(markdown)
    if naked_urls:
        errors.append(f"Markdown body contains naked URL(s): {naked_urls}")
    for heading in ("## 曲目信息", "## 曲目逐首介绍"):
        if heading not in markdown:
            warnings.append(f"recommended section is missing: {heading}")
            manual_review_reasons.append(f"missing recommended section {heading}")

    if roles and len(roles) != len(image_paths):
        errors.append("--image-role count must match --image count")
    if not roles:
        roles = ["cover"] + ["content"] * max(0, len(image_paths) - 1)
        if image_paths:
            manual_review_reasons.append("image roles were inferred instead of supplied")
    if not image_paths:
        errors.append("pack intro requires at least one image")
    elif roles[0] != "official_bilibili_cover":
        warnings.append("first image is not declared as official_bilibili_cover")
        manual_review_reasons.append("official Bilibili preview cover is not verified as the first image")
    if args.partner_required and "partner" not in roles:
        errors.append("partner image is required but no image role is partner")

    image_records: list[dict] = []
    for index, (path, role) in enumerate(zip(image_paths, roles)):
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty image file: {path}")
            continue
        dimensions = image_dimensions(path)
        if dimensions is None:
            warnings.append(f"could not read image dimensions: {path}")
            manual_review_reasons.append(f"image dimensions need manual verification at index {index}")
        else:
            width, height = dimensions
            if role == "official_bilibili_cover" and width <= height:
                warnings.append(f"official Bilibili cover is not landscape: {width}x{height}")
                manual_review_reasons.append("official cover dimensions are unusual")
            if role.startswith("song") and (width, height) != (512, 512):
                warnings.append(f"song image is not 512x512 at index {index}: {width}x{height}")
                manual_review_reasons.append(f"song image dimensions need review at index {index}")
            if role == "partner" and (abs(width - height) > 4 or not 500 <= max(width, height) <= 800):
                warnings.append(f"partner image is outside the expected square ~600px range: {width}x{height}")
                manual_review_reasons.append("partner image dimensions need review")
        image_records.append(
            {
                "index": index,
                "role": role,
                "file": str(path),
                "sha256": sha256_file(path),
                "width": dimensions[0] if dimensions else None,
                "height": dimensions[1] if dimensions else None,
            }
        )

    sources: list[dict] = []
    for value in args.source:
        try:
            source = parse_source(value)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        if not source["url"].startswith("https://"):
            errors.append(f"source URL must use https: {source['url']}")
        sources.append(source)
    if not sources:
        errors.append("at least one source link is required")
    if not any("bilibili.com/video/" in source["url"] for source in sources):
        warnings.append("no official Bilibili video source was supplied")
        manual_review_reasons.append("official Bilibili preview source needs verification")

    manual_review_reasons = list(dict.fromkeys(manual_review_reasons))
    warnings = list(dict.fromkeys(warnings))
    errors = list(dict.fromkeys(errors))
    validation_passed = not errors
    requires_manual_review = bool(manual_review_reasons)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "title": args.title.strip(),
        "target": {
            "guild_name": "韵律源点Arcaea",
            "channel_name": "曲包信息",
            "guild_id": str(args.guild_id),
            "channel_id": str(args.channel_id),
        },
        "draft": str(draft_path),
        "draft_sha256": sha256_file(draft_path),
        "char_count": len(markdown),
        "placeholder_indexes": indexes,
        "image_count": len(image_paths),
        "images": image_records,
        "sources": sources,
        "partner_required": bool(args.partner_required),
        "validation_passed": validation_passed,
        "requires_manual_review": requires_manual_review,
        "draft_ready": validation_passed and not requires_manual_review,
        "manual_review_reasons": manual_review_reasons,
        "errors": errors,
        "warnings": warnings,
        "confirmation_phrase": f"确认发布 {args.title.strip()}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a hash-bound Arcaea pack-intro publish plan")
    parser.add_argument("--title", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--image", action="append", default=[], help="Ordered image path; repeat for every placeholder")
    parser.add_argument(
        "--image-role",
        action="append",
        default=[],
        help="Ordered role matching --image: official_bilibili_cover, song, partner, pack_cover, content",
    )
    parser.add_argument("--source", action="append", default=[], help="Source formatted as https://url|label")
    parser.add_argument("--partner-required", action="store_true")
    parser.add_argument("--manual-review-reason", action="append", default=[])
    parser.add_argument("--guild-id", required=True)
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    plan = build_plan(args)
    draft_path = Path(args.draft).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve() if args.out else draft_path.with_name(f"{draft_path.stem}.publish-plan.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "plan": str(out_path),
                "draft_ready": plan["draft_ready"],
                "requires_manual_review": plan["requires_manual_review"],
                "error_count": len(plan["errors"]),
                "warning_count": len(plan["warnings"]),
                "image_count": plan["image_count"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
