import os
import pandas as pd
import numpy as np


def _read_csv_robust(src_path):
    """
    兼容 UTF-8 / GBK / GB2312 编码的 CSV 读取
    """
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312"]

    for enc in encodings:
        try:
            return pd.read_csv(src_path, encoding=enc)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        "utf-8",
        b"",
        0,
        1,
        "❌ 无法识别 CSV 编码，请尝试用 UTF-8 或 GBK 重新保存 btc_cache.csv"
    )


def _to_numeric_safe(x):
    """
    把可能带逗号、单位后缀的数字转成 float
    例如:
    64,303.60
    41.71K
    1.2M
    """
    if pd.isna(x):
        return np.nan

    s = str(x).strip().replace(",", "")

    if not s:
        return np.nan

    multiplier = 1
    if s.endswith("K"):
        s = s[:-1]
        multiplier *= 1_000
    elif s.endswith("M"):
        s = s[:-1]
        multiplier *= 1_000_000
    elif s.endswith("B"):
        s = s[:-1]
        multiplier *= 1_000_000_000

    try:
        return float(s) * multiplier
    except ValueError:
        return np.nan


def _parse_chinese_date_series(s: pd.Series) -> pd.Series:
    """
    专门处理中文日期格式，例如：
    2026年8月7日
    2026年08月07日
    """
    cleaned = s.astype(str).str.strip()

    # 先尝试标准中文日期格式
    result = pd.to_datetime(
        cleaned,
        format="%Y年%m月%d日",
        errors="coerce"
    )

    # 如果还有没解析出来的，尝试其他常见格式
    mask = result.isna()

    if mask.any():
        result2 = pd.to_datetime(
            cleaned[mask],
            errors="coerce"
        )
        result.loc[mask] = result2

    return result


def load_and_clean_btc_data(src_path: str = "btc_cache.csv") -> pd.DataFrame:
    """
    读取并清洗 BTC CSV 数据。
    适配你的格式：
    日期, 收盘, 开盘, 高, 低, 交易量, 涨跌幅
    日期示例：2026年8月7日
    """

    if not os.path.exists(src_path):
        raise FileNotFoundError(f"❌ 找不到数据文件: {src_path}")

    df = _read_csv_robust(src_path)

    print("📂 CSV 原始列名:", list(df.columns))

    if not df.empty:
        print("📄 CSV 前 3 行:")
        print(df.head(3).to_string())

    # ---------- 1. 找日期列 ----------
    date_col = None
    for col in df.columns:
        if str(col).strip().lower() in ["日期", "date", "time", "timestamp", "时间", "datetime"]:
            date_col = col
            break

    if date_col is None:
        raise ValueError(
            f"❌ 找不到日期列。现有列名: {list(df.columns)}，"
            f"请确认包含 日期/date/time/timestamp/datetime 之一"
        )

    print("📅 日期列样本:")
    print(df[date_col].head(10).to_string())

    # ---------- 2. 解析日期 ----------
    df["日期"] = _parse_chinese_date_series(df[date_col])

    bad_dates = df["日期"].isna().sum()

    if bad_dates == len(df):
        samples = df[date_col].head(10).tolist()
        raise ValueError(
            "❌ 日期列全部解析失败，请检查 CSV 日期格式。\n"
            f"样本值: {samples}"
        )

    if bad_dates > 0:
        print(f"⚠️ 有 {bad_dates} 行日期解析失败，已丢弃")
        df = df.dropna(subset=["日期"])

    df = df.set_index("日期").sort_index()
    df.index.name = "日期"

    # ---------- 3. 识别并统一 OHLCV 列 ----------
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
        elif key in ["volume", "交易量", "成交量", "vol"]:
            col_map[col] = "volume"

    df = df.rename(columns=col_map)

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = df[col].apply(_to_numeric_safe)
        else:
            if "close" in df.columns:
                df[col] = df["close"]

    keep_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep_cols]

    df = df.dropna(subset=["close"])

    # ---------- 4. 去重 + 日级重采样 ----------
    df = df[~df.index.duplicated(keep="last")]
    df = df.resample("D").last()
    df["close"] = df["close"].ffill()

    if len(df) == 0:
        raise ValueError("❌ 清洗后没有任何有效数据，请检查 CSV 内容和列名")

    min_date = df.index.min()
    max_date = df.index.max()

    min_str = min_date.strftime("%Y-%m-%d") if pd.notna(min_date) else "未知"
    max_str = max_date.strftime("%Y-%m-%d") if pd.notna(max_date) else "未知"

    print(f"✅ 数据加载完成: {len(df)} 行 ({min_str} → {max_str})")

    return df
