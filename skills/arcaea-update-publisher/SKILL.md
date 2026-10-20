---
name: arcaea-update-publisher
description: Collect official Arcaea Bilibili dynamics, classify and merge update topics, create validated interleaved Markdown drafts, plan same-version Tencent Channel updates, and record only verified publications. Use for “更新情报”; use arcaea-pack-intro-publisher for 曲包介绍.
metadata: {"openclaw":{"emoji":"🎵"}}
---

# Arcaea Update Publisher

Prepare version-aware Arcaea update intelligence for Tencent Channel `韵律源点Arcaea / 更新情报`.

Actual Tencent reads/writes must also follow `tencent-channel-community`. Draft preparation is the default; publishing, editing, and promotion require either explicit authorization in the current interaction or an already-authorized scheduled automation whose target and policy match this skill.

## Workspace configuration

Run command examples from this skill directory (resolve it from the loaded `SKILL.md`, not a fixed installation path). Set `ARCAEA_WORKSPACE` to a separate data directory and supply the intended Tencent IDs. No production target IDs are bundled.

- Official Bilibili UID: `404145357`
- Workspace: `ARCAEA_WORKSPACE` (an absolute path chosen by the user)
- Cookie: workspace `.bili_cookie` or `BILI_COOKIE`; never display it
- Rules: workspace `arcaea_update_rules.json`
- State: workspace `.arcaea_update_publisher_state.json`
- Registry: workspace `arcaea_update_post_registry.json`
- Production target: `韵律源点Arcaea / 更新情报`
- Target IDs: user-configured `TENCENT_GUILD_ID` and `TENCENT_CHANNEL_ID`; resolve the intended board before use

Treat IDs as execution-only data and credentials as secret. Prefer channel/board names in user-facing reports.

## Modes and authority

1. **Prepare** — fetch or replay Bilibili, classify, download/reuse images, and create validated Markdown. No Tencent mutation.
2. **Plan** — match each draft to a registered same-version post and prepare an append/new-post plan. No Tencent mutation.
3. **Publish/Edit** — execute only an eligible plan after the required authorization and Tencent preflight.
4. **Record** — only after timeline and post-detail verification, update registry/state for exactly one group.
5. **Promote** — optional, independently retryable follow-up. Promotion failure never changes a verified publication back to failed.

Never use the removed legacy `--mark-handled` path. `record_arcaea_publish.py --verified` is the only supported handled-state transition.

## Prepare

Live fetch:

```bash
python3 scripts/prepare_arcaea_update_drafts.py \
  --workspace "$ARCAEA_WORKSPACE" \
  --pages 5 \
  --out-dir arcaea_update_drafts
```

Deterministic replay:

```bash
python3 scripts/prepare_arcaea_update_drafts.py \
  --workspace "$ARCAEA_WORKSPACE" \
  --raw-file /absolute/path/bili_raw_pages.json \
  --reuse-image-dir /absolute/path/prior-drafts \
  --out-dir arcaea_update_replay
```

Useful filters: `--version v6.15`, `--since 2026-04-25`, repeatable `--keyword`, repeatable `--ignore-keyword`, and `--include-handled` for audit/replay only.

Outputs:

- `manifest.json` with `schema_version=2`, per-group validation, source/image mapping, hashes, warnings, and manual-review state
- `*.article.md` ready for `--markdown-content`
- legacy `*.txt` text-only bodies for inspection, not the publishing source
- ordered image files and `bili_raw_pages.json`

## Plan

```bash
python3 scripts/plan_version_append.py \
  --workspace "$ARCAEA_WORKSPACE" \
  --manifest /absolute/path/manifest.json \
  --out-dir arcaea_update_append_plans
```

The planner preserves text/image interleaving and cumulatively offsets placeholders when several groups target the same existing post. Execute same-target actions in plan order; after any skipped or failed action, rebuild the plan before continuing. Exact version matches may be eligible automatically; date-only or multiple matches must remain manual review.

For a new version with several groups, only the first group can be a new post. Later groups are blocked as `replan_after_publish`: verify and record the first post, prepare the remaining unhandled sources, then rebuild the plan. Appends exceeding 50 total images are also blocked; manual approval does not override these errors.

## Hard publish gates

Do not publish or edit unless all apply:

- group/action has no `errors`
- `validation_passed=true`
- `eligible_for_publish=true`, or the user explicitly approves the reported manual-review reason
- content and image hashes still match the manifest
- source author UID is the configured official UID when the field is available
- all image files exist; placeholder indexes are continuous and match ordered images
- body is Markdown, has no top-level H1 duplicate, and stays within Tencent long-post limits
- exact production target is confirmed
- current Tencent schema and login status are checked
- `publish-feed` or `alter-feed` succeeds in explicit CLI `--dry-run` before the real call

Never auto-delete, move, comment, reply, like, manage members/channels, or publish outside the configured board. Do not split over-limit content without user approval.

For detailed Tencent commands, verification, recording, promotion separation, and bounded upload recovery, read [references/publish-workflow.md](references/publish-workflow.md).

For grouping, title, Markdown, image, and source rules, read [references/editorial-rules.md](references/editorial-rules.md).

## Verification and recording

After a real publish/edit:

1. Verify the board timeline contains the expected post.
2. Fetch post detail and verify title, Markdown state, source Markdown, image count, and share URL.
3. Run `record_arcaea_publish.py` for exactly one group with `--verified`; add `--manual-review-approved` only when that review actually occurred.
4. Attempt promotion separately if the authorized policy includes it; record promotion status without altering publication status.

## Failure boundaries

- Bilibili `412`: stop, refresh cookie outside logs, or replay cached pages.
- Tencent `153`: follow the Tencent skill's one delayed retry.
- Slice-upload EOF: retry the same command once; then use the bounded localhost proxy or ordered image downscaling described in the publish reference. Do not reorder images.
- Markdown created without bound images is not success; verify actual `image_count`.
- A public plain-text post must not be deleted until a verified Markdown replacement exists and the user explicitly confirms deletion.
