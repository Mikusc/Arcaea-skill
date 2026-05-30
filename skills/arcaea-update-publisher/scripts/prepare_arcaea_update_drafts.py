#!/usr/bin/env python3
"""Prepare merged Arcaea update drafts from Bilibili dynamics.

This script intentionally does not publish anything by itself. It creates draft
text files, downloads source images, and writes a manifest that a later
publishing step can use for Tencent Channel posting or editing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


API_URL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
DEFAULT_UID = "404145357"
DEFAULT_STATE = ".arcaea_update_publisher_state.json"
DEFAULT_RULES_FILE = "arcaea_update_rules.json"

DEFAULT_RULES = {
    "version_patterns": [
        r"v\s*\d+(?:\.\d+){1,2}",
        r"(?<!\d)\d+(?:\.\d+){1,2}(?=\s*版本)",
    ],
    "date_patterns": [
        r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]",
        r"\d{1,2}\s*月\s*\d{1,2}\s*[日号]",
    ],
    "update_keywords": [
        "更新",
        "版本",
        "将于",
        "上线",
        "开放",
        "推出",
        "实装",
        "追加",
        "新增",
        "加入",
        "登场",
        "限时",
        "期间",
        "起至",
        "复刻",
        "预览",
        "维护",
    ],
    "subject_keywords": [
        "Pack Append",
        "World Extend",
        "Memory Archive",
        "Main Story",
        "Side Story",
        "Arcaea Online",
    ],
    "max_unversioned_merge_hours": 6,
    "include_keywords": [],
    "ignore_keywords": [
        "壁纸",
        "周边",
        "生日快乐",
        "直播",
        "OST",
        "原声带",
        "商品",
        "实体专辑",
    ],
    "category_rules": [
        {"key": "world-extend", "title": "World Extend 更新", "keywords": ["World Extend"]},
        {"key": "pack-append", "title": "Pack Append 更新", "keywords": ["Pack Append", "追加包"]},
        {"key": "collaboration", "title": "联动更新", "keywords": ["联动", "合作"]},
        {"key": "new-songs", "title": "新曲追加", "keywords": ["新曲", "新歌", "追加曲"]},
        {"key": "limited-event", "title": "限时活动", "keywords": ["限时", "期间", "起至"]},
        {"key": "version-update", "title": "版本更新", "keywords": ["版本更新", "更新后", "维护"]},
    ],
}


def clone_default_rules() -> dict:
    return json.loads(json.dumps(DEFAULT_RULES, ensure_ascii=False))


def load_rules(workspace: Path, config_file: str | None) -> tuple[dict, str]:
    if config_file:
        path = Path(config_file).expanduser()
    else:
        path = workspace / DEFAULT_RULES_FILE
    rules = clone_default_rules()
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise RuntimeError(f"rules config must be a JSON object: {path}")
        for key, value in loaded.items():
            rules[key] = value
        return rules, str(path.resolve())
    return rules, ""


def item_haystack(item: dict) -> str:
    return "\n".join([item.get("title") or "", item.get("text") or ""])


def term_hits(text: str, terms: list[str]) -> list[str]:
    text_lower = text.lower()
    hits = []
    for term in terms or []:
        term_text = str(term).strip()
        if term_text and term_text.lower() in text_lower:
            hits.append(term_text)
    return hits


def regex_hits(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for pattern in patterns or []:
        try:
            found = re.findall(str(pattern), text, flags=re.IGNORECASE)
        except re.error as exc:
            raise RuntimeError(f"invalid regex in rules config: {pattern!r}: {exc}") from exc
        for value in found:
            if isinstance(value, tuple):
                value = next((x for x in value if x), "")
            value = str(value).strip()
            if value:
                hits.append(value)
    return hits


def normalize_version(value: str) -> str:
    value = re.sub(r"\s+", "", str(value)).lower()
    if value and value[0].isdigit():
        value = "v" + value
    return value


def extract_versions(text: str, rules: dict) -> list[str]:
    out = []
    for value in regex_hits(text, rules.get("version_patterns") or []):
        version = normalize_version(value)
        if version and version not in out:
            out.append(version)
    return out


def extract_quoted_subjects(text: str) -> list[str]:
    subjects = []
    patterns = [
        r"[「『《](.{2,60}?)[」』》]",
        r"“(.{2,60}?)”",
        r'"(.{2,60}?)"',
    ]
    for value in regex_hits(text, patterns):
        cleaned = re.sub(r"\s+", " ", value).strip()
        if cleaned and cleaned.lower() != "arcaea" and cleaned not in subjects:
            subjects.append(cleaned)
    return subjects


def choose_subject(text: str, rules: dict) -> tuple[str, list[str]]:
    quoted = extract_quoted_subjects(text)
    if quoted:
        return quoted[0], quoted
    hits = term_hits(text, rules.get("subject_keywords") or [])
    if hits:
        return hits[0], hits
    return "", []


def category_for(text: str, rules: dict) -> tuple[str, str, list[str]]:
    for rule in rules.get("category_rules") or []:
        hits = term_hits(text, rule.get("keywords") or [])
        if hits:
            return str(rule.get("key") or "update"), str(rule.get("title") or "更新情报"), hits
    return "", "", []


def parse_since(value: str | None) -> int:
    if not value:
        return 0
    value = value.strip()
    if value.isdigit():
        return int(value)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return int(datetime.strptime(value, fmt).timestamp())
        except ValueError:
            pass
    raise RuntimeError("--since must be a Unix timestamp or date like 2026-04-25")


def unversioned_merge_window_seconds(rules: dict) -> int:
    try:
        hours = float(rules.get("max_unversioned_merge_hours", 6))
    except (TypeError, ValueError):
        hours = 6
    return max(0, int(hours * 3600))


def load_cookie(workspace: Path, cookie_file: str | None) -> str:
    if cookie_file:
        path = Path(cookie_file)
    else:
        path = workspace / ".bili_cookie"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return os.environ.get("BILI_COOKIE", "").strip()


def request_json(uid: str, offset: str, cookie: str) -> dict:
    params = {
        "host_mid": uid,
        "features": (
            "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,forwardListHidden,"
            "decorationCard,commentsNewVersion,onlyfansAssetsV2,ugcDelete,onlyfansQaCard,"
            "avatarAutoTheme,sunflowerStyle,cardsEnhance,eva3CardOpus,eva3CardVideo,"
            "eva3CardComment,eva3CardUser"
        ),
        "timezone_offset": "-480",
        "platform": "web",
    }
    if offset:
        params["offset"] = offset
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15"
        ),
        "Referer": f"https://space.bilibili.com/{uid}/dynamic",
        "Origin": "https://space.bilibili.com",
        "Accept": "application/json, text/plain, */*",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
    text = body.decode("utf-8", errors="replace")
    if "错误号: 412" in text or "bilibili security control policy" in text:
        raise RuntimeError("Bilibili returned 412 security control; refresh .bili_cookie or retry later.")
    data = json.loads(text)
    if data.get("code") == -412:
        raise RuntimeError("Bilibili returned code=-412; refresh .bili_cookie or retry later.")
    if data.get("code") != 0:
        raise RuntimeError(f"Bilibili API error: code={data.get('code')} message={data.get('message')}")
    return data


def fetch_pages(uid: str, pages: int, sleep_seconds: float, cookie: str) -> list[dict]:
    offset = ""
    out = []
    for page in range(pages):
        data = request_json(uid, offset, cookie)
        out.append(data)
        page_data = data.get("data") or {}
        offset = page_data.get("offset") or ""
        if not page_data.get("has_more") or not offset:
            break
        if page + 1 < pages:
            time.sleep(sleep_seconds)
    return out


def module_dynamic(item: dict) -> dict:
    return ((item.get("modules") or {}).get("module_dynamic") or {})


def item_text_and_title(item: dict) -> tuple[str, str]:
    dyn = module_dynamic(item)
    desc = dyn.get("desc") or {}
    text = desc.get("text") or ""
    major = dyn.get("major") or {}
    title = ""
    for key in ("archive", "article", "opus"):
        obj = major.get(key) or {}
        if obj:
            title = obj.get("title") or title
            if key == "opus":
                text = text or ((obj.get("summary") or {}).get("text") or "")
            break
    return text.strip(), title.strip()


def item_images(item: dict) -> list[str]:
    major = module_dynamic(item).get("major") or {}
    urls = []
    opus = major.get("opus") or {}
    for pic in opus.get("pics") or []:
        if isinstance(pic, dict):
            url = pic.get("url") or pic.get("src") or pic.get("img_src")
            if url:
                urls.append(url)
    draw = major.get("draw") or {}
    for pic in draw.get("items") or []:
        if isinstance(pic, dict):
            url = pic.get("src") or pic.get("url")
            if url:
                urls.append(url)
    archive = major.get("archive") or {}
    if archive.get("cover"):
        urls.append(archive["cover"])
    clean = []
    for url in urls:
        url = str(url)
        if url.startswith("//"):
            url = "https:" + url
        url = url.replace("http://", "https://", 1)
        if url not in clean:
            clean.append(url)
    return clean


def author_time(item: dict) -> tuple[int, str]:
    author = (item.get("modules") or {}).get("module_author") or {}
    raw = author.get("pub_ts") or 0
    try:
        raw = int(raw)
    except (TypeError, ValueError):
        raw = 0
    return raw, str(author.get("pub_time") or "")


def simplify_item(item: dict) -> dict:
    text, title = item_text_and_title(item)
    pub_ts, pub_time = author_time(item)
    item_id = str(item.get("id_str") or "")
    return {
        "id": item_id,
        "pub_ts": pub_ts,
        "pub_time": pub_time,
        "type": item.get("type"),
        "text": text,
        "title": title,
        "images": item_images(item),
        "source_url": f"https://t.bilibili.com/{item_id}" if item_id else "",
    }


def classify_item(
    item: dict,
    rules: dict,
    version_filter: str,
    extra_keywords: list[str],
    extra_ignore_keywords: list[str],
) -> dict | None:
    hay = item_haystack(item)
    include_hits = term_hits(hay, (rules.get("include_keywords") or []) + extra_keywords)
    ignore_hits = term_hits(hay, (rules.get("ignore_keywords") or []) + extra_ignore_keywords)
    if ignore_hits and not include_hits:
        return None

    versions = extract_versions(hay, rules)
    version_match = not version_filter or version_filter in versions
    if version_filter and versions and not version_match:
        return None

    update_hits = term_hits(hay, rules.get("update_keywords") or [])
    date_hits = regex_hits(hay, rules.get("date_patterns") or [])
    subject, subject_hits = choose_subject(hay, rules)
    category_key, category_title, category_hits = category_for(hay, rules)

    if version_filter:
        if version_match:
            related = bool(include_hits or update_hits or subject or category_key)
        else:
            related = not versions and bool(date_hits) and bool(subject or category_key or update_hits)
    else:
        related = (
            bool(include_hits)
            or bool(versions and (update_hits or subject_hits or category_key))
            or bool(subject and (update_hits or date_hits or category_key))
            or bool(category_key and (update_hits or date_hits))
        )
    if not related:
        return None

    primary_version = versions[0] if versions else ""
    matched = []
    for value in include_hits + update_hits + subject_hits + category_hits + date_hits:
        if value not in matched:
            matched.append(value)
    return {
        "versions": versions,
        "primary_version": primary_version,
        "subject": subject,
        "subject_key": safe_key(subject) if subject else "",
        "category_key": category_key,
        "category_title": category_title,
        "matched": matched,
    }


def build_group_key(meta: dict, item_id: str) -> str:
    version = safe_name(meta.get("primary_version") or "")
    subject_key = meta.get("subject_key") or ""
    category_key = safe_name(meta.get("category_key") or "")
    if version and subject_key:
        return f"{version}-{subject_key}"
    if subject_key:
        return subject_key
    if version and category_key:
        return f"{version}-{category_key}"
    if version:
        return f"{version}-update"
    if category_key:
        return category_key
    return f"dynamic-{item_id}"


def unique_values(items: list[dict], key: str) -> list[str]:
    out = []
    for item in items:
        meta = item.get("_meta") or {}
        values = meta.get(key)
        if isinstance(values, list):
            candidates = values
        else:
            candidates = [values]
        for value in candidates:
            value = str(value or "").strip()
            if value and value not in out:
                out.append(value)
    return out


def format_subject(subject: str) -> str:
    if not subject:
        return ""
    if re.search(r"[\u4e00-\u9fff]", subject):
        return f"《{subject}》"
    return f"「{subject}」"


def group_title(key: str, items: list[dict]) -> str:
    versions = unique_values(items, "primary_version")
    subjects = unique_values(items, "subject")
    categories = unique_values(items, "category_title")
    version = versions[0] if versions else ""
    subject = subjects[0] if subjects else ""
    category = categories[0] if categories else ""
    if subject and version:
        return f"{format_subject(subject)} {version} 更新情报"
    if subject:
        return f"{format_subject(subject)} 更新情报"
    if version and category:
        return f"Arcaea {version} {category}"
    if version:
        return f"Arcaea {version} 更新情报"
    if category:
        return f"Arcaea {category}"
    first_title = next((x.get("title") for x in items if x.get("title")), "")
    if first_title:
        return first_title[:60]
    text = (items[0].get("text") or "Arcaea 更新情报").replace("\n", " ")
    return text[:60]


HASHTAG_RE = re.compile(r"#[^#\s][^#]{0,40}#")


def clean_for_long_post(text: str) -> str:
    text = HASHTAG_RE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def merge_text(items: list[dict]) -> str:
    blocks = []
    seen = set()
    for item in sorted(items, key=lambda x: x.get("pub_ts") or 0):
        text = clean_for_long_post(item.get("text") or item.get("title") or "")
        if not text:
            continue
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        blocks.append(text)
    return "\n\n".join(blocks).strip()


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"handled_ids": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_key(text: str) -> str:
    base = safe_name(text.lower())
    if base != "draft":
        return base
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"topic-{digest}"


def mark_handled(state_file: Path, manifest_path: Path) -> None:
    state = load_state(state_file)
    handled = set(map(str, state.get("handled_ids") or []))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    handled_groups = state.get("handled_groups") or []
    marked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for group in manifest.get("groups") or []:
        for item_id in group.get("source_ids") or []:
            handled.add(str(item_id))
        handled_groups.append({
            "key": group.get("key"),
            "title": group.get("title"),
            "source_ids": group.get("source_ids") or [],
            "marked_at": marked_at,
        })
    state["handled_ids"] = sorted(handled)
    state["handled_groups"] = handled_groups[-200:]
    state["last_marked_at"] = marked_at
    save_state(state_file, state)


def safe_name(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-")
    return text[:80] or "draft"


def download(url: str, path: Path) -> None:
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://space.bilibili.com/"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        path.write_bytes(resp.read())


def prepare(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace).expanduser().resolve()
    out_dir = (workspace / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    state_file = (workspace / args.state_file).resolve()
    state = load_state(state_file)
    handled = set(map(str, state.get("handled_ids") or []))
    rules, config_path = load_rules(workspace, args.config)
    version_filter = normalize_version(args.version) if args.version else ""
    since_ts = parse_since(args.since)

    cookie = load_cookie(workspace, args.cookie_file)
    pages = fetch_pages(args.uid, args.pages, args.sleep, cookie)
    raw_path = out_dir / "bili_raw_pages.json"
    raw_path.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")

    items = []
    for page in pages:
        for raw_item in (page.get("data") or {}).get("items") or []:
            item = simplify_item(raw_item)
            if not item.get("id"):
                continue
            if not args.include_handled and item["id"] in handled:
                continue
            if since_ts and item.get("pub_ts") and item["pub_ts"] < since_ts:
                continue
            meta = classify_item(
                item,
                rules,
                version_filter,
                args.keyword or [],
                args.ignore_keyword or [],
            )
            if meta:
                item["_meta"] = meta
                item["_group_key"] = build_group_key(meta, item["id"])
                items.append(item)

    groups: dict[str, list[dict]] = {}
    versioned_subject_groups: dict[str, set[str]] = {}
    versioned_candidates: list[tuple[str, int]] = []
    for item in items:
        meta = item.get("_meta") or {}
        if meta.get("primary_version") and meta.get("subject_key"):
            versioned_subject_groups.setdefault(meta["subject_key"], set()).add(item["_group_key"])
        if meta.get("primary_version") and item.get("pub_ts"):
            versioned_candidates.append((item["_group_key"], int(item["pub_ts"])))

    merge_window = unversioned_merge_window_seconds(rules)
    for item in items:
        key = item["_group_key"]
        meta = item.get("_meta") or {}
        if not meta.get("primary_version") and meta.get("subject_key"):
            candidates = versioned_subject_groups.get(meta["subject_key"]) or set()
            if len(candidates) == 1:
                key = next(iter(candidates))
                item["_group_key"] = key
        elif not meta.get("primary_version") and not meta.get("subject_key") and merge_window and item.get("pub_ts"):
            item_ts = int(item["pub_ts"])
            nearest = min(
                versioned_candidates,
                key=lambda candidate: abs(candidate[1] - item_ts),
                default=None,
            )
            if nearest and abs(nearest[1] - item_ts) <= merge_window:
                key = nearest[0]
                item["_group_key"] = key
        groups.setdefault(key, []).append(item)

    if version_filter:
        groups = {
            key: group_items
            for key, group_items in groups.items()
            if any(version_filter in ((item.get("_meta") or {}).get("versions") or []) for item in group_items)
        }

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    manifest = {
        "generated_at": generated_at,
        "uid": args.uid,
        "config_file": config_path,
        "version_filter": version_filter,
        "since": args.since or "",
        "groups": [],
        "raw_pages": str(raw_path),
    }
    for key, group_items in sorted(groups.items(), key=lambda kv: min(x["pub_ts"] for x in kv[1])):
        group_items = sorted(group_items, key=lambda x: x.get("pub_ts") or 0)
        title = group_title(key, group_items)
        body = merge_text(group_items)
        source_links = [x["source_url"] for x in group_items if x.get("source_url")]
        base = safe_name(key)
        text_path = out_dir / f"{base}.txt"
        text_path.write_text(body + "\n", encoding="utf-8")

        image_urls = []
        for item in group_items:
            for url in item.get("images") or []:
                if url not in image_urls:
                    image_urls.append(url)
        image_files = []
        for idx, url in enumerate(image_urls, start=1):
            suffix = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
            image_path = out_dir / f"{base}_{idx}{suffix}"
            if not image_path.exists():
                try:
                    download(url, image_path)
                except Exception as exc:  # keep draft usable if image download fails
                    print(f"warning: failed to download image {url}: {exc}", file=sys.stderr)
                    continue
            image_files.append(str(image_path))

        manifest["groups"].append({
            "key": key,
            "title": title,
            "content_file": str(text_path),
            "image_files": image_files,
            "source_ids": [x["id"] for x in group_items],
            "source_links": source_links,
            "pub_times": [x["pub_time"] for x in group_items],
            "versions": unique_values(group_items, "versions") or unique_values(group_items, "primary_version"),
            "subjects": unique_values(group_items, "subject"),
            "matched": unique_values(group_items, "matched"),
        })

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state["last_checked_at"] = generated_at
    state["last_manifest"] = str(manifest_path)
    save_state(state_file, state)
    print(json.dumps({"manifest": str(manifest_path), "group_count": len(manifest["groups"])}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare merged Arcaea update drafts.")
    parser.add_argument("--workspace", default=".", help="Workspace containing .bili_cookie and state")
    parser.add_argument("--uid", default=DEFAULT_UID, help="Bilibili UID")
    parser.add_argument("--pages", type=int, default=5, help="Recent pages to fetch")
    parser.add_argument("--sleep", type=float, default=3.0, help="Seconds between Bilibili pages")
    parser.add_argument("--cookie-file", help="Optional Bilibili Cookie file")
    parser.add_argument("--state-file", default=DEFAULT_STATE, help="State file relative to workspace")
    parser.add_argument("--out-dir", default="arcaea_update_drafts", help="Draft output dir relative to workspace")
    parser.add_argument("--config", help=f"Rules JSON file; defaults to workspace/{DEFAULT_RULES_FILE} if present")
    parser.add_argument("--version", help="Only collect this Arcaea version, such as v6.15")
    parser.add_argument("--keyword", action="append", default=[], help="Extra include keyword; can be repeated")
    parser.add_argument("--ignore-keyword", action="append", default=[], help="Extra ignore keyword; can be repeated")
    parser.add_argument("--since", help="Only collect dynamics at or after a Unix timestamp or date like 2026-04-25")
    parser.add_argument("--include-handled", action="store_true", help="Include source IDs already recorded as handled")
    parser.add_argument("--mark-handled", help="Manifest path whose source IDs should be marked handled")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    state_file = (workspace / args.state_file).resolve()
    if args.mark_handled:
        mark_handled(state_file, Path(args.mark_handled).expanduser().resolve())
    else:
        prepare(args)


if __name__ == "__main__":
    main()
