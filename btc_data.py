import pandas as pd
import numpy as np
import os

def _read_csv_robust(path: str) -> pd.DataFrame:
    """
    兼容 UTF-8 / GBK / GB2312 / UTF-8-BOM 编码的 CSV 读取
    """
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312"]

    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        "utf-8",
        b"",
        0,
        1,
        "❌ 无法识别 CSV 编码，请用 UTF-8 或 GBK 重新保存 btc_cache.csv"
    )


def _to_numeric_safe(s):
    """
    安全转数字：去掉逗号、百分号、K/M 单位
    """
    if s is None:
        return np.nan

    s = str(s).strip()
    s = s.replace(",", "").replace("，", "")

    multiplier = 1
    if s.endswith("%"):
        s = s[:-1]
        multiplier = 0.01
    if s.endswith("K"):
        s = s[:-1]
        multiplier *= 1_000
    elif s.endswith("M"):
        s = s[:-1]
        multiplier *= 1_000_000

    try:
        return float(s) * multiplier
    except ValueError:
        return np.nan


def load_and_clean_btc_data(src_path: str = "btc_cache.csv") -> pd.DataFrame:
    """
    读取并清洗 BTC 日线 CSV
    返回 DataFrame，index=日期，包含 open/high/low/close/volume
    """

    if not os.path.exists(src_path):
        raise FileNotFoundError(f"❌ 找不到数据文件: {src_path}")

    df = _read_csv_robust(src_path)

    # ---------- 1. 自动识别日期列 ----------
    date_col = None
    for col in df.columns:
        if col.lower() in ["日期", "date", "time", "timestamp", "时间"]:
            date_col = col
            break

    if date_col is None:
        raise ValueError(
            f"❌ 找不到日期列，现有列: {list(df.columns)}"
        )

    df["日期"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["日期"])
    df = df.set_index("日期").sort_index()
    df.index.name = "日期"

    # ---------- 2. 自动识别 OHLC 列 ----------
    col_map = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in ["open", "开盘", "开盘价"]:
            col_map[col] = "open"
        elif key in ["high", "最高", "最高价"]:
            col_map[col] = "high"
        elif key in ["low", "最低", "最低价"]:
            col_map[col] = "low"
        elif key in ["close", "收盘", "收盘价", "价格", "现价"]:
            col_map[col] = "close"
        elif key in ["volume", "成交量", "vol"]:
            col_map[col] = "volume"

    df = df.rename(columns=col_map)

    # ---------- 3. 数值清洗 ----------
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = df[col].apply(_to_numeric_safe)
        else:
            # 缺失 OHLC 用 close 补齐
            if "close" in df.columns:
                df[col] = df["close"]

    df = df[["open", "high", "low", "close", "volume"]]
    df = df.dropna(subset=["close"])

    # ---------- 4. 去重 + 日级重采样 ----------
    df = df[~df.index.duplicated(keep="last")]
    df = df.resample("D").last()
    df["close"] = df["close"].ffill()

    print(
        f"✅ 数据加载完成: {len(df)} 行 "
        f"({df.index.min().strftime('%Y-%m-%d')} → {df.index.max().strftime('%Y-%m-%d')})"
    )

    return df
