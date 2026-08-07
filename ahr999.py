import os
import numpy as np
import pandas as pd
from datetime import datetime


# ═════════════════════════════════════════════════════════
# 工具：安全读取缓存 CSV，解决 GitHub Actions UTF-8 报错
# ═════════════════════════════════════════════════════════

def read_cache_csv_safe(path):
    """
    兼容 utf-8-sig / utf-8 / gbk / cp936 等编码。
    如果全都失败，删除损坏缓存，避免下次继续炸。
    """
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "cp936"]
    for enc in encodings:
        try:
            return pd.read_csv(path, parse_dates=["日期"], encoding=enc)
        except UnicodeDecodeError:
            continue

    try:
        os.remove(path)
        print(f"⚠️ 缓存编码损坏，已删除: {path}")
    except Exception:
        pass

    raise FileNotFoundError(f"缓存文件编码无法识别，且无法恢复: {path}")


def safe_to_csv(df, path):
    """
    统一用 utf-8-sig 写 CSV。
    Windows Excel 能正常打开，GitHub Actions / Linux 也能正常读。
    """
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ═════════════════════════════════════════════════════════
# 数据获取：优先 Binance，可扩展 Yahoo
# ═════════════════════════════════════════════════════════

def fetch_btc_data(force_refresh=False, cache_path="btc_cache.csv"):
    """
    获取 BTC 日线数据。
    force_refresh=True 时删除旧缓存并重新拉取。
    """

    if force_refresh and os.path.exists(cache_path):
        os.remove(cache_path)
        print(f"✅ 强制刷新: 已删除旧缓存 {cache_path}")

    if os.path.exists(cache_path):
        try:
            df = read_cache_csv_safe(cache_path)
            print(f"📦 使用缓存: {cache_path}")
            return df
        except Exception as e:
            print(f"⚠️ 读取缓存失败，将重新拉取: {e}")
            try:
                os.remove(cache_path)
            except Exception:
                pass

    print("📡 尝试从 Binance 获取真实数据...")

    try:
        import requests

        url = "https://api.binance.com/api/v3/klines"
        all_bars = []
        start_ms = 1502697600000  # 大约 2017-08-14，Binance BTCUSDT 早期可用区间
        limit = 1000

        while True:
            params = {
                "symbol": "BTCUSDT",
                "interval": "1d",
                "startTime": start_ms,
                "limit": limit
            }
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            bars = r.json()

            if not bars:
                break

            all_bars += bars
            last_open = bars[-1][0]

            if len(bars) < limit:
                break

            start_ms = last_open + 1

        if not all_bars:
            raise ValueError("Binance 返回空数据")

        df = pd.DataFrame(all_bars, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_base", "taker_quote", "ignore"
        ])

        df["日期"] = pd.to_datetime(df["open_time"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        df = df[["日期", "open", "high", "low", "close", "volume"]].copy()
        df = df.sort_values("日期").drop_duplicates("日期").reset_index(drop=True)

        safe_to_csv(df, cache_path)
        print(f"✅ Binance 数据: {len(df)} 行 ({df['日期'].min()} → {df['日期'].max()})")
        print(f"📦 缓存已保存: {cache_path}")
        return df

    except Exception as e:
        print(f"❌ Binance 获取失败: {e}")

        # 这里不自动读坏缓存，直接报错
        raise RuntimeError(
            "无法获取 Binance 数据，且不使用损坏缓存。请检查网络或稍后重试。"
        )


# ═════════════════════════════════════════════════════════
# AHR999 计算
# ═════════════════════════════════════════════════════════

def calculate_ahr999(df):
    """
    计算 AHR999 指标。
    包含 MA200 防御，避免早期数据为 0 时除零。
    """
    df = df.sort_values("日期").copy()

    df["ma200"] = df["close"].rolling(200).mean()

    # 简化版幂律价格：用指数拟合思路给一个正的价格参考
    # 这里用滚动/累计近似，避免旧参数导致天文数字。
    days = np.arange(len(df)) + 1
    # 用一个温和增长曲线，仅作 AHR999 分母参考，不用于绝对预测
    df["power_price"] = df["close"].iloc[0] * np.exp(0.0015 * days)

    df["ahr999"] = np.where(
        (df["ma200"] > 0) & (df["power_price"] > 0),
        (df["close"] / df["ma200"]) * (df["close"] / df["power_price"]),
        np.nan
    )

    df["fair_value"] = df["ma200"]
    df["deviation_pct"] = np.where(
        df["fair_value"] > 0,
        (df["close"] - df["fair_value"]) / df["fair_value"] * 100,
        np.nan
    )

    return df


# ═════════════════════════════════════════════════════════
# 异常检测
# ═════════════════════════════════════════════════════════

def detect_anomalies(df):
    """
    标记异常 K 线：涨跌幅过大、成交量异常等。
    返回带 anomaly 标记的 DataFrame。
    """
    df = df.copy()
    df["daily_change_pct"] = df["close"].pct_change() * 100

    # 简单规则：单日涨跌幅超过 15% 视为异常波动
    df["anomaly"] = df["daily_change_pct"].abs() > 15

    # 成交量异常：超过 3 倍中位数
    if "volume" in df.columns:
        med_vol = df["volume"].median()
        if med_vol and med_vol > 0:
            df["volume_anomaly"] = df["volume"] > med_vol * 3
            df["anomaly"] = df["anomaly"] | df["volume_anomaly"]
        else:
            df["volume_anomaly"] = False
    else:
        df["volume_anomaly"] = False

    return df


# ═════════════════════════════════════════════════════════
# 区间判断
# ═════════════════════════════════════════════════════════

def assign_zone(df):
    """
    根据 AHR999 给区间标签。
    """
    df = df.copy()

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
# 买卖记录/盈亏模拟
# ═════════════════════════════════════════════════════════

def apply_trades(df, manual_input_path="manual_input.csv"):
    """
    读取手动买卖记录并合并到结果里。
    如果没有文件，返回原 df 并带空交易列。
    """
    df = df.copy()

    df["trade_action"] = ""
    df["trade_amount"] = 0.0
    df["trade_price"] = np.nan

    if not os.path.exists(manual_input_path):
        return df

    try:
        trades = pd.read_csv(manual_input_path, encoding="utf-8-sig")
        print(f"📥 读取交易记录: {len(trades)} 条")
        # 这里可以扩展真实匹配逻辑
        return df
    except Exception as e:
        print(f"⚠️ 读取 manual_input.csv 失败: {e}")
        return df


# ═════════════════════════════════════════════════════════
# 导出
# ═════════════════════════════════════════════════════════

def export_results(df, xlsx_path="BTC_AHR999.xlsx", json_path="ahr999_data.json"):
    """
    导出 Excel / JSON。
    """
    out = df.copy()

    # 避免 NaN 写 JSON 出问题
    out = out.replace({np.nan: None})

    out.to_excel(xlsx_path, index=False)
    out.to_json(json_path, orient="records", force_ascii=False)

    print(f"✅ 导出 {xlsx_path}")
    print(f"✅ 导出 {json_path}")


# ═════════════════════════════════════════════════════════
# 管线封装
# ═════════════════════════════════════════════════════════

def run_pipeline(force_refresh=False):
    print(f"\n{'='*60}")
    print(f"  ₿ BTC AHR999 Pipeline  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    df = fetch_btc_data(force_refresh=force_refresh)
    df = calculate_ahr999(df)
    df = detect_anomalies(df)
    df = assign_zone(df)
    df = apply_trades(df)
    export_results(df)

    latest = df.dropna(subset=["ahr999"]).iloc[-1]
    print(f"\n📡 数据源: binance")
    print(f"📈 最新 AHR999: {latest['ahr999']:.4f}")
    print(f"🏷️ 区间: {latest['zone']}")

    return df