#!/usr/bin/env python3
"""
OpenSky Network 货运航班追踪器
监控关键货运航线频次变化
数据推送到 Central-Bank/data/opensky/
"""

import json, os, time, sys
from datetime import datetime
from pathlib import Path
import urllib.request, urllib.error
import subprocess

# OpenSky API (免费，无需 key)
API_BASE = "https://opensky-network.org/api"

# GitHub
GITHUB_TOKEN = os.environ.get("GH_PAT", "")
REPO = "wenfp108/Central-Bank"

# 关键货运航线区域（bbox: lat1, lon1, lat2, lon2）
CARGO_ROUTES = {
    "中东→中国": {
        "bbox": (15, 35, 40, 60),
        "desc": "波斯湾/中东出发，能源/商品相关",
    },
    "巴西→中国": {
        "bbox": (-35, -60, 5, -30),
        "desc": "巴西出发，大豆/铁矿相关",
    },
    "美国→中国": {
        "bbox": (25, -130, 50, -70),
        "desc": "美国出发，农产品/科技相关",
    },
    "澳大利亚→中国": {
        "bbox": (-40, 112, -10, 155),
        "desc": "澳大利亚出发，铁矿/煤炭相关",
    },
}

# 全球主要货运机场
CARGO_AIRPORTS = {
    "PVG": {"name": "上海浦东", "lat": 31.15, "lon": 121.80, "country": "CN"},
    "HKG": {"name": "香港", "lat": 22.31, "lon": 113.91, "country": "HK"},
    "ICN": {"name": "首尔仁川", "lat": 37.46, "lon": 126.44, "country": "KR"},
    "MEM": {"name": "孟菲斯(FedEx)", "lat": 35.04, "lon": -89.98, "country": "US"},
    "SDF": {"name": "路易斯维尔(UPS)", "lat": 38.17, "lon": -85.74, "country": "US"},
    "DXB": {"name": "迪拜", "lat": 25.25, "lon": 55.36, "country": "AE"},
    "FRA": {"name": "法兰克福", "lat": 50.03, "lon": 8.57, "country": "DE"},
    "ANC": {"name": "安克雷奇", "lat": 61.17, "lon": -150.00, "country": "US"},
}

# 常见货运航空公司 ICAO 代码
CARGO_PREFIXES = [
    "FDX", "UPS", "DHL", "TNT", "GEC", "CLX",
    "CKK", "CSN", "CES", "CHH", "CSZ", "CDC",
    "SQC", "GTI", "PAC", "BOX", "QTR",
    "ABW", "TAY", "FHY", "AAR",
]


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
    """判断是否为货机"""
    callsign = (state[1] or "").strip().upper()
    if not callsign:
        return False
    return any(callsign.startswith(p) for p in CARGO_PREFIXES)


def run():
    if not GITHUB_TOKEN:
        print("❌ 未设置 GH_PAT")
        sys.exit(1)

    today = datetime.now().strftime("%Y%m%d")
    print(f"📡 OpenSky 货运航班追踪 ({today})")
    print("=" * 50)

    results = {
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "routes": {},
        "airports": {},
    }

    # 货运航线统计
    print("\n🛫 货运航线监控:")
    for route_name, route in CARGO_ROUTES.items():
        print(f"\n  📍 {route_name} ({route['desc']})")
        states = fetch_states_by_bbox(route["bbox"])
        time.sleep(2)

        total = len(states)
        cargo = sum(1 for s in states if is_cargo_flight(s))

        results["routes"][route_name] = {
            "total_flights": total,
            "cargo_flights": cargo,
            "desc": route["desc"],
        }
        print(f"    总航班: {total}, 货机: {cargo}")

    # 主要货运机场统计
    print("\n🏢 主要货运机场:")
    for icao, info in CARGO_AIRPORTS.items():
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

    # 推送到 Central-Bank
    y = today[:4]
    m = today[4:6]
    d = today[6:8]
    path = f"data/opensky/{y}/{m}/{d}/{today}.json"
    msg = f"✈️ OpenSky: {today} 货运航班数据"

    if push_to_bank(path, results, msg):
        print(f"\n💾 已推送: Central-Bank/{path}")

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
