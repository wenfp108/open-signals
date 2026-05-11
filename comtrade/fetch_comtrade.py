#!/usr/bin/env python3
"""
UN COMTRADE 数据采集器
采集中国主要大宗商品进口数据（粮食、能源、矿产）
数据推送到 Central-Bank/data/comtrade/
"""

import json, os, time, sys
from datetime import datetime, timedelta
from pathlib import Path
import urllib.request, urllib.error
import subprocess

# UN COMTRADE Public API (免费，无需 key)
API_BASE = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"

# GitHub
GITHUB_TOKEN = os.environ.get("GH_PAT", "")
REPO = "wenfp108/Central-Bank"

# 中国 reporter code
CHINA = 156

# 关注商品 HS 编码
COMMODITIES = {
    "1201": {"name": "大豆", "name_en": "Soybeans", "sector": "粮食"},
    "1005": {"name": "玉米", "name_en": "Corn/Maize", "sector": "粮食"},
    "1001": {"name": "小麦", "name_en": "Wheat", "sector": "粮食"},
    "1006": {"name": "稻米", "name_en": "Rice", "sector": "粮食"},
    "2709": {"name": "原油", "name_en": "Crude Petroleum", "sector": "能源"},
    "2711": {"name": "天然气", "name_en": "Petroleum Gas/LNG", "sector": "能源"},
    "2701": {"name": "煤炭", "name_en": "Coal", "sector": "能源"},
    "2601": {"name": "铁矿石", "name_en": "Iron Ore", "sector": "矿产"},
}

# 主要贸易伙伴
PARTNERS = {
    "0":   "世界",
    "842": "美国",
    "076": "巴西",
    "032": "阿根廷",
    "036": "澳大利亚",
    "643": "俄罗斯",
    "682": "沙特",
    "360": "印尼",
}


def gh_api(method, path, data=None):
    """调用 GitHub API"""
    cmd = ["gh", "api", "-X", method, f"repos/{REPO}/contents/{path}"]
    if data:
        cmd += ["--input", "-"]
        result = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None, result.stderr.strip()
    return json.loads(result.stdout) if result.stdout.strip() else {}, None


def push_to_bank(path, content, message):
    """推送到 Central-Bank"""
    json_str = json.dumps(content, ensure_ascii=False, indent=2)

    # 检查是否已存在
    existing, _ = gh_api("GET", path)

    body = {
        "message": message,
        "content": __import__("base64").b64encode(json_str.encode()).decode(),
        "encoding": "base64",
    }
    if existing and existing.get("sha"):
        body["sha"] = existing["sha"]

    result, err = gh_api("PUT", path, body)
    if err:
        print(f"  ❌ 推送失败: {err}")
        return False
    return True


def fetch_comtrade(reporter, partner, period, cmd_codes):
    """调用 COMTRADE Public API 获取贸易数据（免费，无需 key）"""
    cmd = ",".join(cmd_codes)
    url = f"{API_BASE}?reporterCode={reporter}&partnerCode={partner}&period={period}&cmdCode={cmd}&flowCode=M"

    req = urllib.request.Request(url, headers={"User-Agent": "open-signals/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data.get("data", [])
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("  ⚠️ 限流，等待 60 秒...")
            time.sleep(60)
            return fetch_comtrade(reporter, partner, period, cmd_codes)
        print(f"  ❌ HTTP {e.code}: {e.reason}")
        return []
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return []


def get_recent_months(n=30):
    """获取最近 n 个月的 YYYYMM 列表"""
    months = []
    now = datetime.now()
    y, m = now.year, now.month
    for _ in range(n):
        months.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return months


def run():
    if not GITHUB_TOKEN:
        print("❌ 未设置 GH_PAT")
        sys.exit(1)

    months = get_recent_months(30)
    cmd_codes = list(COMMODITIES.keys())
    all_results = {}
    empty_streak = 0
    found_count = 0

    for period in months:
        print(f"\n📅 采集 {period} 数据...")
        period_data = {}

        for partner_code, partner_name in PARTNERS.items():
            time.sleep(1.5)
            records = fetch_comtrade(CHINA, partner_code, period, cmd_codes)

            if not records:
                continue

            for r in records:
                cmd = r.get("cmdCode", "")
                if cmd not in COMMODITIES:
                    continue

                info = COMMODITIES[cmd]
                key = f"{partner_code}_{cmd}"

                period_data[key] = {
                    "period": period,
                    "commodity": info["name"],
                    "commodity_en": info["name_en"],
                    "hs_code": cmd,
                    "sector": info["sector"],
                    "partner": partner_name,
                    "partner_code": partner_code,
                    "import_value_usd": r.get("primaryValue") or 0,
                    "net_weight_kg": r.get("netWgt") or 0,
                    "quantity": r.get("qty") or 0,
                }

            print(f"  ✅ {partner_name}: {len(records)} 条记录")

        if period_data:
            # 推送到 Central-Bank
            y, m = period[:4], period[4:6]
            # 用最后一天作为日期（月度数据）
            last_day = (datetime(int(y), int(m) % 12 + 1, 1) - timedelta(days=1)).strftime("%d")
            path = f"data/comtrade/{y}/{m}/{last_day}/{period}.json"
            msg = f"📊 COMTRADE: {period} 中国进口数据"
            if push_to_bank(path, period_data, msg):
                print(f"  💾 已推送: Central-Bank/{path}")
                found_count += 1
            all_results[period] = period_data
            empty_streak = 0
        else:
            empty_streak += 1
            if empty_streak >= 18:
                print("\n⚠️ 连续 18 个月无数据，停止采集")
                break

    # 生成摘要
    if all_results:
        summary = generate_summary(all_results)
        summary_path = "data/comtrade/latest_summary.json"
        push_to_bank(summary_path, summary, f"📊 COMTRADE: 摘要更新 ({found_count} 个月)")
        print(f"\n📊 摘要已推送")
        print_summary(summary)


def generate_summary(all_results):
    """生成商品进口趋势摘要"""
    summary = {"updated": datetime.now().isoformat(), "commodities": {}}

    for period, data in sorted(all_results.items()):
        for key, record in data.items():
            if record["partner_code"] != "0":
                continue
            cmd = record["hs_code"]
            if cmd not in summary["commodities"]:
                summary["commodities"][cmd] = {
                    "name": record["commodity"],
                    "sector": record["sector"],
                    "trend": [],
                }
            summary["commodities"][cmd]["trend"].append({
                "period": period,
                "value_usd": record["import_value_usd"],
                "weight_kg": record["net_weight_kg"],
            })

    return summary


def print_summary(summary):
    """打印摘要"""
    print("\n" + "=" * 50)
    print("📊 中国大宗商品进口趋势")
    print("=" * 50)

    for cmd, info in summary["commodities"].items():
        trend = sorted(info["trend"], key=lambda x: x["period"])
        if len(trend) >= 2:
            latest = trend[-1]
            prev = trend[-2]
            prev_val = prev["value_usd"] or 0
            latest_val = latest["value_usd"] or 0
            change = 0
            if prev_val > 0:
                change = (latest_val - prev_val) / prev_val * 100
            arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
            print(f"  {info['name']:6} ({info['sector']}): {arrow} {change:+.1f}%  (${latest_val/1e9:.2f}B)")


if __name__ == "__main__":
    run()
