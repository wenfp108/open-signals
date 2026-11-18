#!/usr/bin/env python3
"""
在本地生成一份中国大宗商品进口快照（不推送任何仓库）。

用途：让没有 Central-Bank 访问权限的人也能复现数据、画图、做分析。

    python3 scripts/snapshot_comtrade.py --months 12

数据来源：UN COMTRADE Public API（免费、无需 key）。
输出：
    data/comtrade/{yyyy}/{mm}/{last_day}/{yyyymm}.json
    data/comtrade/latest_summary.json
"""

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

API_BASE = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
CHINA = 156
ROOT = Path(__file__).resolve().parent.parent

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

PARTNERS = {
    "0": "世界",
    "842": "美国",
    "076": "巴西",
    "032": "阿根廷",
    "036": "澳大利亚",
    "643": "俄罗斯",
    "682": "沙特",
    "360": "印尼",
}


def fetch(reporter, partner, period, codes):
    cmd_codes = ",".join(codes)
    url = (
        f"{API_BASE}?reporterCode={reporter}&partnerCode={partner}"
        f"&period={period}&cmdCode={cmd_codes}&flowCode=M"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "open-signals/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read()).get("data", [])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 30 * (attempt + 1)
                print(f"    ⚠️ 限流，等待 {wait}s…")
                time.sleep(wait)
                continue
            print(f"    ❌ HTTP {e.code}: {e.reason}")
            return []
        except Exception as e:
            print(f"    ❌ 请求失败: {e}")
            time.sleep(5)
    return []


def months_back(n):
    y, m = date.today().year, date.today().month
    for _ in range(n):
        yield f"{y}{m:02d}"
        m -= 1
        if m == 0:
            m = 12
            y -= 1


def last_day_of(period):
    y, m = int(period[:4]), int(period[4:6])
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1).strftime("%d")


def record(period, cmd, row, partner_code):
    info = COMMODITIES[cmd]
    return {
        "period": period,
        "commodity": info["name"],
        "commodity_en": info["name_en"],
        "hs_code": cmd,
        "sector": info["sector"],
        "partner": PARTNERS[partner_code],
        "partner_code": partner_code,
        "import_value_usd": row.get("primaryValue") or 0,
        "net_weight_kg": row.get("netWgt") or 0,
        "quantity": row.get("qty") or 0,
    }


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"    💾 {path.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description="生成中国大宗商品进口本地快照")
    ap.add_argument("--months", type=int, default=12, help="抓取最近 N 个有数据的月份（默认 12）")
    ap.add_argument("--probe", type=int, default=36, help="向前探测多少个月（默认 36）")
    ap.add_argument("--periods", help="直接指定月份，逗号分隔，如 202401,202402（跳过探测）")
    ap.add_argument("--no-partners", action="store_true", help="不抓取分国别数据，只保留世界合计")
    ap.add_argument("--sleep", type=float, default=2.0, help="每次请求之间的间隔秒数")

    args = ap.parse_args()
    codes = list(COMMODITIES)

    if args.periods:
        valid = [p.strip() for p in args.periods.split(",") if p.strip()]
        print(f"📅 使用指定月份: {', '.join(valid)}")
    else:
        print(f"🔍 向前探测有数据的月份（最多 {args.probe} 个月）…")
        valid = []
        for period in months_back(args.probe):
            rows = fetch(CHINA, 0, period, codes)
            if rows:
                valid.append(period)
                print(f"  ✅ {period}: {len(rows)} 条")
                if len(valid) >= args.months:
                    break
            else:
                print(f"  ⏭️ {period}: 无数据")
            time.sleep(args.sleep)

    if not valid:
        raise SystemExit("❌ 没有找到任何数据")

    summary = {"updated": datetime.now().isoformat(timespec="seconds"), "commodities": {}}

    for i, period in enumerate(sorted(valid)):
        print(f"\n📅 {period}")
        rows = fetch(CHINA, 0, period, codes)
        period_data = {}
        for r in rows:
            cmd = r.get("cmdCode", "")
            if cmd in COMMODITIES:
                period_data[f"0_{cmd}"] = record(period, cmd, r, "0")
        time.sleep(args.sleep)

        # 最新一个月额外抓取主要贸易伙伴
        if not args.no_partners and i == len(valid) - 1:
            for partner_code in PARTNERS:
                if partner_code == "0":
                    continue
                prows = fetch(CHINA, partner_code, period, codes)
                for r in prows:
                    cmd = r.get("cmdCode", "")
                    if cmd in COMMODITIES:
                        period_data[f"{partner_code}_{cmd}"] = record(period, cmd, r, partner_code)
                time.sleep(args.sleep)

        path = ROOT / "data/comtrade" / period[:4] / period[4:6] / last_day_of(period) / f"{period}.json"
        write_json(path, period_data)

        for key, rec in period_data.items():
            if rec["partner_code"] != "0":
                continue
            cmd = rec["hs_code"]
            bucket = summary["commodities"].setdefault(
                cmd, {"name": rec["commodity"], "sector": rec["sector"], "trend": []}
            )
            bucket["trend"].append(
                {"period": period, "value_usd": rec["import_value_usd"], "weight_kg": rec["net_weight_kg"]}
            )

    write_json(ROOT / "data/comtrade/latest_summary.json", summary)

    print("\n" + "=" * 56)
    print("📊 最新月份进口额（世界合计）")
    print("=" * 56)
    for cmd, info in summary["commodities"].items():
        trend = sorted(info["trend"], key=lambda x: x["period"])
        latest = trend[-1]
        print(f"  {info['name']:6} {latest['period']}: ${latest['value_usd'] / 1e9:6.2f}B")


if __name__ == "__main__":
    main()
