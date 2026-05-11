#!/usr/bin/env python3
"""
OpenSky Network 货运航班追踪器
监控关键货运航线频次变化
"""

import json, os, time, sys
from datetime import datetime, timedelta
from pathlib import Path
import urllib.request, urllib.error

# OpenSky API (免费，无需 key，每天 5000 次)
API_BASE = "https://opensky-network.org/api"

# 关键货运航线区域（bbox: lat1, lon1, lat2, lon2）
CARGO_ROUTES = {
    "中东→中国": {
        "bbox": (15, 35, 40, 60),  # 波斯湾区域
        "dest_bbox": (20, 100, 45, 130),  # 中国区域
        "desc": "波斯湾/中东出发，能源/商品相关",
    },
    "巴西→中国": {
        "bbox": (-35, -60, 5, -30),  # 巴西区域
        "dest_bbox": (20, 100, 45, 130),  # 中国区域
        "desc": "巴西出发，大豆/铁矿相关",
    },
    "美国→中国": {
        "bbox": (25, -130, 50, -70),  # 美国区域
        "dest_bbox": (20, 100, 45, 130),  # 中国区域
        "desc": "美国出发，农产品/科技相关",
    },
    "澳大利亚→中国": {
        "bbox": (-40, 112, -10, 155),  # 澳大利亚区域
        "dest_bbox": (20, 100, 45, 130),  # 中国区域
        "desc": "澳大利亚出发，铁矿/煤炭相关",
    },
}

# 全球主要货运机场（用于统计货运航班）
CARGO_AIRPORTS = {
    "PVG": {"name": "上海浦东", "lat": 31.15, "lon": 121.80, "country": "CN"},
    "HKG": {"name": "香港", "lat": 22.31, "lon": 113.91, "country": "HK"},
    "ICN": {"name": "首尔仁川", "lat": 37.46, "lon": 126.44, "country": "KR"},
    "NRT": {"name": "东京成田", "lat": 35.77, "lon": 140.39, "country": "JP"},
    "MEM": {"name": "孟菲斯(FedEx)", "lat": 35.04, "lon": -89.98, "country": "US"},
    "SDF": {"name": "路易斯维尔(UPS)", "lat": 38.17, "lon": -85.74, "country": "US"},
    "DXB": {"name": "迪拜", "lat": 25.25, "lon": 55.36, "country": "AE"},
    "FRA": {"name": "法兰克福", "lat": 50.03, "lon": 8.57, "country": "DE"},
    "LHR": {"name": "伦敦希思罗", "lat": 51.47, "lon": -0.46, "country": "GB"},
    "ANC": {"name": "安克雷奇", "lat": 61.17, "lon": -150.00, "country": "US"},
}

DATA_DIR = Path(__file__).parent.parent / "data" / "opensky"


def fetch_states_by_bbox(bbox):
    """获取指定区域内的所有航班"""
    lat1, lon1, lat2, lon2 = bbox
    url = f"{API_BASE}/states/all?lamin={lat1}&lomin={lon1}&lamax={lat2}&lomax={lon2}"

    req = urllib.request.Request(url, headers={"User-Agent": "open-signals/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data.get("states", []) or []
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("  ⚠️ 限流，等待 60 秒...")
            time.sleep(60)
            return fetch_states_by_bbox(bbox)
        print(f"  ❌ HTTP {e.code}")
        return []
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return []


def is_cargo_flight(state):
    """判断是否为货机（基于 ICAO 呼号前缀）"""
    callsign = (state[1] or "").strip().upper()
    if not callsign:
        return False

    # 常见货运航空公司 ICAO 代码
    cargo_prefixes = [
        "FDX", "UPS", "DHL", "TNT", "GEC", "CLX",  # FedEx, UPS, DHL, TNT, Lufthansa Cargo, Cargolux
        "ETH", "SIA", "KAL", "CPA", "ANA", "JAL",  # 货运兼营
        "CKK", "CSN", "CES", "CHH", "CSZ", "CDC",  # 中国货运：中货航、南货航、东货航等
        "SQC", "GTI", "PAC", "FDX", "BOX", "QTR",  # 新加坡货航、Atlas Air、Polar Air、Qatar Cargo
        "ABW", "TAY", "FHY", "ACA", "AAR",         # AirBridgeCargo, TNT Airways, Atlas Air
    ]
    return any(callsign.startswith(p) for p in cargo_prefixes)


def run():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    print(f"📡 OpenSky 货运航班追踪 ({today})")
    print("=" * 50)

    results = {
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "routes": {},
        "airports": {},
    }

    # 1. 货运航线统计
    print("\n🛫 货运航线监控:")
    for route_name, route in CARGO_ROUTES.items():
        print(f"\n  📍 {route_name} ({route['desc']})")

        # 获取出发区域航班
        states = fetch_states_by_bbox(route["bbox"])
        time.sleep(2)  # 避免限流

        total = len(states)
        cargo = sum(1 for s in states if is_cargo_flight(s))

        results["routes"][route_name] = {
            "total_flights": total,
            "cargo_flights": cargo,
            "desc": route["desc"],
        }

        print(f"    总航班: {total}, 货机: {cargo}")

    # 2. 主要货运机场统计
    print("\n🏢 主要货运机场:")
    for icao, info in CARGO_AIRPORTS.items():
        # 获取机场附近航班（0.5度范围内）
        bbox = (info["lat"] - 0.5, info["lon"] - 0.5, info["lat"] + 0.5, info["lon"] + 0.5)
        states = fetch_states_by_bbox(bbox)
        time.sleep(1)

        total = len(states)
        cargo = sum(1 for s in states if is_cargo_flight(s))

        results["airports"][icao] = {
            "name": info["name"],
            "country": info["country"],
            "total_flights": total,
            "cargo_flights": cargo,
        }

        print(f"    {info['name']:12} ({icao}): 总 {total}, 货机 {cargo}")

    # 保存结果
    outfile = DATA_DIR / f"cargo_flights_{today}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 保存: {outfile.name}")

    # 打印摘要
    print_summary(results)


def print_summary(results):
    """打印摘要"""
    print("\n" + "=" * 50)
    print("📊 货运航班摘要")
    print("=" * 50)

    for route, data in results["routes"].items():
        pct = (data["cargo_flights"] / data["total_flights"] * 100) if data["total_flights"] > 0 else 0
        print(f"  {route:16}: 货机 {data['cargo_flights']:3d} / 总 {data['total_flights']:4d} ({pct:.1f}%)")


if __name__ == "__main__":
    run()
