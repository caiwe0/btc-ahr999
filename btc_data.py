import pandas as pd
import os

def load_and_clean_btc_data(src_path="btc_cache.csv") -> pd.DataFrame:
    """
    读取并清洗 BTC 日线 CSV。
    支持：中文表头、千分位逗号、GBK/UTF-8、百分号、K/M 单位等。
    返回列：open / high / low / close / volume，index=日期。
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"❌ 找不到数据文件: {src_path}")

    # 尝试多种编码
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb2312", "cp936"):
        try:
            df = pd.read_csv(src_path, encoding=enc)
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    else:
        raise RuntimeError(f"❌ 无法读取 {src_path}，请检查编码和格式")

    # 统一列名（兼容中英文）
    rename_map = {}
    for c in df.columns:
        s = str(c).strip().lower()
        if s in ("date", "日期", "时间", "datetime"):
            rename_map[c] = "日期"
        elif s in ("open", "开盘", "开盘价"):
            rename_map[c] = "open"
        elif s in ("high", "最高", "最高价"):
            rename_map[c] = "high"
        elif s in ("low", "最低", "最低价"):
            rename_map[c] = "low"
        elif s in ("close", "收盘", "收盘价", "price"):
            rename_map[c] = "close"
        elif s in ("volume", "成交量", "vol"):
            rename_map[c] = "volume"
    df = df.rename(columns=rename_map)

    # 必须有日期和收盘价
    if "日期" not in df.columns or "close" not in df.columns:
        raise ValueError(
            f"❌ CSV 缺少必要列。现有列: {list(df.columns)}，"
            "需要包含：日期、开盘、最高、最低、收盘（或英文 OHLC）"
        )

    # 解析日期
    df["日期"] = pd.to_datetime(df["日期"], infer_datetime_format=True, errors="coerce")
    df = df.dropna(subset=["日期", "close"]).set_index("日期").sort_index()

    # 数值清洗：去千分位逗号、去百分号、去 K/M 单位
    def to_num(s):
        if s is None:
            return pd.NA
        s = str(s).strip().replace(",", "").replace("，", "")
        mult = 1
        if s.endswith("%"):
            s = s[:-1]
            mult = 0.01
        if s.endswith("K"):
            s = s[:-1]
            mult *= 1000
        elif s.endswith("M"):
            s = s[:-1]
            mult *= 1_000_000
        try:
            return float(s) * mult
        except ValueError:
            return pd.NA

    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = df[col].apply(to_num)
        else:
            # 缺失的 OHLC 用 close 补齐
            df[col] = df["close"]

    df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    df.index.name = "日期"

    print(f"✅ 数据加载完成: {len(df)} 行  ({df.index.min()} → {df.index.max()})")
    return df