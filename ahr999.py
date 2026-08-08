import pandas as pd
import numpy as np

from btc_data import load_and_clean_btc_data

# ═════════════════════════════════════════════════════════
# AHR999 计算（100% 对齐 TradingView 公式）
# ═════════════════════════════════════════════════════════

def calculate_sma200(df: pd.DataFrame) -> pd.DataFrame:
    df["sma200"] = df["close"].rolling(window=200, min_periods=1).mean()
    return df

def calculate_power_law(df: pd.DataFrame) -> pd.DataFrame:
    """
    幂律估值: y = 10^(a * log10(x) + b)
    x = 天数（从 2009-01-03 起算）
    """
    genesis = pd.Timestamp("2009-01-03")
    days = (df.index - genesis).days + 1
    a, b = 2.48, -17.02
    df["index_growth_val"] = 10 ** (a * np.log10(days) + b)
    return df

def calculate_ahr999(df: pd.DataFrame) -> pd.DataFrame:
    df = calculate_sma200(df)
    df = calculate_power_law(df)

    # TV: ahr999 = close / sma200 * (close / indexGrowthVal)
    df["ahr999"] = (
        df["close"] / df["sma200"] *
        df["close"] / df["index_growth_val"]
    )

    # 偏离幅度（相对 SMA200）
    df["deviation_pct"] = (
        (df["close"] - df["sma200"]) / df["sma200"] * 100
    )

    # 日涨跌幅
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
    print("  ₿ BTC AHR999 Pipeline（本地数据版）")
    print("=" * 60 + "\n")

    df = load_and_clean_btc_data(src_path)
    df = calculate_ahr999(df)
    df = assign_zone(df)

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