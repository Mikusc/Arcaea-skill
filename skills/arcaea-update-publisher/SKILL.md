---
name: arcaea-update-publisher
description: Use when collecting current or future Arcaea update dynamics from Bilibili, detecting versions and update topics, merging related posts into Markdown long-form Tencent Channel drafts with interleaved source images, automatically publishing or appending eligible update posts to the Tencent Channel “更新情报” board, and recording handled source dynamics.
metadata: {"openclaw":{"emoji":"🎵"}}
---

# Arcaea Update Publisher

## Overview

This skill prepares and publishes Arcaea update intelligence posts from the official Bilibili space, detects version numbers and update topics, groups related dynamics into long-form Tencent Channel drafts, downloads source images, updates existing same-version Tencent Channel posts when appropriate, and records which dynamics have been handled.

Tencent Channel publishing and editing must follow the `tencent-channel-community` skill. This skill is allowed to auto-run `publish-feed` and `alter-feed` only for eligible Arcaea update-intelligence posts in the configured production channel and board.

## Fixed Defaults

- Bilibili UID: `404145357`
- Workspace: `/Users/mikusc/Documents/ArcaeaChannel`
- Bilibili cookie location: `/Users/mikusc/Documents/ArcaeaChannel/.bili_cookie` or `BILI_COOKIE`
- Rules file: `/Users/mikusc/Documents/ArcaeaChannel/arcaea_update_rules.json`
- Same-version post registry: `/Users/mikusc/Documents/ArcaeaChannel/arcaea_update_post_registry.json`
- Same-version append planner: `/Users/mikusc/Documents/ArcaeaChannel/scripts/plan_version_append.py`
- Production Tencent Channel: `韵律源点Arcaea`
- Production board: `更新情报`
- Production IDs for CLI calls: guild `63281101636793373`, board `685837281`
- Test Tencent Channel: `Lowiro（测试用）`
- Test board: `全部`
- Test IDs for CLI calls: guild `622466294048980363`, board `693453953`

Treat Tencent Channel IDs, cookies, and tokens as execution-only data. Do not echo cookies or tokens. Prefer names in user-facing summaries unless an ID is necessary for a command.

## Automation Publishing Policy

- Scheduled jobs may fetch Bilibili, prepare drafts, download images, generate same-version append plans, publish new eligible update posts, append eligible updates to existing same-version Tencent Channel posts, and run eligible post-promotion actions.
- Auto-publishing is restricted to the production Tencent Channel `韵律源点Arcaea` and production board `更新情报`.
- Auto-publishing is restricted to groups created by `prepare_arcaea_update_drafts.py` from unhandled official Bilibili dynamics for UID `404145357` using the workspace rules file.
- Auto-editing is restricted to `append_existing` actions produced by `plan_version_append.py` whose target is already present in `arcaea_update_post_registry.json`.
- Do not auto-publish or auto-edit if the manifest has no groups, an action has manual-review warnings, source images referenced by the manifest are missing, Tencent login is invalid, the target post detail cannot be fetched, the target post is not Markdown when a Markdown append is required, or the draft exceeds Tencent limits.
- Do not auto-delete, move, comment, reply, like, manage members, modify channels, or operate outside the configured update board.
- New update posts with source images must be Markdown long posts by default. Use plain-text long posts only when there are no source images or when a user explicitly asks for plain text.
- For multiple new-post candidates that belong to the same version/release window, merge them into one Markdown long post instead of publishing separate small posts.
- After every successful publish or edit, verify the board list, run the configured post-promotion workflow, update `arcaea_update_post_registry.json` when needed, and mark the source dynamics as handled.
- If an auto-publish or auto-edit step fails after the documented retry path, stop and report the exact pending action instead of trying alternate public actions.

## Tencent Channel Markdown Capability Notes

The current Tencent Channel workflow supports iterative Markdown posts:

- Long Markdown posts can place images at specific positions using `[(0,N)](@img)` placeholders and ordered `--image` arguments.
- For Arcaea update posts, place each text block next to its corresponding image: section text, then the matching `[(0,N)](@img)` placeholder, then a Markdown separator such as `---` before the next section.
- Do not duplicate the Tencent long-post title as a top-level Markdown H1 in the body. The post title already renders separately; start the Markdown body with an intro sentence or a `##` section.
- Existing Tencent Channel posts can be edited with `tencent-channel-cli feed alter-feed`.
- Markdown posts must be edited with `--markdown-content`; plain-text posts must use `--content` or `--content-file`.
- A plain-text Tencent post cannot be converted in place to Markdown with `alter-feed --markdown-content`. If a post was accidentally published in plain-text mode, publish and verify a Markdown replacement first, then delete the old plain-text post only after explicit user confirmation.
- Media replacement during edit should use `--clear-images` / `--clear-videos` before appending the replacement media.
- If only appending new images to the end of an existing Markdown post, keep original media in place and start new image placeholders from the current `image_count`.

## Prepare Drafts

Run the helper script from the workspace. It fetches recent dynamics, filters likely Arcaea update posts with the rules file, merges related items, downloads original images, and writes a manifest.

```bash
python3 /Users/mikusc/.codex/skills/arcaea-update-publisher/scripts/prepare_arcaea_update_drafts.py \
  --workspace /Users/mikusc/Documents/ArcaeaChannel \
  --pages 5 \
  --out-dir arcaea_update_drafts
```

Useful filters:

```bash
# Restrict to one version
python3 /Users/mikusc/.codex/skills/arcaea-update-publisher/scripts/prepare_arcaea_update_drafts.py \
  --workspace /Users/mikusc/Documents/ArcaeaChannel \
  --version v6.15 \
  --pages 5

# Only inspect dynamics after a date
python3 /Users/mikusc/.codex/skills/arcaea-update-publisher/scripts/prepare_arcaea_update_drafts.py \
  --workspace /Users/mikusc/Documents/ArcaeaChannel \
  --since 2026-04-25

# Force-include a special event keyword for the current run
python3 /Users/mikusc/.codex/skills/arcaea-update-publisher/scripts/prepare_arcaea_update_drafts.py \
  --workspace /Users/mikusc/Documents/ArcaeaChannel \
  --keyword "特殊联动名"
```

Important outputs:

- `manifest.json`: draft groups, titles, content files, image files, source IDs, source links, and source times.
- `*.txt`: long-post body drafts.
- `bili_raw_pages.json`: raw Bilibili API pages for inspection.

If the manifest has no groups, report that no matching new dynamics were found and do not publish anything.

## Same-Version Append Workflow

The target operating model is:

1. Daily 08:10 check prepares draft groups for unhandled dynamics.
2. Each group is matched by version against `arcaea_update_post_registry.json`.
3. If a matching version post exists, generate an append plan for that existing post.
4. If no matching version post exists, keep the group as a new-post candidate.
5. During scheduled runs, automatically execute eligible `alter-feed` or `publish-feed` actions, then verify the result and update local handled state.

Generate same-version append plans after `manifest.json` is created:

```bash
python3 /Users/mikusc/Documents/ArcaeaChannel/scripts/plan_version_append.py \
  --workspace /Users/mikusc/Documents/ArcaeaChannel \
  --manifest "/path/to/manifest.json" \
  --out-dir arcaea_update_append_plans
```

Important outputs:

- `append_plan.json`: groups marked as `append_existing` or `new_post`.
- `*.append.md`: Markdown blocks that can be appended to the current post body by the automation.

For `append_existing`, verify the registry target before editing:

- `version`
- `guild_id`
- `channel_id`
- `feed_id`
- `create_time`
- `image_count`
- `share_url`

Before editing, fetch the current post detail with `get-feed-detail`, read `content_richtext.source_markdown`, append the generated `*.append.md` block, then run `alter-feed`.

For an append to an existing Markdown post, use `alter-feed` with the full updated Markdown body and only the new images:

```bash
tencent-channel-cli feed alter-feed \
  --guild-id 63281101636793373 \
  --channel-id 685837281 \
  --feed-id "目标帖子ID" \
  --create-time "目标帖子create_time_raw" \
  --markdown-content "当前source_markdown + append block" \
  --image "/path/to/new-image1.jpg" \
  --image "/path/to/new-image2.jpg"
```

If old media must be deleted or reordered, use `--clear-images` and re-upload every image in final placeholder order. Keep the placeholder indexes aligned with the ordered `--image` list.

## Review And Merge

Review every group before publishing or editing:

- Sort source dynamics from old to new.
- Merge dynamics that describe the same update, version, or release window into one long Markdown post.
- Give every long post a clear title.
- Keep the title in the Tencent title field only; do not repeat it as `# title` in Markdown content.
- Remove Bilibili topic tags from long posts.
- Keep original image files whenever possible.
- If one source dynamic has no image, do not invent an image; only use images from related source dynamics.
- Keep each source image near the text it illustrates. Do not put all text in one block and all images at the end.
- Use `##` headings for sections and `---` between major sections when a merged post contains several update topics.
- Check that the version, title, date, topic, and image really refer to the same update being posted.
- Avoid naked URLs in Tencent post content; use inline Markdown links such as `[原动态 1](https://t.bilibili.com/...)` in Markdown posts, or `--link url|原动态` for plain-text posts.

When the script output needs manual adjustment, edit the generated `.txt` draft files and use the manifest paths as the source of truth for images and source links.

## Rules File

The rules file controls future-version behavior without code changes:

- `version_patterns`: regexes that detect versions such as `v6.15`.
- `date_patterns`: regexes that detect release or campaign dates.
- `update_keywords`: words that indicate an actual update, release, append, event, or maintenance notice.
- `subject_keywords`: reusable topics such as `Pack Append`, `World Extend`, `Memory Archive`, or `联动`.
- `include_keywords`: force-include terms that should be treated as update signals.
- `ignore_keywords`: terms to skip, such as merch or live-stream posts.
- `category_rules`: named buckets used for grouping and title generation.

When a future release uses unusual wording, prefer editing `/Users/mikusc/Documents/ArcaeaChannel/arcaea_update_rules.json` or passing `--keyword` for that run instead of editing the script.

## Publish And Edit

Use the `tencent-channel-community` skill for all Tencent Channel operations. Verify CLI availability and token state if the current session has not already done so.

For a new long post, prefer Markdown mode with interleaved source images. The Markdown body should not start with the same title as the Tencent title field:

```bash
tencent-channel-cli feed publish-feed \
  --guild-id 63281101636793373 \
  --channel-id 685837281 \
  --title "Arcaea v6.15 更新情报" \
  --markdown-content "Arcaea v6.15 将于 **2026年6月25日** 带来以下更新。\n\n## 主题一\n\n正文段落。\n\n[(0,0)](@img)\n\n---\n\n## 主题二\n\n正文段落。\n\n[(0,1)](@img)\n\n来源：[原动态 1](https://t.bilibili.com/源动态ID)" \
  --image "/path/to/image1.jpg" \
  --image "/path/to/image2.jpg"
```

Use multiple inline source links when a merged Markdown post has multiple source dynamics. Use multiple `--image` flags for all selected images, in the same order as the `[(0,N)](@img)` placeholders.

Use plain text only for image-free posts or when explicitly requested:

```bash
tencent-channel-cli feed publish-feed \
  --guild-id 63281101636793373 \
  --channel-id 685837281 \
  --title "帖子标题" \
  --content-file "/path/to/draft.txt" \
  --link "https://t.bilibili.com/源动态ID|原动态"
```

After publishing or editing:

1. Capture and report the Tencent Channel share link.
2. Verify the latest board list with `get-channel-timeline-feeds`.
3. Fetch the post detail with `get-feed-detail` and verify `is_markdown=true` / `sourceMarkdown` or `source_markdown` is present for Markdown posts, and that `image_count` matches the placeholder count.
4. For a new version post, add or update its entry in `arcaea_update_post_registry.json`, including `publish_mode: "markdown"`, `is_markdown: true`, `image_count`, `content_file`, fallback image paths if used, and any replaced/deleted plain-text post metadata.
5. For an edited existing version post, update its `image_count`, `source_ids`, `updated_at`, and `share_url` if changed.
6. Run the post-promotion workflow below.
7. Mark handled source IDs:

```bash
python3 /Users/mikusc/.codex/skills/arcaea-update-publisher/scripts/prepare_arcaea_update_drafts.py \
  --workspace /Users/mikusc/Documents/ArcaeaChannel \
  --mark-handled "/path/to/manifest.json"
```

## Post Promotion

After a successful eligible `publish-feed` or `alter-feed`, automatically promote the affected Tencent Channel post:

1. Fetch the post detail with `get-feed-detail` and keep `feed_id`, `author_id`, `create_time_raw`, `guild_id`, `channel_id`, `share_url`, and `is_markdown`.
2. Set the post as essence:

```bash
tencent-channel-cli feed set-feed-essence \
  --feed-id "目标帖子ID" \
  --action 1
```

3. Push the essence notification only when the registry does not already show that this post has been pushed:

```bash
tencent-channel-cli feed push-essence-feed \
  --feed-id "目标帖子ID"
```

`push-essence-feed` requires the post to be essence first, is limited to 3 pushes per day, and can only be used once per post. If Tencent reports that the post was already pushed or the daily quota is exhausted, record the skipped status in `arcaea_update_post_registry.json` and do not retry the same push in the same automation run.

4. Pin the post:

```bash
tencent-channel-cli feed top-feed \
  --feed-id "目标帖子ID" \
  --user-id "帖子作者author_id" \
  --create-time "帖子create_time_raw" \
  --guild-id 63281101636793373 \
  --action 1 \
  --top-type 1
```

For `top-feed`, `user-id` must come from `get-feed-detail` as `author_id`; do not guess it. If top/promotion permissions are missing, leave the published or edited post in place, record the promotion failure, and continue with registry/handled-state updates.

## Automation Guidance

For recurring checks, create an automation that runs the draft preparation workflow, generates append plans, and automatically publishes or edits eligible update posts in the configured production board.

Default daily check time: `08:10 Asia/Shanghai`. For known release periods, increase `--pages` or add `--version` if the target version is already known.

For the same-version update model, the daily automation should:

- run `prepare_arcaea_update_drafts.py` for unhandled recent dynamics;
- when groups exist, run `plan_version_append.py` against the generated manifest;
- execute eligible `append_existing` actions by fetching the target Markdown source, appending the generated block, and running `alter-feed`;
- execute eligible `new_post` actions with `publish-feed` as Markdown long posts when source images exist, using section text followed by matching `[(0,N)](@img)` placeholders;
- after successful publish/edit, run `set-feed-essence`, `push-essence-feed` when not already pushed, and `top-feed`;
- report target post title/share URL, append or new-post title, image count, source links, verification result, promotion result, registry update, and handled-state update;
- leave any blocked or manual-review action unpublished and report the exact reason.

## Failure Handling

- Bilibili `412` or security-control errors: refresh `.bili_cookie`, reduce request frequency, and retry later.
- Missing or expired cookie: ask the user to refresh the Bilibili cookie; never print the old value.
- Tencent auth failure: ask the user to re-run token setup as directed by `tencent-channel-community`.
- Tencent rate limit: follow `tencent-channel-community` retry rules.
- Image upload may fail even when Markdown syntax is correct. A common failure mode is Tencent image slice upload EOF / `retcode=-1` during `publish-feed` or `alter-feed`; do not treat this as a Markdown placeholder failure.
- Image upload retry strategy: retry once with the same image set if it looks transient; if it fails again, replace or compress the largest image first; keep image order stable because `[(0,N)](@img)` depends on ordered `--image` arguments.
- Image upload fails or looks compressed: retry with original image first. If needed, create fallback copies with `sips -Z 1600 --setProperty format jpeg --setProperty formatOptions 92 input -o output.jpg`, then `1280`, then `960` when Tencent slice upload still returns EOF. Keep image order stable.
- The same upload retry rules apply to `alter-feed` when replacing or appending images.
- If a Markdown post was created without bound images, do not treat `sourceMarkdown` alone as success. Verify `image_count` and the board list images. If needed, edit the Markdown post with `--clear-images` and compressed local images until the images bind.
- If correcting an already public plain-text post, never delete it before the Markdown replacement has been published, verified as Markdown, and verified with the expected images. Delete the old post only after explicit user confirmation, then update registry `replaced_post` metadata.
- Draft exceeds Tencent limits: stop, explain the limit, and leave the split decision for a manual follow-up; do not auto-publish split posts.
