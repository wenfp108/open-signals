#!/usr/bin/env python3
"""
UN COMTRADE 数据采集器
采集中国主要大宗商品进口数据（粮食、能源、矿产）
"""

import json, os, time, sys
from datetime import datetime, timedelta
from pathlib import Path
import urllib.request, urllib.error

# UN COMTRADE API
# 免费注册: https://comtradeplus.un.org/subscriptions
# 注册后在 GitHub repo Settings → Secrets 添加 COMTRADE_KEY
API_KEY = os.environ.get("COMTRADE_KEY", "")
API_BASE = "https://comtradeapi.un.org/data/v1/get/C/M/HS"

# 中国 reporter code
CHINA = 156
WORLD = 0

# 关注商品 HS 编码
COMMODITIES = {
    # 粮食
    "1201": {"name": "大豆", "name_en": "Soybeans", "sector": "粮食"},
    "1005": {"name": "玉米", "name_en": "Corn/Maize", "sector": "粮食"},
    "1001": {"name": "小麦", "name_en": "Wheat", "sector": "粮食"},
    "1006": {"name": "稻米", "name_en": "Rice", "sector": "粮食"},
    # 能源
    "2709": {"name": "原油", "name_en": "Crude Petroleum", "sector": "能源"},
    "2711": {"name": "天然气", "name_en": "Petroleum Gas/LNG", "sector": "能源"},
    "2701": {"name": "煤炭", "name_en": "Coal", "sector": "能源"},
    # 矿产
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
    "031": "阿塞拜疆",
    "360": "印尼",
}

DATA_DIR = Path(__file__).parent.parent / "data" / "comtrade"


def fetch_comtrade(reporter, partner, period, cmd_codes):
    """调用 COMTRADE API 获取贸易数据"""
    if not API_KEY:
        print("  ❌ 未设置 COMTRADE_KEY，请先注册: https://comtradeplus.un.org/subscriptions")
        return []

    cmd = ",".join(cmd_codes)
    url = f"{API_BASE}?reporterCode={reporter}&partnerCode={partner}&period={period}&cmdCode={cmd}&flowCode=M&subscriptioncode={API_KEY}"

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


def get_recent_months(n=6):
    """获取最近 n 个月的 YYYYMM 列表"""
    months = []
    now = datetime.now()
    for i in range(n):
        d = now - timedelta(days=30 * i)
        months.append(d.strftime("%Y%m"))
    return months


def run():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 获取最近 3 个月数据（COMTRADE 数据有延迟）
    months = get_recent_months(3)
    cmd_codes = list(COMMODITIES.keys())

    all_results = {}

    for period in months:
        print(f"\n📅 采集 {period} 数据...")
        period_data = {}

        for partner_code, partner_name in PARTNERS.items():
            time.sleep(1)  # 避免限流
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
                    "import_value_usd": r.get("primaryValue", 0),
                    "net_weight_kg": r.get("netWgt", 0),
                    "quantity": r.get("qty", 0),
                }

            print(f"  ✅ {partner_name}: {len(records)} 条记录")

        # 保存月度文件
        if period_data:
            outfile = DATA_DIR / f"china_imports_{period}.json"
            with open(outfile, "w", encoding="utf-8") as f:
                json.dump(period_data, f, ensure_ascii=False, indent=2)
            print(f"  💾 保存: {outfile.name} ({len(period_data)} 条)")
            all_results[period] = period_data

    # 生成摘要
    if all_results:
        summary = generate_summary(all_results)
        summary_file = DATA_DIR / "latest_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n📊 摘要已保存: {summary_file.name}")
        print_summary(summary)


def generate_summary(all_results):
    """生成商品进口趋势摘要"""
    summary = {"updated": datetime.now().isoformat(), "commodities": {}}

    for period, data in sorted(all_results.items()):
        for key, record in data.items():
            if record["partner_code"] != "0":  # 只看世界总计
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
            change = 0
            if prev["value_usd"] and prev["value_usd"] > 0:
                change = (latest["value_usd"] - prev["value_usd"]) / prev["value_usd"] * 100
            arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
            print(f"  {info['name']:6} ({info['sector']}): {arrow} {change:+.1f}%  (${latest['value_usd']/1e9:.2f}B)")


if __name__ == "__main__":
    run()
