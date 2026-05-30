# Arcaea Codex Skills

This repository mirrors the Arcaea-related Codex skills used locally on
`/Users/mikusc/.codex/skills`.

## Active Skills

- `skills/arcaea-update-publisher`
  - Collects official Arcaea Bilibili dynamics.
  - Groups update items by version/topic.
  - Prepares Tencent Channel Markdown drafts with source images.
  - Supports eligible automated publish/append/promotion workflows for
    `韵律源点Arcaea / 更新情报`.
- `skills/arcaea-pack-intro-publisher`
  - Prepares long-form pack introduction posts for
    `韵律源点Arcaea / 曲包信息`.
  - Uses official Bilibili covers and Arcaea中文Wiki references.
  - Keeps actual Tencent Channel publish/edit actions confirmation-gated.

## Legacy

- `legacy/arcaea-update-compiler`
  - Original single-skill snapshot from the first version of this repository.

## Sync Notes

Sensitive runtime data is intentionally excluded from this repository:

- Bilibili cookies
- Tencent tokens or login state
- `.env` files
- Python bytecode/cache files

