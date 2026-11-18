#!/usr/bin/env python3
"""
把 data/ 里的采集结果渲染成 README 用的 SVG 图表（无第三方依赖）。

    python3 scripts/render_charts.py

输出：
    docs/corridors.svg   货运航班单日快照（横向条形图）
    docs/imports.svg     中国大宗商品进口额月度趋势（折线图）
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

SANS = "-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Noto Sans SC, sans-serif"
MONO = "ui-monospace, SF Mono, Menlo, monospace"

INK = "#14161c"
MUTED = "#747b8a"
GRID = "#e7e8ee"
ACCENT = "#4f46e5"
SERIES = ["#4f46e5", "#e8890c", "#0e9f6e", "#0ea5e9", "#8b5cf6", "#ef4444", "#14b8a6", "#a16207"]


def esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fmt_billion(v):
    return f"{v / 1e9:.1f}"


def load_snapshot():
    files = sorted((ROOT / "data" / "opensky").rglob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def load_summary():
    path = ROOT / "data" / "comtrade" / "latest_summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def svg_open(width, height):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
    )


def text(x, y, s, size=12, fill=INK, weight=400, anchor="start", mono=False, opacity=1):
    family = MONO if mono else SANS
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}" opacity="{opacity}">{esc(s)}</text>'
    )


def render_corridors():
    snap = load_snapshot()
    if not snap:
        print("⚠️ 没有 OpenSky 数据，跳过 corridors.svg")
        return False

    routes = snap.get("routes", {})
    rows = sorted(routes.items(), key=lambda kv: kv[1].get("cargo_flights", 0), reverse=True)
    if not rows:
        print("⚠️ OpenSky 数据为空，跳过 corridors.svg")
        return False

    W, H = 880, 316
    left, right = 132, 200
    top = 96
    row_h = 46
    bar_h = 22
    max_cargo = max([r.get("cargo_flights", 0) for _, r in rows] + [1])
    plot_w = W - left - right

    parts = [svg_open(W, H)]
    parts.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    parts.append(text(28, 42, "货运航班 · 单日快照", 19, INK, 650))
    d = str(snap.get("date", ""))
    d = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
    parts.append(text(28, 64, f"OpenSky Network · {d} · 按货运走廊统计", 12, MUTED))

    for i, (name, r) in enumerate(rows):
        y = top + i * row_h
        cargo = r.get("cargo_flights", 0)
        total = r.get("total_flights", 0)
        w = 0 if cargo == 0 else max(3, plot_w * cargo / max_cargo)

        parts.append(text(left - 14, y + bar_h - 5, name, 13, INK, 550, anchor="end"))
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{plot_w}" height="{bar_h}" rx="6" fill="#f1f2f7"/>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{w:.1f}" height="{bar_h}" rx="6" fill="{ACCENT}" opacity="0.9"/>'
        )
        parts.append(text(W - 106, y + bar_h - 4, f"{cargo} 架", 13, INK, 600, mono=True, anchor="end"))
        parts.append(text(W - 28, y + bar_h - 4, f"总 {total}", 11, MUTED, 400, mono=True, anchor="end"))

    note_y = top + len(rows) * row_h + 22
    parts.append(
        f'<line x1="28" y1="{note_y - 14}" x2="{W - 28}" y2="{note_y - 14}" stroke="{GRID}" stroke-width="1"/>'
    )
    parts.append(
        text(28, note_y + 6, "货机识别基于呼号前缀（FedEx / UPS / 顺丰 / 国货航等），为近似统计。", 11, MUTED)
    )
    parts.append("</svg>")

    DOCS.mkdir(exist_ok=True)
    (DOCS / "corridors.svg").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("✅ docs/corridors.svg")
    return True


def render_imports():
    summary = load_summary()
    if not summary or not summary.get("commodities"):
        print("⚠️ 没有 COMTRADE 数据，跳过 imports.svg")
        return False

    # 选数据最全的 4 个品类
    ranked = sorted(
        summary["commodities"].items(),
        key=lambda kv: (len(kv[1].get("trend", [])), max([t.get("value_usd", 0) for t in kv[1].get("trend", [])] or [0])),
        reverse=True,
    )[:4]
    ranked = [kv for kv in ranked if kv[1].get("trend")]

    periods = sorted({t["period"] for _, info in ranked for t in info["trend"]})
    if not periods:
        print("⚠️ COMTRADE 趋势为空，跳过 imports.svg")
        return False

    W, H = 880, 360
    left, right, top, bottom = 60, 28, 100, 46
    plot_w = W - left - right
    plot_h = H - top - bottom

    values = [t.get("value_usd", 0) for _, info in ranked for t in info["trend"]]
    vmax = max(values + [1])
    # 取整到一个好看的刻度
    step = 10 ** (len(str(int(vmax))) - 1) / 2
    ymax = (int(vmax / step) + 1) * step

    def x_at(i):
        return left + (plot_w * i / max(1, len(periods) - 1) if len(periods) > 1 else plot_w / 2)

    def y_at(v):
        return top + plot_h - plot_h * (v / ymax)

    parts = [svg_open(W, H)]
    parts.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    parts.append(text(28, 42, "中国大宗商品进口额", 19, INK, 650))
    parts.append(
        text(
            28,
            64,
            f"UN COMTRADE · {periods[0][:4]}-{periods[0][4:]} → {periods[-1][:4]}-{periods[-1][4:]} · 月度 · 世界合计",
            12,
            MUTED,
        )
    )

    # 网格与 y 轴
    for k in range(5):
        v = ymax * k / 4
        y = y_at(v)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(text(left - 10, y + 4, f"{fmt_billion(v)}B", 10, MUTED, mono=True, anchor="end"))

    # x 轴标签（最多 8 个）
    every = max(1, len(periods) // 8)
    for i, period in enumerate(periods):
        if i % every and i != len(periods) - 1:
            continue
        parts.append(
            text(x_at(i), top + plot_h + 22, f"{period[:4]}-{period[4:]}", 10, MUTED, mono=True, anchor="middle")
        )

    # 折线
    for idx, (cmd, info) in enumerate(ranked):
        color = SERIES[idx % len(SERIES)]
        trend = sorted(info["trend"], key=lambda t: t["period"])
        pts = [(x_at(periods.index(t["period"])), y_at(t.get("value_usd", 0))) for t in trend]
        if len(pts) > 1:
            d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            parts.append(
                f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="2.2" '
                f'stroke-linejoin="round" stroke-linecap="round" opacity="0.95"/>'
            )
        for x, y in pts:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#fff" stroke="{color}" stroke-width="2"/>')

    # 图例
    lx = left
    for idx, (cmd, info) in enumerate(ranked):
        color = SERIES[idx % len(SERIES)]
        label = info.get("name", cmd)
        parts.append(f'<circle cx="{lx + 5}" cy="{84}" r="4.5" fill="{color}"/>')
        parts.append(text(lx + 15, 88, label, 12, INK, 500))
        lx += 15 + len(label) * 13 + 18

    parts.append("</svg>")

    DOCS.mkdir(exist_ok=True)
    (DOCS / "imports.svg").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("✅ docs/imports.svg")
    return True


if __name__ == "__main__":
    ok1 = render_corridors()
    ok2 = render_imports()
    if not (ok1 or ok2):
        raise SystemExit("❌ 没有任何可渲染的数据")
