import pandas as pd
import numpy as np

from btc_data import load_and_clean_btc_data

# ═════════════════════════════════════════════════════════
# 稳定版 AHR999 计算（不依赖创世块天数，避免 Index 报错）
# ═════════════════════════════════════════════════════════

def calculate_sma200(df: pd.DataFrame) -> pd.DataFrame:
    """200 日简单移动平均（定投成本线）"""
    df["sma200"] = df["close"].rolling(window=200, min_periods=200).mean()
    return df

def calculate_trend_line(df: pd.DataFrame) -> pd.DataFrame:
    """
    用对数线性回归拟合长期趋势，替代容易出错的幂律公式。
    - 对索引编号做 log
    - 用 numpy 多项式拟合，完全规避 pandas Index 问题
    """
    n = len(df)
    if n < 200:
        df["index_growth_val"] = np.nan
        return df

    # 用 1~n 的序号做自变量（稳定、无时区/天数问题）
    x = np.arange(1, n + 1, dtype=float)
    y = df["close"].values.astype(float)

    # 只对有效价格做拟合
    valid = ~np.isnan(y)
    x_valid = x[valid]
    y_valid = y[valid]

    # 对数空间线性拟合：log(y) = a * x + b
    log_y = np.log(y_valid)
    coeffs = np.polyfit(x_valid, log_y, deg=1)  # [a, b]
    a, b = coeffs[0], coeffs[1]

    trend_log = a * x + b
    df["index_growth_val"] = np.exp(trend_log)

    return df

def calculate_ahr999(df: pd.DataFrame) -> pd.DataFrame:
    df = calculate_sma200(df)
    df = calculate_trend_line(df)

    # 安全计算 AHR999
    mask = (
        df["sma200"].notna() &
        df["index_growth_val"].notna() &
        (df["sma200"] > 0) &
        (df["index_growth_val"] > 0)
    )

    df["ahr999"] = np.where(
        mask,
        (df["close"] / df["sma200"]) *
        (df["close"] / df["index_growth_val"]),
        np.nan
    )

    df["deviation_pct"] = np.where(
        df["sma200"] > 0,
        (df["close"] - df["sma200"]) / df["sma200"] * 100,
        np.nan
    )

    df["change_pct"] = df["close"].pct_change() * 100
    return df

def assign_zone(df: pd.DataFrame) -> pd.DataFrame:
    conditions = [
        df["ahr999"] < 0.45,
        df["ahr999"] < 1.0,
        df["ahr999"] < 1.4,
        df["ahr999"] >= 1.4,
    ]
    choices = ["极度低估", "低估", "正常", "高估"]
    df["zone"] = np.select(conditions, choices, default="未知")
    return df

# ═════════════════════════════════════════════════════════
# 流水线入口
# ═════════════════════════════════════════════════════════

def run_pipeline(src_path: str = "btc_cache.csv") -> pd.DataFrame:
    print("\n" + "=" * 60)
    print("  ₿ BTC AHR999 Pipeline（✅ 稳定最终版）")
    print("=" * 60 + "\n")

    df = load_and_clean_btc_data(src_path)
    df = calculate_ahr999(df)
    df = assign_zone(df)

    latest = df.dropna(subset=["ahr999"]).iloc[-1]

    print(f"\n📅 最新日期: {latest.name.strftime('%Y-%m-%d')}")
    print(f"📈 现价: ${latest['close']:,.2f}")
    print(f"📐 SMA200: ${latest['sma200']:,.2f}")
    print(f"🌐 趋势估值: ${latest['index_growth_val']:,.2f}")
    print(f"📐 AHR999: {latest['ahr999']:.4f}")
    print(f"🏷️ 区间: {latest['zone']}")
    print(f"📊 偏离幅度: {latest['deviation_pct']:.2f}%")

    return df

if __name__ == "__main__":
    run_pipeline()
