---
name: arcaea-update-compiler
description: 韵律源点 Arcaea 更新情报生成器。当用户要求整合 B站 Arcaea 官号动态、生成版本更新情报时使用。自动抓取指定日期范围的动态，按版本分组，生成带配图的完整更新情报。支持任意版本日期的信息整合。配置文件路径：C:\Users\85170\.qclaw\workspace\bilibili-monitor-config.json
---

# Arcaea 更新情报生成器

## 核心功能

将 B站 Arcaea 官号（UID: 404145357）的多条动态整合为一份完整的版本更新情报。

## 使用流程

### 1. 抓取动态

使用 curl 获取 B站动态 API：

```bash
curl.exe -s "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?host_mid=404145357&offset=0&timezone=-8&features=itemOpusStyle" -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" -H "Referer: https://space.bilibili.com/404145357/dynamic" -b "SESSDATA=<从配置文件读取>; buvid3=<从配置文件读取>"
```

### 2. 读取 Cookie

从 `C:\Users\85170\.qclaw\workspace\bilibili-monitor-config.json` 读取 `arcaea.cookies` 下的 SESSDATA 和 buvid3。

### 3. 解析动态数据

动态 JSON 中关键字段：
- `items[].id_str` - 动态 ID
- `items[].modules.module_author.pub_ts` - 发布时间戳
- `items[].modules.module_author.pub_time` - 格式化时间（如"03月09日"）
- `items[].modules.module_dynamic.major.opus.summary.text` - 动态文字内容
- `items[].modules.module_dynamic.major.opus.pics[].url` - 配图链接

### 4. 版本分组规则

按以下规则将动态归入同一版本：

| 场景 | 处理方式 |
|------|----------|
| 动态明确提到"x月x号更新" | 以此日期为版本标识 |
| 动态没提日期 | 查找同批次其他动态，借用其日期 |
| 判断条件 | 无日期动态的发布时间 < 更新日期 = 属于同一版本 |

### 5. 输出格式

```
「韵律源点 Arcaea {版本日期} {版本号} 版本更新情报」

📌 {分点标题}
{内容描述}
![配图](图片链接)

---

📌 {分点标题}
**「曲名」** by 作者
{内容描述}

---

🔗 原文链接：https://space.bilibili.com/404145357/dynamic

💬 [管理员点评]
```

## 排版规范

1. **标题**：无 emoji，`「韵律源点 Arcaea 日期 版本 更新情报」`
2. **分点**：用 `📌` 开头，加粗标题
3. **曲名**：`**「曲名」**` 格式
4. **配图**：每个分点配对应动态的图片
5. **原文链接**：只放官号主页链接，不逐条列出
6. **点评**：留空给管理员

## 配图对应关系

| 动态内容 | 配图来源 |
|----------|----------|
| 版本更新 | v6.13 更新宣传图（4张） |
| 九周年庆典曲目 | Desertrealm 宣传图 |
| 限时免费曲 | Cryogenic 宣传图 |
| World Extend 新曲 | 3rd Avenue 宣传图 |
| 世界模式新曲 | Vallista 宣传图 |
| 回忆档案馆 | GOODRAGE 宣传图 |
| 周年优惠 | 九周年优惠图（2张） |
| 角色回归 | 迷尔回归图 |
| Beyond 难度 | Axium Divergence 图 |
| 功能更新 | 个人档案更新图 |
| 贺图 | 单独帖子，不纳入更新情报 |

## 贺图收集（单独处理）

贺图类动态（画师 xxx）不纳入更新情报，单独生成贺图合集：

```
「韵律源点 Arcaea {日期} 贺图合集」

🎨 贺图 X
画师：{作者名}
![配图](链接)
```

## 注意事项

- 配图必须严格对应各自动态的内容，不能混淆
- 分页获取：使用 `offset` 参数继续获取更早动态
- API 返回 412 错误需换 Cookie 重试
