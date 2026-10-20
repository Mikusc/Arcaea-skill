---
name: arcaea-pack-intro-publisher
description: Research, draft, validate, publish, or update factual Arcaea 曲包介绍 Markdown long posts for Tencent Channel “曲包信息”, using official Bilibili covers, source-tracked song/partner facts, ordered images, hash-bound publish plans, explicit confirmation, and verified recording. Not for short update intelligence.
metadata: {"openclaw":{"emoji":"🎼"}}
---

# Arcaea Pack Intro Publisher

Create factual 曲包介绍 posts for `韵律源点Arcaea / 曲包信息`. Current/future Bilibili update dynamics belong to `arcaea-update-publisher`.

Actual Tencent operations must also follow `tencent-channel-community`.

## Workspace configuration

Run command examples from this skill directory (resolve it from the loaded `SKILL.md`, not a fixed installation path). Set `ARCAEA_WORKSPACE` to a separate data directory and supply the intended Tencent IDs. No production target IDs are bundled.

- Workspace: `ARCAEA_WORKSPACE` (an absolute path chosen by the user)
- Draft root: workspace `pack_intro_drafts/`
- Asset root: workspace `pack_intro_assets/`
- Current sequence: `pack_intro_drafts/main_story_act2/00-posting-order.md`
- Official Bilibili UID: `404145357`
- Production target: `韵律源点Arcaea / 曲包信息`
- Target IDs: user-configured `TENCENT_GUILD_ID` and `TENCENT_CHANNEL_ID`; resolve the intended board before use
- Registry: workspace `pack_intro_post_registry.json`

Tencent IDs and credentials are execution-only data. Never display cookies or tokens.

## Authority boundary

- Source lookup, downloading, conversion, drafting, and local validation are allowed without additional confirmation.
- Never publish or edit without explicit confirmation in the current interaction.
- The confirmation must refer to the current hash-bound publish plan. If draft, images, order, title, target, or sources change, rebuild the plan and ask again.
- Never delete, move, comment, like, pin, push, or promote unless the user separately requests it.
- Any legacy workspace batch output is candidate material only. Do not use a legacy `--publish` path; rebuild and validate a v2 publish plan first.

## Source and content requirements

- First image: current official `韵律源点Arcaea` Bilibili preview cover whenever one exists.
- Then one ordered image per song; add a partner/key-character image when central to unlock or story progression.
- Use individual Arcaea中文Wiki pages for factual song, pack, unlock, partner, and mechanic fields. `wiki.arcaea.cn` and `arcwiki.mcd.blue` may be protected by Anubis; use an interactive browser or already obtained source material rather than bypassing protection.
- Treat wiki 攻略 as optional play guidance, not objective fact. Do not quote long passages.
- Keep prose factual; omit absent fields instead of writing source-absence statements.
- New drafts should keep the Tencent title out of the Markdown body: no duplicate top-level H1.

For detailed sourcing, writing structure, image roles, progression rules, and current sequence, read [references/writing-and-sources.md](references/writing-and-sources.md).

## Freeze a publish plan

After the draft and exact image order are ready:

```bash
python3 scripts/build_pack_publish_plan.py \
  --title "<Pack Name>曲包介绍" \
  --guild-id "$TENCENT_GUILD_ID" \
  --channel-id "$TENCENT_CHANNEL_ID" \
  --draft /absolute/path/publish.md \
  --image /absolute/path/official-cover.jpg \
  --image-role official_bilibili_cover \
  --image /absolute/path/song-1-512.png \
  --image-role song \
  --image /absolute/path/partner-600.png \
  --image-role partner \
  --source "https://www.bilibili.com/video/<BVID>|官方预览" \
  --source "https://wiki.arcaea.cn/<page>|Arcaea中文Wiki" \
  --partner-required
```

The plan records draft/image SHA-256, dimensions, roles, sources, placeholder order, errors, warnings, and the exact confirmation phrase.

## Hard publish gates

Do not ask for confirmation or publish until:

- `validation_passed=true`
- no `errors`
- `draft_ready=true`, or every reported manual-review reason is explicitly reviewed
- draft and image hashes still match
- placeholders are exactly `0..image_count-1`
- body is at most 10,000 characters and images at most 50
- first image/source are verified as the intended official Bilibili preview, or the fallback is explicitly approved
- song and partner image roles/order match their article sections
- source links and target are present
- no duplicate post exists
- Tencent schema/login checks and an explicit CLI `--dry-run` pass

Before publishing, show title, target, concise body scope, image count/order/roles, source links, validation/manual-review result, plan path, and confirmation phrase.

For dry-run, publish/edit commands, upload recovery, post-detail verification, and verified registry recording, read [references/publish-workflow.md](references/publish-workflow.md).

## Verification

After a confirmed write:

1. Verify the correct board timeline entry.
2. Verify post detail: title, `feed_type=2`, Markdown state/source, image count/order, expected phrase, and share URL.
3. Run `record_pack_publish.py --verified`; add `--manual-review-approved` only if those reasons were actually reviewed.
4. Report title, verification result, image count/order, share URL in angle brackets, plan path, and local draft path.

Do not treat an API success response alone as completion, and do not expose internal IDs in the user-facing result.
