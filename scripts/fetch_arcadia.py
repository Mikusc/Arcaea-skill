#!/usr/bin/env python3
"""
Arcaea 更新情报生成器
自动抓取 B站 Arcaea 官号动态并整合
"""

import json
import urllib.request
import urllib.parse
import re
from datetime import datetime
from typing import Dict, List, Optional

CONFIG_PATH = r"C:\Users\85170\.qclaw\workspace\bilibili-monitor-config.json"
BILIBILI_UID = "404145357"
API_URL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"

def load_config():
    """加载配置文件"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_dynamics(offset: str = "", limit: int = 20) -> dict:
    """获取动态"""
    config = load_config()
    cookies = config.get("arcaea", {}).get("cookies", {})
    
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    
    url = f"{API_URL}?host_mid={BILIBILI_UID}&offset={offset}&timezone=-8&features=itemOpusStyle"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    req.add_header("Referer", f"https://space.bilibili.com/{BILIBILI_UID}/dynamic")
    req.add_header("Cookie", cookie_str)
    
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))

def parse_dynamics(data: dict, target_date: str = "") -> List[dict]:
    """解析动态数据"""
    items = data.get("data", {}).get("items", [])
    parsed = []
    
    for item in items:
        try:
            modules = item.get("modules", {})
            author = modules.get("module_author", {})
            dynamic = modules.get("module_dynamic", {})
            
            # 获取配图
            pics = []
            major = dynamic.get("major", {})
            opus = major.get("opus", {})
            for pic in opus.get("pics", []):
                pics.append(pic.get("url", ""))
            
            # 获取文字内容
            summary = opus.get("summary", {})
            text = summary.get("text", "")
            
            parsed.append({
                "id": item.get("id_str", ""),
                "pub_ts": author.get("pub_ts", 0),
                "pub_time": author.get("pub_time", ""),
                "text": text,
                "pics": pics,
                "jump_url": f"https://www.bilibili.com/opus/{item.get('id_str', '')}"
            })
        except Exception as e:
            print(f"解析动态失败: {e}")
            continue
    
    return parsed

def group_by_version(dynamics: List[dict], version_date: str) -> dict:
    """按版本分组动态"""
    groups = {}
    
    for d in dynamics:
        text = d.get("text", "")
        pub_ts = d.get("pub_ts", 0)
        
        # 查找日期关键词
        date_match = re.search(r'(\d+)月(\d+)日', text)
        if date_match:
            found_date = f"{date_match.group(1)}月{date_match.group(2)}日"
        else:
            found_date = version_date
        
        if found_date not in groups:
            groups[found_date] = []
        groups[found_date].append(d)
    
    return groups

def format_update_report(dynamics: List[dict], version: str) -> str:
    """生成更新情报"""
    output = f"「韵律源点 Arcaea {version} 版本更新情报」\n\n"
    
    for d in dynamics:
        output += f"📌 {d['text'][:100]}\n"
        for pic in d.get('pics', []):
            output += f"![配图]({pic})\n"
        output += f"[链接]({d.get('jump_url', '')})\n\n---\n\n"
    
    output += f"🔗 原文链接：https://space.bilibili.com/{BILIBILI_UID}/dynamic\n\n💬 \n"
    
    return output

if __name__ == "__main__":
    print("正在获取 Arcaea 动态...")
    data = fetch_dynamics()
    dynamics = parse_dynamics(data)
    
    print(f"获取到 {len(dynamics)} 条动态")
    
    # 示例：按3月9日版本分组
    groups = group_by_version(dynamics, "3月9日")
    
    for date, items in groups.items():
        print(f"\n=== {date} ===")
        print(format_update_report(items, date))
