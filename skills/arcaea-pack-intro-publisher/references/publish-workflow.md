# Arcaea 曲包介绍腾讯频道发布流程

仅在用户当前交互明确确认当前 publish plan 后执行。

## 1. Plan 与重复检查

读取 plan 并再次核对：

- title、target、draft hash、image hashes 未变化
- `validation_passed=true` 且无 errors
- 所有 manual-review reason 已展示并明确批准
- 图片角色、顺序、尺寸和占位符一致
- Bilibili/Wiki 来源链接完整

然后用完整标题执行 `search-guild-feeds`，并读取 `曲包信息` 最新时间线。已有同标题时停止新帖流程；需要更新则回读原帖并走 `alter-feed`。

## 2. Tencent preflight 与 dry-run

```bash
tencent-channel-cli version
tencent-channel-cli login status --json
tencent-channel-cli schema feed.publish-feed --json
tencent-channel-cli schema feed.alter-feed --json
```

必须使用 CLI flag `--dry-run`。不要只在 stdin JSON 中写 `dry_run`。

```bash
draft_markdown=$(< /absolute/path/publish.md)
tencent-channel-cli feed publish-feed \
  --guild-id "$TENCENT_GUILD_ID" \
  --channel-id "$TENCENT_CHANNEL_ID" \
  --feed-type 2 \
  --title "<Pack Name>曲包介绍" \
  --markdown-content "$draft_markdown" \
  --image /absolute/path/official-cover.jpg \
  --image /absolute/path/song-1.jpg \
  --image /absolute/path/partner.jpg \
  --link "https://www.bilibili.com/video/<BVID>|官方预览" \
  --dry-run --json
```

Dry-run 返回 `dry_run=true` 且参数与 plan 一致后，才可移除 `--dry-run` 执行一次正式发布。

编辑现有 Markdown 帖时，从 `get-feed-detail` 取得 `create_time_raw` 和当前 Markdown。按实时 schema 组装 `alter-feed`；重排/替换图片时使用 `--clear-images` 并按最终顺序上传全部图片。不要依赖陈旧示例猜测 flags。

## 3. 上传失败边界

- 返回不明确时先查同标题、版块时间线和帖子详情；确认没有写入前不得重试。
- `sliceupload EOF` 时原图集只重试一次。
- 仍失败可生成最长边 1600 px 的高质量 JPEG 副本，保持占位符和图片顺序。
- 随机 EOF 持续时可临时启动本 Skill 的 localhost proxy：

```bash
python3 scripts/retrying_http_proxy.py --port 18765
```

仅对本次写入设置 `HTTP_PROXY=http://127.0.0.1:18765 NO_PROXY=`，完成后停止代理。代理达到有限重试上限后停止，不循环发布。

## 4. 回读验证

正式写入后必须检查：

1. `get-channel-timeline-feeds`：目标帖位于 `曲包信息`，标题、作者、时间和图片列表正确。
2. `get-feed-detail`：
   - `feed_type=2`
   - `is_markdown=true`
   - `content_richtext.source_markdown` 存在
   - 图片数量等于 plan `image_count`
   - 占位符、关键正文和图片角色顺序符合 plan
   - share URL 可取得

只有两项都通过，才能记录：

```bash
python3 scripts/record_pack_publish.py \
  --workspace "$ARCAEA_WORKSPACE" \
  --plan /absolute/path/publish-plan.json \
  --operation publish \
  --guild-id "内部频道 ID" \
  --channel-id "内部版块 ID" \
  --feed-id "回读帖子 ID" \
  --create-time "回读 create_time_raw" \
  --share-url "回读分享链接" \
  --image-count 7 \
  --is-markdown --verified
```

plan 含人工复核理由时额外传 `--manual-review-approved`。更新已有帖使用 `--operation edit`，必要时用 `--registry-key` 保持原 registry key。

## 5. 用户侧结果

报告标题、版块、正文范围、图片数量与顺序验证、来源、local draft/plan 路径和 `<https://pd.qq.com/s/...>` 分享链接。除非用户另行要求，不执行 promotion、评论、点赞、移动或删除。
