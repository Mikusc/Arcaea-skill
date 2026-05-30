---
name: arcaea-pack-intro-publisher
description: Use when preparing, updating, or publishing Arcaea 曲包介绍 long posts for Tencent Channel “曲包信息”, especially posts that use Markdown, official Bilibili video covers, Arcaea中文Wiki song/partner images, per-song factual wiki summaries, unlock/progression notes, and explicit confirmation before posting.
metadata: {"openclaw":{"emoji":"🎼"}}
---

# Arcaea Pack Intro Publisher

## Scope

This skill is for **曲包介绍** posts, not short update intelligence.

Use it when the user asks to:

- continue publishing Arcaea 曲包信息 / 曲包介绍 posts
- decide the next pack in the current intro sequence
- draft a pack intro in the current Markdown format
- add per-song wiki-based introductions and covers
- replace the first image with the official Bilibili video cover
- publish or update a Tencent Channel post in `韵律源点Arcaea / 曲包信息`

For current/future Bilibili update dynamics and `更新情报`, use `arcaea-update-publisher` instead. For any actual Tencent Channel operation, also use `tencent-channel-community`.

## Fixed Defaults

- Workspace: `/Users/mikusc/Documents/ArcaeaChannel`
- Draft root: `/Users/mikusc/Documents/ArcaeaChannel/pack_intro_drafts`
- Asset root: `/Users/mikusc/Documents/ArcaeaChannel/pack_intro_assets`
- Current sequence folder: `/Users/mikusc/Documents/ArcaeaChannel/pack_intro_drafts/main_story_act2`
- Tencent Channel: `韵律源点Arcaea`
- Target board for pack intros: `曲包信息`
- Production IDs for CLI calls:
  - guild `63281101636793373`
  - channel `686566029`
- Official Bilibili UID for Arcaea CN: `404145357`
- Arcaea中文Wiki domain: `https://arcwiki.mcd.blue`

Treat Tencent Channel IDs and Bilibili/Tencent cookies or tokens as execution-only data. Do not echo cookies or tokens.

## Safety Boundary

- Never publish, edit, delete, comment, like, or move Tencent Channel content without explicit confirmation in the current interaction.
- Drafting, source lookup, image downloading, local conversion, and validation are allowed without extra confirmation.
- Before publishing a new post, present:
  - planned title
  - target channel/board
  - body summary
  - image count and exact image order
  - source links
  - local draft path
- Before editing an existing post, present:
  - target post title/link
  - what changes
  - final image count and order
  - source links
  - local draft path
- Explicit confirmations such as `确认发布 Severed Eden`, `发布这篇`, or `更新帖子` can trigger the external action.
- If the user asks a factual question like “下一个曲包是什么”, answer directly from the local order and do not publish.

## Current Main Story Act II Order

Use `/Users/mikusc/Documents/ArcaeaChannel/pack_intro_drafts/main_story_act2/00-posting-order.md` as the local order file.

Current order:

1. `Lasting Eden`
2. `Severed Eden` / `Lasting Eden Chapter 2`
3. `Shifting Veil`
4. `Absolute Nihil`
5. `Lucent Historia`
6. `Liminal Eclipse` as a current-version supplement when appropriate

If the user asks “下一个”, check which posts have already been published in the current conversation or by searching Tencent Channel, then answer the next unpublished pack.

## Draft File Convention

Use one local publish-ready Markdown file per pack:

```text
/Users/mikusc/Documents/ArcaeaChannel/pack_intro_drafts/main_story_act2/<NN>-<pack-slug>-pack-intro-channel-publish.md
```

If updating an already published draft, create a new version instead of overwriting unless the user asks otherwise:

```text
.../<NN>-<pack-slug>-pack-intro-channel-publish-v2.md
.../<NN>-<pack-slug>-pack-intro-channel-publish-v3.md
```

Keep earlier drafts as provenance. Do not delete them unless the user explicitly asks.

## Asset Convention

Use one asset folder per pack:

```text
/Users/mikusc/Documents/ArcaeaChannel/pack_intro_assets/<pack-slug>/
  video-cover/
  wiki/
  converted/
```

Image order for a full post:

1. `[(0,0)](@img)` official Bilibili preview cover, preferably the final/current official video cover.
2. One image per song, from Arcaea中文Wiki or official wiki source, converted to `512x512`.
3. Partner image or important pack/character image from wiki, converted around `600x600`.

When a pack has no partner or the partner is not central, use the pack cover or key hidden-song cover instead. Do not invent images.

Use `sips` for simple local resizing on macOS:

```bash
sips -Z 512 "/path/wiki/song.jpg" --out "/path/converted/song_512.jpg"
sips -Z 600 "/path/wiki/partner.png" --out "/path/converted/partner_600.png"
```

Validate dimensions with `file` before publishing.

## Source Lookup

### Bilibili Video Cover

Prefer the official preview video from `韵律源点Arcaea`.

Find it through search or Bilibili API, then download the `pic` / archive cover URL into `video-cover/`.

For search, use queries combining:

- pack name
- `韵律源点Arcaea`
- `预览`
- `Arcaea主线故事第二幕`
- BVID if already known

Record the official video URL as a post link:

```text
https://www.bilibili.com/video/<BVID>|官方预览
```

If the official video title or cover changed after release, use the latest/current official cover and mention the wiki note only if it is relevant to the pack story.

### Wiki Text

Use Arcaea中文Wiki individual pages, not only the pack page.

For each song, open the song detail page and extract:

- artist
- duration
- BPM
- side/background
- difficulty levels
- chart constants
- note counts
- chart designer names
- unlock conditions
- useful `游戏相关`
- optional `攻略` only when it is clearly useful; if used, summarize it as play/configuration information without turning it into a subjective review

For partner or pack pages, extract:

- price
- type
- mobile version/date
- purchase requirement
- partner unlock
- pack transformation or special effect notes

Do not treat wiki攻略 as objective fact. Do not quote large blocks. Summarize.

In the published body, do not emphasize the source mechanically:

- Do not write phrases such as `wiki 说`, `wiki 记载`, `wiki 详情页可用信息`, `wiki 里没有`, `暂无额外条目`, or `当前 wiki 文本未给出`.
- Do not add absence statements just because a source field is empty. Omit the missing field instead.
- Present extracted facts directly under neutral headings such as `基本信息`, `解禁`, `补充信息`, `购买与基本信息`, and `解锁与推进`.
- Keep source provenance in the local workflow and publication confirmation, not as repeated wording inside every song section.

### Image URLs From Wiki

Song and partner images are usually visible in page HTML as `/images/...` or `/images/thumb/...`.

Prefer original full-size files where possible:

```text
https://arcwiki.mcd.blue/images/<path>/Songs_xxx.jpg
https://arcwiki.mcd.blue/images/<path>/Partner_xxx.png
```

If only a thumbnail is found, download the largest practical thumbnail and convert locally.

## Writing Structure

Use a factual Markdown long-post structure. The article should read like a compact information post, not a review essay.

```markdown
> 以下内容涉及 **<pack/story spoiler scope>** 剧情、隐藏曲与解锁机制剧透。

[(0,0)](@img)

# <Pack Name> 曲包介绍

<1-2 short factual intro paragraphs: type, version/date, price, song count, prerequisite, central unlock/partner mechanic if any. Avoid broad thematic claims.>

## 曲目信息

<optional note about order: update order, progression order, hidden/final order>

| 曲目 | 曲师 | 难度 | 定数 |
| --- | --- | --- | --- |
| **Song** | Artist | `...` | `...` |

## 曲目逐首介绍

### 1. Song

[(0,1)](@img)

**基本信息：** 曲师、时长、BPM、背景、Note 数、谱面设计。

**解禁：** 解禁条件。

**补充信息：** 公募身份、定数变更、联动、特殊配置、长版、词义、谱师首作等 factual details. Omit this line if there is no useful detail.

## 购买与基本信息

价格、平台、Pack Append / prerequisite、搭档、版本日期。

[(0,N)](@img)

## 解锁与推进逻辑

Write a sequential user-readable flow when the pack has unlock progression.

<End after necessary unlock/progression, purchase, partner, and mechanism information. Do not add `曲包定位`, `编者短评`, or an essay-like closing interpretation unless the user explicitly asks for commentary.>
```

Default style:

- `基本信息` is factual.
- `解禁` is factual.
- `补充信息` is factual and should not mention the source label repeatedly.
- Avoid evaluative or descriptive filler such as `关键词是`, `如果说 A 是...那么 B 是...`, `它不是...而是...`, `我会把它看作...`, `最世界观型`, `回声型`, `边界`, `收束`, unless the user explicitly asks for a more editorial tone.
- Avoid commentary sections by default. The current preferred style is necessary information only.

If the user asks whether comments were invented, be explicit. Do not claim editor interpretation came from wiki.

## Unlock And Progression Section

For packs with unlock mechanics, include a standalone `## 解锁与推进逻辑` section even if per-song sections already mention unlocks.

Use a simple sequence:

```text
购买/前置曲包 -> 普通曲目 -> 前置曲/最终曲 -> 隐藏曲条件 -> 组曲/异象/首次游玩 -> 曲包形态或搭档变化
```

Examples:

- `Lasting Eden`: first three songs -> `UNKNOWN LEVELS` -> `Abstruse Dilemma` -> later connection to `Lasting Eden Chapter 2` / `Severed Eden`.
- `Severed Eden`: purchase `Lasting Eden Chapter 2` -> three normal songs -> `Ego Eimi` -> story and name-filling conditions -> select Maya -> medley challenge -> first `Arghena` play -> pack transforms into `Severed Eden`.

## Validation Before Asking To Publish

Run local checks:

```bash
python3 - <<'PY'
from pathlib import Path
import re
p = Path("/path/to/draft.md")
s = p.read_text()
idx = [int(m.group(1)) for m in re.finditer(r'\[\(0,(\d+)\)\]\(@img\)', s)]
print("placeholder_count", len(idx))
print("placeholder_indexes", idx)
print("contiguous_from_zero", idx == list(range(len(idx))))
print("has_naked_url", bool(re.search(r'https?://', s)))
print("char_count", len(s))
PY
```

Expected:

- placeholder count equals image count
- indexes are contiguous from zero
- no naked URLs in post body
- first image is official video cover
- song images are in the same order as the sections
- partner/pack image index matches the placeholder location

Check images:

```bash
file "/path/video-cover.jpg" "/path/converted/song1_512.jpg" "/path/converted/partner_600.png"
```

Before publishing, search for an existing post to avoid duplicates:

```bash
tencent-channel-cli feed search-guild-feeds \
  --guild-id 63281101636793373 \
  --query "<Pack Name>曲包介绍" \
  --json
```

The search command does not accept `--channel-id`; filter results by title/author if needed.

## Confirmation Message

Before a new external post, send a concise confirmation summary:

```text
本地稿已准备好，还没发布。

发布计划：
- 标题：`<Pack Name>曲包介绍`
- 版块：`韵律源点Arcaea / 曲包信息`
- 正文：<summary>
- 图片：`N` 张
- 图片顺序：官方 Bilibili 视频封面 -> ...
- 校验：占位符连续、无裸 URL、素材尺寸正常、CLI 已登录、未发现同名已发帖子
- 本地稿：<absolute path>

确认的话回复 “确认发布 <Pack Name>”。
```

## Tencent Channel Publish

Use `tencent-channel-community` rules.

Daily/version checks before writing:

```bash
curl -sI -L https://connect.qq.com/skills/tencent-channel-community.zip | tr -d '\r' | rg -i 'x-cos-meta-tcc-version|x-cos-meta-tcc-cli-version'
tencent-channel-cli version
tencent-channel-cli login status --json
tencent-channel-cli schema feed.publish-feed --json
```

Publish confirmed Markdown post:

```bash
tencent-channel-cli feed publish-feed \
  --guild-id 63281101636793373 \
  --channel-id 686566029 \
  --feed-type 2 \
  --title "<Pack Name>曲包介绍" \
  --markdown-content "$(< /absolute/path/to/publish.md)" \
  --image "/absolute/path/to/video-cover.jpg" \
  --image "/absolute/path/to/song1_512.jpg" \
  --image "/absolute/path/to/song2_512.jpg" \
  --image "/absolute/path/to/partner_600.png" \
  --link "https://www.bilibili.com/video/<BVID>|官方预览" \
  --json
```

If image upload fails with a transient upload/server error, retry the same command once before changing content or compressing images.

## Tencent Channel Edit Existing Post

Use this only after explicit confirmation such as `更新帖子`.

Fetch current detail:

```bash
tencent-channel-cli feed get-feed-detail \
  --guild-id 63281101636793373 \
  --channel-id 686566029 \
  --feed-id "<feed_id>" \
  --json
```

For Markdown post replacement with reordered/replaced images:

```bash
tencent-channel-cli feed alter-feed \
  --guild-id 63281101636793373 \
  --channel-id 686566029 \
  --feed-id "<feed_id>" \
  --create-time "<create_time_raw>" \
  --feed-type 2 \
  --markdown-content "$(< /absolute/path/to/publish-vN.md)" \
  --clear-images \
  --image "/absolute/path/to/video-cover.jpg" \
  --image "/absolute/path/to/song1_512.jpg" \
  --image "/absolute/path/to/song2_512.jpg" \
  --image "/absolute/path/to/partner_600.png" \
  --link "https://www.bilibili.com/video/<BVID>|官方预览" \
  --json
```

Keep placeholder indexes aligned with the ordered `--image` flags.

## Post-Publish Verification

Always verify the newly created or edited post:

```bash
tencent-channel-cli feed get-feed-detail \
  --guild-id 63281101636793373 \
  --channel-id 686566029 \
  --feed-id "<feed_id>" \
  --json
```

Parse or inspect:

- `title`
- `feed_type == 2`
- `content_richtext.is_markdown == true` or equivalent `is_markdown`
- `image_count`
- `content_richtext.source_markdown` contains expected new phrase
- placeholders are still `0..N-1`
- first image dimensions match official cover, usually `1728x1080`
- song images are `512x512`
- partner image is around `600x600`
- `share_url`

Final user report should include:

- posted/updated title
- share URL in angle brackets, e.g. `<https://pd.qq.com/s/...>`
- image count and order verification
- local draft path
- next pack if useful

Do not expose internal IDs in the final answer unless necessary for troubleshooting.

## Proven Examples

Published/validated examples from this workflow:

- `Lasting Eden曲包介绍`
  - draft: `/Users/mikusc/Documents/ArcaeaChannel/pack_intro_drafts/main_story_act2/01-lasting-eden-pack-intro-channel-publish-v3.md`
  - images: official Bilibili preview cover, five song covers, Maya partner image
  - share: `<https://pd.qq.com/s/5e2uqhrpd>`
- `Severed Eden曲包介绍`
  - draft: `/Users/mikusc/Documents/ArcaeaChannel/pack_intro_drafts/main_story_act2/02-severed-eden-pack-intro-channel-publish.md`
  - images: official Bilibili preview cover, five song covers, Insight partner image
  - share: `<https://pd.qq.com/s/4zczxspvc>`

These are examples of structure, not immutable source text. Recheck wiki and official Bilibili data for future posts because details, titles, and covers can change.
