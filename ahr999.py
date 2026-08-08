"""
₿ BTC AHR999 指标计算（对齐 TradingView 九神公式）

公式：
  sma200        = ta.sma(close, 200)
  daysSinceBirth = max((time - 2009-01-03) / 86400, 1)
  logCoinAge    = log10(daysSinceBirth)
  indexGrowthVal= 10^(5.84 * logCoinAge - 17.01)
  ahr999        = close / sma200 * (close / indexGrowthVal)

网页展示字段：现价 / AHR999 / 偏离幅度(SMA200) / SMA200 / 幂律估值 / 区间
（不展示"实现价值"）
"""
import math
import numpy as np
import pandas as pd

from btc_data import load_btc_data

# ════════════════════════════════════════════════════════
# 1. 核心计算
# ════════════════════════════════════════════════════════

def calculate_ahr999(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().sort_values("date").reset_index(drop=True)

    # ---------- SMA200 ----------
    df["sma200"] = df["close"].rolling(window=200).mean()

    # ---------- 币龄 ----------
    genesis = pd.Timestamp("2009-01-03")
    days = (df["date"] - genesis).dt.total_seconds() / 86400.0
    days = np.maximum(days, 1.0)

    # ---------- 指数增长估值（幂律）----------
    log_age = np.log10(days)
    df["index_growth_val"] = 10 ** (5.84 * log_age - 17.01)

    # ---------- ✅ AHR999 ----------
    df["ahr999"] = (df["close"] / df["sma200"]) * (df["close"] / df["index_growth_val"])

    # ---------- 偏离幅度（现价 vs SMA200）----------
    df["deviation_pct"] = (df["close"] - df["sma200"]) / df["sma200"] * 100

    # ---------- 涨跌幅 ----------
    if "change_pct" not in df.columns:
        df["change_pct"] = df["close"].pct_change() * 100

    return df

# ════════════════════════════════════════════════════════
# 2. 区间判定（九神标准）
# ════════════════════════════════════════════════════════

ZONE_RULES = [
    (0.45, "极度低估", "#00e676"),
    (0.80, "定投区",   "#76ff03"),
    (1.20, "合理区",   "#ffd600"),
    (2.00, "偏高",     "#ff9100"),
    (np.inf, "高估",    "#ff1744"),
]

def assign_zone(df: pd.DataFrame) -> pd.DataFrame:
    def _zone(x):
        if pd.isna(x):
            return "数据不足"
        for cap, label, _ in ZONE_RULES:
            if x < cap:
                return label
        return "高估"
    df["zone"] = df["ahr999"].apply(_zone)
    return df

# ════════════════════════════════════════════════════════
# 3. 异常 K 线检测
# ════════════════════════════════════════════════════════

def detect_anomalies(df: pd.DataFrame, z_thresh: float = 4.0) -> pd.DataFrame:
    df = df.copy()
    if "change_pct" not in df.columns:
        df["change_pct"] = df["close"].pct_change() * 100

    mean = df["change_pct"].rolling(200, min_periods=30).mean()
    std = df["change_pct"].rolling(200, min_periods=30).std()
    df["anomaly"] = (df["change_pct"].abs() > z_thresh * std) & df["change_pct"].notna()
    return df

# ════════════════════════════════════════════════════════
# 4. 流水线
# ════════════════════════════════════════════════════════

def run_pipeline(src: str = "btc_cache.csv"):
    print(f"\n{'='*60}")
    print(f"  ₿ BTC AHR999 Pipeline（用户数据版）")
    print(f"{'='*60}\n")

    df = load_btc_data(src)
    print(f"📊 原始数据: {len(df)} 行 | {df['date'].min().date()} → {df['date'].max().date()}")

    df = calculate_ahr999(df)
    df = assign_zone(df)
    df = detect_anomalies(df)

    valid = df.dropna(subset=["ahr999"])
    n_valid = len(valid)
    n_total = len(df)
    print(f"✅ AHR999 有效: {n_valid}/{n_total} 行")
    print(f"⚠️ 异常 K 线: {int(df['anomaly'].sum())} 根")

    if n_valid > 0:
        latest = valid.iloc[-1]
        print(f"\n📅 最新日期:  {latest['date'].strftime('%Y-%m-%d')}")
        print(f"📈 现价:       ${latest['close']:>12,.2f}")
        print(f"📊 偏离幅度:    {latest['deviation_pct']:>11.2f}%")
        print(f"📐 SMA200:      ${latest['sma200']:>12,.2f}")
        print(f"🌐 幂律估值:    ${latest['index_growth_val']:>12,.2f}")
        print(f"📐 AHR999:     {latest['ahr999']:>12.4f}")
        print(f"🏷️  区间:        {latest['zone']}")
    else:
        print("⚠️ 无有效 AHR999 数据（数据量不足 200 行）")

    return df

if __name__ == "__main__":
    run_pipeline()
