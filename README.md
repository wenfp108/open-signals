# open-signals

开源地缘政治信号数据采集，用于大宗商品趋势推断。

数据自动推送到 [Central-Bank](https://github.com/wenfp108/Central-Bank)。

## 数据源

| 脚本 | 来源 | 内容 | 频率 |
|:---|:---|:---|:---|
| `comtrade/` | UN COMTRADE | 中国大宗商品进口（粮食/能源/矿产） | 月度 |
| `opensky/` | OpenSky Network | 货运航班频次（中东/巴西/美国/澳洲→中国） | 日度 |

## 关注指标

### 贸易数据（COMTRADE）
- 粮食：大豆、玉米、小麦、稻米（分来源国）
- 能源：原油、天然气、煤炭
- 矿产：铁矿石

### 航班数据（OpenSky）
- 中东→中国（能源相关）
- 巴西→中国（大豆/铁矿相关）
- 美国→中国（农产品/科技相关）
- 澳大利亚→中国（铁矿/煤炭相关）

## 数据结构

```
Central-Bank/data/
├── comtrade/
│   ├── latest_summary.json
│   └── 2024/12/31/202412.json
└── opensky/
    └── 2026/05/12/20260512.json
```

## 配置

需要在 GitHub repo Settings → Secrets 添加 `GH_PAT`（Central-Bank 写入权限）。

## 使用方式

```bash
# 采集中国粮食进口数据
GH_PAT=your_token python3 comtrade/fetch_comtrade.py

# 采集货运航班数据
GH_PAT=your_token python3 opensky/fetch_opensky.py
```

两个数据源均为免费公开 API，无需注册。GitHub Actions 每天自动采集并推送到 Central-Bank。
