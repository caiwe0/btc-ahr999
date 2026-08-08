import os
import numpy as np
import pandas as pd


def _read_csv_robust(src_path):
    """
    兼容 UTF-8 / UTF-8-BOM / GBK / GB2312 的 CSV 读取
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
        "❌ 无法识别 CSV 编码，请用 Excel 另存为「CSV UTF-8」或确认文件为 GBK 编码"
    )


def _to_numeric_safe(x):
    """
    把可能带 K/M/B 或逗号的数值转成 float
    """
    if pd.isna(x):
        return np.nan

    s = str(x).strip().replace(",", "")

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


def _find_date_column(df):
    """
    自动寻找日期列
    """
    candidates = ["日期", "date", "time", "timestamp", "时间", "datetime", "day"]

    for col in df.columns:
        if str(col).strip().lower() in candidates:
            return col

    # 如果列名不完全匹配，再模糊找一下
    for col in df.columns:
        low = str(col).strip().lower()
        if "date" in low or "time" in low or "day" in low or "日期" in low or "时间" in low:
            return col

    return None


def _parse_dates(series):
    """
    更稳的日期解析：
    1. 先直接解析
    2. 失败则尝试常见格式
    3. 仍失败则报错并展示样本
    """
    cleaned = series.astype(str).str.strip()

    # 先普通解析
    result = pd.to_datetime(cleaned, errors="coerce")

    # 如果大量失败，尝试常见格式
    if result.isna().mean() > 0.5:
        result = pd.to_datetime(
            cleaned,
            format="%Y-%m-%d",
            errors="coerce"
        )

    if result.isna().mean() > 0.5:
        result = pd.to_datetime(
            cleaned,
            format="%Y/%m/%d",
            errors="coerce"
        )

    if result.isna().mean() > 0.5:
        result = pd.to_datetime(
            cleaned,
            format="%d/%m/%Y",
            errors="coerce"
        )

    if result.isna().mean() > 0.5:
        result = pd.to_datetime(
            cleaned,
            format="%m/%d/%Y",
            errors="coerce"
        )

    return result


def load_and_clean_btc_data(src_path: str = "btc_cache.csv") -> pd.DataFrame:
    """
    读取并清洗 BTC CSV 数据
    返回 index=日期 的 DataFrame，包含 open/high/low/close/volume
    """

    if not os.path.exists(src_path):
        raise FileNotFoundError(f"❌ 找不到数据文件: {src_path}")

    df = _read_csv_robust(src_path)

    print("📂 CSV 原始列名:", list(df.columns))
    print("📄 CSV 前 3 行:")
    print(df.head(3).to_string())

    date_col = _find_date_column(df)

    if date_col is None:
        raise ValueError(
            f"❌ 找不到日期列。现有列名: {list(df.columns)}，"
            f"请确认包含 日期/date/time/timestamp/datetime 之一"
        )

    df["日期"] = _parse_dates(df[date_col])

    bad_dates = df["日期"].isna().sum()
    if bad_dates == len(df):
        samples = df[date_col].head(10).tolist()
        raise ValueError(
            f"❌ 日期列 '{date_col}' 全部解析失败，请检查 CSV 日期格式。\n"
            f"样本值: {samples}"
        )

    if bad_dates > 0:
        print(f"⚠️ 有 {bad_dates} 行日期解析失败，已丢弃")
        df = df.dropna(subset=["日期"])

    df = df.set_index("日期").sort_index()
    df.index.name = "日期"

    # ---------- 自动识别价格列 ----------
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

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = df[col].apply(_to_numeric_safe)
        else:
            if "close" in df.columns:
                df[col] = df["close"]

    keep_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep_cols]

    df = df.dropna(subset=["close"])

    df = df[~df.index.duplicated(keep="last")]
    df = df.resample("D").last()
    df["close"] = df["close"].ffill()

    if len(df) == 0:
        raise ValueError("❌ 清洗后没有任何有效数据，请检查 CSV 内容和列名")

    # 安全打印日期范围，避免 NaT.strftime 崩溃
    min_date = df.index.min()
    max_date = df.index.max()

    min_str = min_date.strftime("%Y-%m-%d") if pd.notna(min_date) else "未知"
    max_str = max_date.strftime("%Y-%m-%d") if pd.notna(max_date) else "未知"

    print(f"✅ 数据加载完成: {len(df)} 行 ({min_str} → {max_str})")

    return df
