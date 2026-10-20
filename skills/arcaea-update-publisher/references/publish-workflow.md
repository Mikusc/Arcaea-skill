# Arcaea 更新情报腾讯频道发布流程

只有在当前请求或既有 scheduled automation 明确授权发布/更新时读取和执行。

## 1. Preflight

1. 按 `tencent-channel-community` 做当日版本检查，并读取实时 schema：

```bash
tencent-channel-cli version
tencent-channel-cli login status --json
tencent-channel-cli schema feed.publish-feed --json
tencent-channel-cli schema feed.alter-feed --json
```

2. 确认目标仍是 `韵律源点Arcaea / 更新情报`。
3. 读取 manifest 和 append plan，检查 hard gates、内容 hash、图片 hash 与重复帖子。
4. 同版本帖子已存在时只能走 `alter-feed`，不得再发第二篇。

## 2. Dry-run

必须使用 CLI flag `--dry-run`；不要把 `dry_run` 仅放进 stdin JSON。

新帖：

```bash
draft_markdown=$(< /absolute/path/group.article.md)
tencent-channel-cli feed publish-feed \
  --guild-id "$TENCENT_GUILD_ID" \
  --channel-id "$TENCENT_CHANNEL_ID" \
  --feed-type 2 \
  --title "manifest 标题" \
  --markdown-content "$draft_markdown" \
  --image /absolute/path/first.jpg \
  --image /absolute/path/second.jpg \
  --dry-run --json
```

已有帖：先回读 `content_richtext.source_markdown`，拼接 planner 生成的 `.append.md`，再按实时 schema 组装 `alter-feed --dry-run`。同一目标有多个 action 时必须按 `append_plan.json` 顺序执行，并核对 `depends_on_group_keys`、`placeholder_offset` 和 `expected_image_count_after`；任一前序 action 被跳过或失败后必须重新回读并生成 plan。只追加新图时保留旧媒体；替换或重排时使用 `--clear-images` 并按最终索引上传全部图片。

Dry-run 必须返回 `dry_run=true` 且标题、目标、Markdown、图片顺序完整。正式命令只移除 `--dry-run`，其他参数不变；一次只执行一个正式写入。

## 3. 不确定结果与上传 EOF

- 发布返回不明确时，先查同标题搜索、版块时间线和帖子详情；确认未创建/未更新前不得重试。
- `sliceupload EOF` 仅表示上传层失败，不等于 Markdown 失败。
- 原图集最多重试一次；仍失败时生成最长边 1600 px 的高质量 JPEG 副本并保持顺序。
- 随机 EOF 仍持续时，可临时使用本 Skill 的 POST-only localhost proxy：

```bash
python3 scripts/retrying_http_proxy.py --port 18765
```

仅对本次发布设置代理：

```bash
HTTP_PROXY=http://127.0.0.1:18765 NO_PROXY= tencent-channel-cli feed publish-feed ...
```

命令结束后停止代理。代理最多 8 次上游网络重试；仍失败则停止，不做无限循环。

## 4. 回读验证

必须同时验证：

- `get-channel-timeline-feeds` 中目标帖子位于正确版块，标题、时间和图片列表符合计划
- `get-feed-detail` 中 `feed_type=2`、`is_markdown=true`、`source_markdown` 存在
- 实际 `image_count` 等于 group/plan
- source Markdown 的占位符、来源链接和预期内容存在
- share URL 可取得

验证完成后才可记录：

```bash
python3 scripts/record_arcaea_publish.py \
  --workspace "$ARCAEA_WORKSPACE" \
  --manifest /absolute/path/manifest.json \
  --group-key "manifest group key" \
  --operation publish \
  --guild-id "内部频道 ID" \
  --channel-id "内部版块 ID" \
  --feed-id "回读帖子 ID" \
  --create-time "回读 create_time_raw" \
  --share-url "回读分享链接" \
  --image-count 2 \
  --is-markdown --verified
```

人工复核组需额外传 `--manual-review-approved`。追加现有帖子使用 `--operation edit`，传入原帖的 ID 和 `create_time_raw`，`--image-count` 必须是回读到的**整帖图片总数**（原有数量 + 本次新增数量）。记录脚本会与当前 registry 的目标和原有数量交叉核对；不支持把整帖替换伪装为追加。顺序执行并记录每个 action 后，下一 action 才能使用更新后的数量；已记录的来源再次出现会停止，需先回读排查。

## 5. Promotion 是独立事务

发布验证和 recorder 成功后，才按已授权策略尝试 `set-feed-essence`、`push-essence-feed`、`top-feed`。精华推送每日最多 3 次且每帖一次；置顶作者 ID 必须从详情回读。

任何 promotion 审核、权限或配额失败都只记录为 pending/failed，不回滚帖子，不撤销 handled state，也不自动删除或重复发布。
