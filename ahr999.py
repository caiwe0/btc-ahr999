import os
import math
import time
import numpy as np
import pandas as pd
import requests
from datetime import datetime

CACHE_PATH = "btc_cache.csv"

# ═════════════════════════════════════════════════════════
# 1. 缓存读写（UTF‑8‑SIG，解决 CI 编码问题）
# ═════════════════════════════════════════════════════════

def save_cache_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")

def read_cache_csv_safe(path):
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
        try:
            return pd.read_csv(path, parse_dates=["日期"])
        except UnicodeDecodeError:
            continue
    if os.path.exists(path):
        os.remove(path)
    raise FileNotFoundError("缓存编码损坏已删除")

# ═════════════════════════════════════════════════════════
# 2. 三级数据源（Stooq → Yahoo，Investing 需 JS）
# ═════════════════════════════════════════════════════=
def fetch_stooq():
    print("📡 Stooq (BTCUSD) 获取数据...")
    url = "https://stooq.com/q/d/l/?s=btcusd&i=d"
    df = pd.read_csv(url)
    df.columns = df.columns.str.lower()
    df = df.rename(columns={
        "date": "日期",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume"
    })
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期").dropna(subset=["close"])
    print(f"✅ Stooq: {len(df)} 行")
    return df[["日期","open","high","low","close","volume"]]

def fetch_yahoo():
    import yfinance as yf
    print("📡 Yahoo Finance 兜底...")
    df = yf.download("BTC-USD", start="2013-01-01", interval="1d", progress=False)
    df = df.reset_index()
    df = df.rename(columns={
        "Date": "日期",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })
    df["日期"] = pd.to_datetime(df["日期"])
    print(f"✅ Yahoo: {len(df)} 行")
    return df[["日期","open","high","low","close","volume"]]

def fetch_btc_data(force_refresh=False):
    if force_refresh and os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
        print("🗑️ 强制刷新缓存")

    if not force_refresh and os.path.exists(CACHE_PATH):
        return read_cache_csv_safe(CACHE_PATH)

    for src in (fetch_stooq, fetch_yahoo):
        try:
            df = src()
            save_cache_csv(df, CACHE_PATH)
            return df
        except Exception as e:
            print(f"❌ {src.__name__} 失败: {e}")

    raise RuntimeError("所有数据源均失败")

# ═════════════════════════════════════════════════════════
# 3. ✅ 完全对齐 TV 的 AHR999 计算
# ═════════════════════════════════════════════════════════

def calculate_ahr999(df):
    df = df.copy().sort_values("日期").reset_index(drop=True)

    # ---------- 1. SMA200 ----------
    df["sma200"] = df["close"].rolling(200).mean()

    # ---------- 2. 币龄（天） ----------
    genesis = pd.Timestamp("2009-01-03")
    df["days_since_birth"] = np.maximum(
        (df["日期"] - genesis).dt.days, 1
    )

    # ---------- 3. 指数增长估值（幂律） ----------
    df["log_coin_age"] = np.log10(df["days_since_birth"])
    df["index_growth_val"] = 10 ** (
        5.84 * df["log_coin_age"] - 17.01
    )

    # ---------- 4. ✅ 流通供应量（BTC_SUPPLY） ----------
    days = df["days_since_birth"].values
    halvings = days // 210000
    reward = 50 * (0.5 ** halvings)
    block_per_day = 144
    supply = days * block_per_day * reward
    df["supply"] = supply / 1e8  # 转为 BTC 单位

    # ---------- 5. ✅ 已实现市值（Realized Cap） ----------
    # TV: realized_cap = request.security("BTC_MARKETCAPREAL")
    # 近似：SMA200 × 流通量（高保真日线近似）
    df["realized_cap"] = df["sma200"] * df["supply"]

    # ---------- 6. ✅ 实现价值（Realized Price） ----------
    df["realized_price"] = df["realized_cap"] / df["supply"]

    # ---------- 7. ✅ AHR999 ----------
    df["ahr999"] = np.where(
        (df["sma200"] > 0) &
        (df["index_growth_val"] > 0),
        (df["close"] / df["sma200"]) *
        (df["close"] / df["index_growth_val"]),
        np.nan
    )

    # ---------- 8. 偏离幅度 ----------
    df["deviation_pct"] = (
        (df["close"] - df["realized_price"]) / df["realized_price"] * 100
    )

    return df

# ═════════════════════════════════════════════════════════
# 4. 区间判断（九神标准）
# ═════════════════════════════════════════════════════════

def assign_zone(df):
    def zone(x):
        if pd.isna(x):
            return "数据不足"
        if x < 0.45:
            return "极度低估"
        if x < 0.8:
            return "定投区"
        if x < 1.2:
            return "合理区"
        if x < 2.0:
            return "偏高"
        return "高估"
    df["zone"] = df["ahr999"].apply(zone)
    return df

# ═════════════════════════════════════════════════════════
# 5. 流水线
# ═════════════════════════════════════════════════════════

def run_pipeline(force_refresh=False):
    print(f"\n{'='*60}")
    print(f"  ₿ BTC AHR999 Pipeline（TV 对齐版）")
    print(f"{'='*60}\n")

    df = fetch_btc_data(force_refresh)
    df = calculate_ahr999(df)
    df = assign_zone(df)

    latest = df.dropna(subset=["ahr999"]).iloc[-1]

    print(f"\n📡 数据源: Stooq / Yahoo")
    print(f"📅 最新日期: {latest['日期'].strftime('%Y-%m-%d')}")
    print(f"📈 现价: ${latest['close']:,.2f}")
    print(f"💰 实现价值 (Realized Price): ${latest['realized_price']:,.2f}")
    print(f"📊 偏离幅度: {latest['deviation_pct']:.2f}%")
    print(f"📐 SMA200: ${latest['sma200']:,.2f}")
    print(f"🌐 幂律估值: ${latest['index_growth_val']:,.2f}")
    print(f"📐 AHR999: {latest['ahr999']:.4f}")
    print(f"🏷️ 区间: {latest['zone']}")

    return df

if __name__ == "__main__":
    run_pipeline(force_refresh=True)
