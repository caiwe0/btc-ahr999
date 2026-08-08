import pandas as pd
import numpy as np

from btc_data import load_and_clean_btc_data

# ═════════════════════════════════════════════════════════
# AHR999 计算（✅ 修复 Index.clip 错误 + 幂律数值稳定）
# ═════════════════════════════════════════════════════════

def calculate_sma200(df: pd.DataFrame) -> pd.DataFrame:
    """
    SMA200：至少 200 个交易日才有效
    """
    df["sma200"] = df["close"].rolling(window=200, min_periods=200).mean()
    return df


def calculate_power_law(df: pd.DataFrame) -> pd.DataFrame:
    """
    幂律估值（AHR999 专用）
    y = 10^(a * log10(x) + b)
    x = 距比特币创世块的天数

    系数来源：ahr999 社区常用拟合
    """
    genesis = pd.Timestamp("2009-01-03")

    # ✅ 转为 numpy array，避免 Index 没有 clip()
    days = np.asarray((df.index - genesis).days, dtype=float) + 1.0
    days = np.where(days < 1, 1.0, days)

    # ✅ 九神 AHR999 标准系数
    a = 2.48
    b = -17.02

    df["index_growth_val"] = 10 ** (a * np.log10(days) + b)
    return df


def calculate_ahr999(df: pd.DataFrame) -> pd.DataFrame:
    df = calculate_sma200(df)
    df = calculate_power_law(df)

    # ✅ 安全掩码，防止除 0 或 NaN
    mask = (
        df["sma200"].notna() &
        df["index_growth_val"].notna() &
        (df["sma200"] > 0) &
        (df["index_growth_val"] > 0)
    )

    # AHR999 = (Price / 200DMA) × (Price / PowerLaw)
    df["ahr999"] = np.where(
        mask,
        (df["close"] / df["sma200"]) *
        (df["close"] / df["index_growth_val"]),
        np.nan
    )

    # 偏离幅度（相对 SMA200）
    df["deviation_pct"] = np.where(
        df["sma200"] > 0,
        (df["close"] - df["sma200"]) / df["sma200"] * 100,
        np.nan
    )

    # 日涨跌幅
    df["change_pct"] = df["close"].pct_change() * 100

    return df


def assign_zone(df: pd.DataFrame) -> pd.DataFrame:
    """
    AHR999 区间划分（九神标准）
    """
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
    print("  ₿ BTC AHR999 Pipeline（✅ 最终稳定版）")
    print("=" * 60 + "\n")

    df = load_and_clean_btc_data(src_path)
    df = calculate_ahr999(df)
    df = assign_zone(df)

    # 取最新有效数据
    latest = df.dropna(subset=["ahr999"]).iloc[-1]

    print(f"\n📅 最新日期: {latest.name.strftime('%Y-%m-%d')}")
    print(f"📈 现价: ${latest['close']:,.2f}")
    print(f"📐 SMA200: ${latest['sma200']:,.2f}")
    print(f"🌐 幂律估值: ${latest['index_growth_val']:,.2f}")
    print(f"📐 AHR999: {latest['ahr999']:.4f}")
    print(f"🏷️ 区间: {latest['zone']}")
    print(f"📊 偏离幅度: {latest['deviation_pct']:.2f}%")

    return df


if __name__ == "__main__":
    run_pipeline()
