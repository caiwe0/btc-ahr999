"""
BTC 数据加载模块
读取用户提供的 btc_cache.csv（中文表头、千分位逗号、K 单位、百分号）
清洗为标准化 DataFrame
"""
import re
import pandas as pd
import numpy as np

COLUMN_MAP = {
    "日期": "date",
    "收盘": "close",
    "开盘": "open",
    "高": "high",
    "低": "low",
    "交易量": "volume",
    "涨跌幅": "change_pct",
}

def _strip_quote(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s

def _coerce_numeric(raw) -> pd.Series:
    """去掉千分位逗号、百分号、K/M/B 单位后转 float"""
    s = raw.astype(str).map(_strip_quote).str.strip()
    s = s.str.replace(",", "", regex=False)
    s = s.str.replace("%", "", regex=False)

    # 处理 K / M / B 单位
    mult = pd.Series(1.0, index=s.index)
    last_char = s.str[-1].str.upper()
    mult[last_char == "K"] = 1e3
    mult[last_char == "M"] = 1e6
    mult[last_char == "B"] = 1e9

    has_unit = last_char.isin(["K", "M", "B"])
    if has_unit.any():
        s_clean = s[has_unit].str[:-1].astype(float) * mult[has_unit]
        s_out = s_clean.reindex(index=s.index)
        s_out[~has_unit] = pd.to_numeric(s[~has_unit], errors="coerce")
        return s_out.astype(float)

    return pd.to_numeric(s, errors="coerce")

def _parse_date(s: str) -> pd.Timestamp | None:
    """解析 '2026年8月7日' 格式"""
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # 兜底：交给 pandas
    try:
        return pd.to_datetime(s, format="mixed", errors="raise")
    except Exception:
        return None

def load_btc_data(path: str = "btc_cache.csv") -> pd.DataFrame:
    """加载并清洗 BTC 日线数据"""
    # 先按原始读取，避免引号/逗号干扰
    raw = pd.read_csv(path, header=0, dtype=str, encoding="utf-8-sig")
    raw.columns = raw.columns.str.strip()

    # 重命名
    raw = raw.rename(columns=COLUMN_MAP)

    # 逐列清洗
    df = pd.DataFrame()
    df["date"] = raw["date"].map(_parse_date)
    for c in ["open", "high", "low", "close"]:
        if c in raw.columns:
            df[c] = _coerce_numeric(raw[c])
    if "volume" in raw.columns:
        df["volume"] = _coerce_numeric(raw["volume"])
    else:
        df["volume"] = 0.0
    if "change_pct" in raw.columns:
        df["change_pct"] = _coerce_numeric(raw["change_pct"])

    # 去空、去重、排序
    df = df.dropna(subset=["date", "close"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    df["volume"] = df["volume"].fillna(0.0)

    return df

if __name__ == "__main__":
    df = load_btc_data()
    print(f"✅ 加载完成: {len(df)} 行 | {df['date'].min().date()} → {df['date'].max().date()}")
    print(df.head(3).to_string())
    print("...")
    print(df.tail(3).to_string())
