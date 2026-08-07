#!/usr/bin/env python3
"""
₿ BTC AHR999 定投指标 · 主程序（UTF‑8 缓存修复版）
"""
import os
import json
import math
import time
import logging
from datetime import datetime

import numpy as np
import pandas as pd
import config

# ── 日志 ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="  %(asctime)s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════
#  1. 数据获取（多源降级 + 缓存 · UTF‑8 修复）
# ═════════════════════════════════════════════════════════
def fetch_btc_data(force_refresh=False):
    """获取 BTC 日线数据，多源降级 + 本地缓存（UTF‑8）"""
    cache = config.CACHE_FILE

    # 强制刷新：删除旧缓存
    if force_refresh and os.path.exists(cache):
        os.remove(cache)
        log.info(f"  🗑️ 强制刷新：已删除旧缓存 {cache}")

    # 缓存命中（6小时内不重拉）
    if not force_refresh and os.path.exists(cache):
        age = datetime.now().timestamp() - os.path.getmtime(cache)
        if age < 3600 * 6:
            df = read_cache_csv_safe(cache)
            log.info(f"  📂 使用缓存: {cache} ({(age/3600):.1f}h 前)")
            return df.sort_values("date").reset_index(drop=True)

    df = None

    # ── 源1: Binance 公开 REST API（最稳定） ──
    df = _fetch_binance()
    if df is not None and not df.empty:
        log.info("  📡 数据源: Binance (公开API)")
    else:
        # ── 源2: Yahoo Finance ──
        df = _fetch_yahoo()
        if df is not None and not df.empty:
            log.info("  📡 数据源: Yahoo Finance")
        else:
            # ── 源3: 合成数据兜底 ──
            log.warning("  ⚠️ 全部数据源失败，使用合成数据")
            df = _synthetic_data()

    df = df.sort_values("date").reset_index(drop=True)
    df.to_csv(cache, index=False, encoding="utf-8-sig")
    log.info(f"  💾 缓存已保存: {cache} ({len(df)} 行)")
    return df


def read_cache_csv_safe(path):
    """兼容多种编码读取缓存，损坏自动删除"""
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "cp936"]
    for enc in encodings:
        try:
            return pd.read_csv(path, parse_dates=["date"], encoding=enc)
        except UnicodeDecodeError:
            continue
    # 编码全部失败 → 删除损坏缓存
    os.remove(path)
    raise FileNotFoundError(f"缓存编码损坏已删除: {path}")


def _fetch_binance():
    """从 Binance 公开 API 拉取 BTCUSDT 日线（稳定分页）"""
    try:
        import urllib.request
        headers = {"User-Agent": "Mozilla/5.0"}

        start_ts = int(pd.Timestamp("2013-01-01").timestamp() * 1000)
        all_bars = []

        while True:
            url = (
                "https://api.binance.com/api/v3/klines"
                f"?symbol=BTCUSDT&interval=1d&limit=1000&startTime={start_ts}"
            )
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                bars = json.loads(resp.read().decode())

            if not bars:
                break

            all_bars.extend(bars)
            start_ts = bars[-1][0] + 1
            time.sleep(0.3)

            if bars[-1][0] > int(time.time() * 1000) - 86400000:
                break

        if not all_bars:
            return None

        df = pd.DataFrame(all_bars, columns=[
            "ts","open","high","low","close","volume",
            "close_time","qav","ntrades","tbbav","tbqav","ignore"
        ])
        df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.tz_localize(None)
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        return df[["date","open","high","low","close","volume"]].dropna(subset=["close"])
    except Exception as e:
        log.warning(f"  ⚠️ Binance 失败: {e}")
        return None


def _fetch_yahoo():
    try:
        import yfinance as yf
        t = yf.Ticker("BTC-USD")
        df = t.history(start="2013-01-01", auto_adjust=True)
        if df.empty:
            return None
        df = df.reset_index()[["Date","Open","High","Low","Close","Volume"]]
        df.columns = ["date","open","high","low","close","volume"]
        return df
    except Exception as e:
        log.warning(f"  ⚠️ Yahoo 失败: {e}")
        return None


def _synthetic_data():
    dates = pd.date_range("2013-01-01", datetime.now().strftime("%Y-%m-%d"))
    n = len(dates)
    np.random.seed(42)
    rets = np.random.normal(0.0015, 0.04, n)
    price = 100 * np.cumprod(1 + rets)
    return pd.DataFrame({
        "date": dates,
        "open": price * 0.99,
        "high": price * 1.02,
        "low": price * 0.98,
        "close": price,
        "volume": np.random.lognormal(10, 1, n),
    })


# ═════════════════════════════════════════════════════════
#  2. AHR999 计算（防御式除法）
# ═════════════════════════════════════════════════════════
def compute_ahr999(df):
    c = config.Config()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    df["ma200"] = df["close"].rolling(200, min_periods=30).mean()
    genesis = pd.Timestamp("2009-01-03")
    df["days"] = ((df["date"] - genesis).dt.days).astype(float)
    df["power_price"] = c.POWER_LAW_A * df["days"] ** c.POWER_LAW_B

    df["ahr999"] = np.where(
        (df["ma200"] > 0) & (df["power_price"] > 0),
        (df["close"] / df["ma200"]) * (df["close"] / df["power_price"]),
        np.nan
    )

    df["fair_value"] = df["ma200"]
    df["deviation_pct"] = (df["close"] - df["fair_value"]) / df["fair_value"] * 100
    return df


# ═════════════════════════════════════════════════════════
#  3. 异常检测 / 区间 / 买卖 / 导出（略，保持你原逻辑）
# ═════════════════════════════════════════════════════════
# （此处省略你原有 detect_anomalies / assign_zone / apply_trades / export 等函数，
#  因为这些部分与编码问题无关，可直接保留你现有版本）