#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""获取 Arcaea B站动态 - 修复编码问题"""

import json
import urllib.request
import urllib.parse
import sys

# 配置
CONFIG_PATH = r"C:\Users\85170\.qclaw\workspace\bilibili-monitor-config.json"
UID = "404145357"
API_URL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_dynamics(offset=""):
    config = load_config()
    cookies = config.get("arcaea", {}).get("cookies", {})
    
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    
    url = f"{API_URL}?host_mid={UID}&offset={offset}&timezone=-8&features=itemOpusStyle"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    req.add_header("Referer", f"https://space.bilibili.com/{UID}/dynamic")
    req.add_header("Cookie", cookie_str)
    req.add_header("Accept", "application/json")
    
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))

def parse_items(data):
    items = data.get("data", {}).get("items", [])
    result = []
    
    for item in items:
        try:
            modules = item.get("modules", {})
            author = modules.get("module_author", {})
            dynamic = modules.get("module_dynamic", {})
            major = dynamic.get("major", {})
            opus = major.get("opus", {})
            
            # 获取文字
            summary = opus.get("summary", {})
            text = summary.get("text", "") or dynamic.get("desc", {}).get("text", "")
            
            # 获取配图
            pics = [p.get("url", "") for p in opus.get("pics", [])]
            
            result.append({
                "id": item.get("id_str", ""),
                "type": item.get("type", ""),
                "pub_ts": author.get("pub_ts", 0),
                "pub_time": author.get("pub_time", ""),
                "text": text,
                "pics": pics,
                "url": f"https://www.bilibili.com/opus/{item.get('id_str', '')}"
            })
        except Exception as e:
            print(f"解析错误: {e}", file=sys.stderr)
    
    return result

def main():
    print("=== Arcaea B站动态获取 ===\n", flush=True)
    
    # 获取第一页
    data = fetch_dynamics()
    items = parse_items(data)
    
    print(f"获取到 {len(items)} 条动态\n", flush=True)
    
    # 显示所有动态
    for i, item in enumerate(items, 1):
        print(f"--- 动态 {i} ---")
        print(f"ID: {item['id']}")
        print(f"时间: {item['pub_time']} (ts: {item['pub_ts']})")
        print(f"类型: {item['type']}")
        print(f"内容: {item['text'][:200]}...")
        print(f"配图: {len(item['pics'])} 张")
        if item['pics']:
            print(f"首图: {item['pics'][0]}")
        print(f"链接: {item['url']}")
        print()
    
    # 检查是否有更多
    has_more = data.get("data", {}).get("has_more", False)
    next_offset = data.get("data", {}).get("offset", "")
    
    print(f"has_more: {has_more}")
    print(f"next_offset: {next_offset}")
    
    # 保存到文件
    with open(r"C:\Users\85170\.qclaw\workspace\arcaea-dynamics.json", "w", encoding="utf-8") as f:
        json.dump({"items": items, "has_more": has_more, "offset": next_offset}, f, ensure_ascii=False, indent=2)
    
    print("\n已保存到 arcaea-dynamics.json")

if __name__ == "__main__":
    main()
