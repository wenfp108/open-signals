# open-signals

开源地缘政治信号数据采集，用于大宗商品趋势推断。

## 数据源

| 目录 | 来源 | 内容 | 频率 |
|:---|:---|:---|:---|
| `comtrade/` | UN COMTRADE | 全球贸易统计（精确到商品+国家） | 月度 |
| `opensky/` | OpenSky Network | 货运航班频次追踪 | 日度 |

## 关注指标

### 贸易数据（COMTRADE）
- 中国粮食进口：大豆、玉米、小麦（分来源国）
- 中国能源进口：原油、天然气
- 中国矿产进口：铁矿石

### 航班数据（OpenSky）
- 波斯湾 → 中国 货运航班频次
- 巴西 → 中国 货运航班频次
- 美国 → 中国 货运航班频次

## 使用方式

```bash
# 采集中国粮食进口数据
python3 comtrade/fetch_comtrade.py

# 采集货运航班数据
python3 opensky/fetch_opensky.py
```

## 自动化

GitHub Actions 每天 UTC 06:00 自动采集。

## 文件结构

```
data/
├── comtrade/
│   └── china_imports_YYYYMM.json    # 月度贸易数据
└── opensky/
    └── cargo_flights_YYYYMMDD.json  # 日度航班数据
```
