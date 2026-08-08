import pandas as pd


def load_and_clean_btc_data(src_path="btc_cache.csv") -> pd.DataFrame:
    """
    读取本地 BTC CSV 数据并清洗。
    假设 CSV 至少包含:
    - 日期列，列名可以是 日期 / date / Date / time / Time
    - 价格列，列名可以是 close / Close / 收盘价 / 现价
    """

    df = pd.read_csv(src_path)

    # 自动识别日期列
    date_col = None
    for col in df.columns:
        if col.lower() in ["日期", "date", "time", "timestamp", "时间"]:
            date_col = col
            break

    if date_col is None:
        raise ValueError("❌ 找不到日期列，请确认 CSV 包含 日期/date/time/timestamp 列")

    df["日期"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["日期"])
    df = df.set_index("日期").sort_index()

    # 自动识别 close 列
    close_col = None
    for col in df.columns:
        if col.lower() in ["close", "收盘价", "现价", "price", "价格"]:
            close_col = col
            break

    if close_col is None:
        raise ValueError("❌ 找不到价格列，请确认 CSV 包含 close/收盘价/现价/price 列")

    df = df[[close_col]].copy()
    df = df.rename(columns={close_col: "close"})
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])

    # 去重并按日重采样，防止重复日期或缺失日期
    df = df[~df.index.duplicated(keep="last")]
    df = df.resample("D").last()
    df["close"] = df["close"].ffill()

    return df
