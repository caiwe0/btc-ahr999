"""
ahr999.py
BTC AHR999 定投指标 · 核心计算模块

功能：
  1. 多源数据获取 (Investing.com → Stooq → Yahoo 三级降级)
  2. AHR999 指标计算 (防御式除法，避免 NaN/0)
  3. 异常 K 线检测
  4. 区间标签 (极度低估 / 定投区 / 合理 / 偏高 / 高估)
  5. 买卖记录合并 + 盈亏计算
  6. 导出 Excel / JSON / HTML data.js

使用：
  from ahr999 import run_pipeline
  df = run_pipeline(force_refresh=False)
"""

import os
import json
import time
import logging
import datetime
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════
#  配置
# ═════════════════════════════════════════════════════════

CACHE_PATH = "btc_cache.csv"
PAGES_DIR = "_site"

# 幂律参数（用历史关键点拟合，覆盖到 2026+）
# price ≈ A * days^B
POWER_LAW_A = 4.201e-13
POWER_LAW_B = 4.5985

# AHR999 区间阈值
ZONE_EXTREME_LOW = 0.45    # < 0.45 极度低估
ZONE_DCA = 0.80            # 0.45~0.8 定投区
ZONE_REASONABLE = 1.20      # 0.8~1.2 合理
ZONE_HIGH = 2.00            # 1.2~2.0 偏高
# > 2.0 高估

# 异常检测阈值
ANOMALY_CHANGE_PCT = 15.0   # 单日涨跌幅超 15% 视为异常
ANOMALY_VOL_MULTIPLE = 3.0   # 成交量超中位数 3 倍视为异常

# ═════════════════════════════════════════════════════════
#  1. 数据获取（多源降级）
# ═════════════════════════════════════════════════════════

def _read_cache(path=CACHE_PATH):
    """安全读取缓存，兼容多种编码"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
        try:
            return pd.read_csv(path, parse_dates=["日期"], encoding=enc)
        except UnicodeDecodeError:
            continue
    # 全失败 → 删损坏缓存
    try: os.remove(path)
    except: pass
    raise FileNotFoundError(f"缓存编码损坏已删除: {path}")


def _write_cache(df, path=CACHE_PATH):
    """统一 utf-8-sig 写入"""
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ── 源1: Investing.com ──────────────────────────────────
def _fetch_investing(start="2017-01-01", end=None, max_retry=3):
    """从 cn.investing.com 抓取 BTC/USD 日线"""
    import requests, re

    if end is None:
        end = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    def _fmt(d):
        return datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://cn.investing.com/",
        "X-Requested-With": "XMLHttpRequest",
    }

    # 获取 curr_id / smlID
    page_url = "https://cn.investing.com/crypto/bitcoin/historical-data"
    s = requests.Session()
    s.get("https://cn.investing.com/", headers=headers, timeout=15)

    last_err = None
    for attempt in range(1, max_retry + 1):
        try:
            r = s.get(page_url, headers=headers, timeout=15)
            r.raise_for_status()
            html = r.text
            break
        except Exception as e:
            last_err = e
            log.warning(f"  ⚠️ Investing.com 页面第 {attempt} 次失败: {e}")
            time.sleep(2 * attempt)
    else:
        raise last_err

    # 解析 curr_id / smlID
    m = re.search(r"window\.histDataExcessInfo\s*=\s*(\{[^;]*\})", html)
    if m:
        info = json.loads(m.group(1))
        curr_id, sml_id = info.get("curr_id"), info.get("smlID")
    else:
        m2 = re.search(r'curr_id["\']?\s*[:=]\s*["\']?(\d+)', html)
        m3 = re.search(r'smlID["\']?\s*[:=]\s*["\']?(\d+)', html)
        if not (m2 and m3):
            raise RuntimeError("Investing.com: 无法解析 curr_id/smlID")
        curr_id, sml_id = m2.group(1), m3.group(1)

    # POST 拉数据
    payload = {
        "curr_id": curr_id, "smlID": sml_id,
        "header": "null",
        "st_date": _fmt(start), "end_date": _fmt(end),
        "interval_sec": "Daily",
        "sort_col": "date", "sort_ord": "DESC",
        "action": "historical_data",
    }
    post_url = "https://cn.investing.com/instruments/HistoricalDataAjax"

    for attempt in range(1, max_retry + 1):
        try:
            r = s.post(post_url, data=payload, headers={
                **headers,
                "Referer": page_url,
                "Content-Type": "application/x-www-form-urlencoded",
            }, timeout=20)
            r.raise_for_status()
            break
        except Exception as e:
            last_err = e
            log.warning(f"  ⚠️ Investing.com POST 第 {attempt} 次失败: {e}")
            time.sleep(2 * attempt)
    else:
        raise last_err

    # 解析 HTML 表格
    import io as _io
    dfs = pd.read_html(_io.StringIO(r.text))
    if not dfs:
        raise RuntimeError("Investing.com: 返回空表格")
    df = dfs[0]

    # 列名标准化
    rename = {}
    for c in df.columns:
        s = str(c).strip()
        if "日期" in s: rename[c] = "日期"
        elif "开盘" in s: rename[c] = "open"
        elif "高" in s: rename[c] = "high"
        elif "低" in s: rename[c] = "low"
        elif "收盘" in s or s == "价格": rename[c] = "close"
        elif "交易" in s or "成交量" in s: rename[c] = "volume"
    df = df.rename(columns=rename)

    if "日期" not in df.columns or "close" not in df.columns:
        raise RuntimeError(f"Investing.com 列解析失败: {list(df.columns)}")

    df["日期"] = pd.to_datetime(df["日期"], infer_datetime_format=True, errors="coerce")
    df = df.dropna(subset=["日期", "close"])
    for c in ("open", "high", "low", "close", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(",", "").str.replace("-", "0"),
                errors="coerce"
            )

    # 缺失 OHLC 用 close 填
    for c in ("open", "high", "low"):
        if c not in df.columns:
            df[c] = df["close"]
        else:
            df[c] = df[c].fillna(df["close"])

    df = df.sort_values("日期").drop_duplicates("日期").reset_index(drop=True)
    log.info(f"  ✅ Investing.com: {len(df)} 行 "
             f"({df['日期'].min().date()} → {df['日期'].max().date()})")
    return df[["日期", "open", "high", "low", "close", "volume"]]


# ── 源2: Stooq ──────────────────────────────────────────
def _fetch_stooq(start="2017-01-01", end=None):
    """Stooq 免费 CSV，极稳定"""
    import requests, io
    if end is None:
        end = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    def _d(d):
        return datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%Y%m%d")

    url = f"https://stooq.com/q/d/l/?s=btcusd&d1={_d(start)}&d2={_d(end)}&i=d"
    headers = {"User-Agent": "Mozilla/5.0 BTC-AHR999/1.0"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip().lower() for c in df.columns]
    rename = {"date": "日期", "open": "open", "high": "high",
             "low": "low", "close": "close", "volume": "volume"}
    df = df.rename(columns=rename)

    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df = df.dropna(subset=["日期", "close"])
    for c in ("open", "high", "low", "close", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    for c in ("open", "high", "low"):
        if c not in df.columns:
            df[c] = df["close"]
        else:
            df[c] = df[c].fillna(df["close"])

    df = df.sort_values("日期").drop_duplicates("日期").reset_index(drop=True)
    log.info(f"  ✅ Stooq: {len(df)} 行 "
             f"({df['日期'].min().date()} → {df['日期'].max().date()})")
    return df[["日期", "open", "high", "low", "close", "volume"]]


# ── 源3: Yahoo Finance ──────────────────────────────────
def _fetch_yahoo(start="2017-01-01", end=None):
    """Yahoo Finance 兜底"""
    import yfinance as yf
    if end is None:
        end = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    log.info("  📡 Yahoo Finance BTC-USD 兜底...")
    data = yf.download("BTC-USD", start=start, end=end,
                       interval="1d", progress=False, auto_adjust=False)
    if data.empty:
        raise RuntimeError("Yahoo 返回空数据")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.rename(columns={"Open": "open", "High": "high",
                                "Low": "low", "Close": "close",
                                "Volume": "volume"})
    data = data.reset_index()
    if "Date" in data.columns and "日期" not in data.columns:
        data = data.rename(columns={"Date": "日期"})

    data["日期"] = pd.to_datetime(data["日期"]).dt.normalize()
    data = data.dropna(subset=["日期", "close"])
    for c in ("open", "high", "low", "close", "volume"):
        if c in data.columns:
            data[c] = pd.to_numeric(data[c], errors="coerce")

    for c in ("open", "high", "low"):
        if c not in data.columns:
            data[c] = data["close"]
        else:
            data[c] = data[c].fillna(data["close"])

    data = data.sort_values("日期").drop_duplicates("日期").reset_index(drop=True)
    log.info(f"  ✅ Yahoo: {len(data)} 行 "
             f"({data['日期'].min().date()} → {data['日期'].max().date()})")
    return data[["日期", "open", "high", "low", "close", "volume"]]


# ── 主入口 ──────────────────────────────────────────────
def fetch_btc_data(force_refresh=False, start="2017-01-01", end=None):
    """
    三级降级：Investing.com → Stooq → Yahoo
    返回标准化 DataFrame
    """
    if end is None:
        end = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    # 强制刷新：删旧缓存
    if force_refresh and os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
        log.info(f"  🗑️ 强制刷新: 已删除旧缓存 {CACHE_PATH}")

    # 缓存命中（6 小时内）
    if not force_refresh and os.path.exists(CACHE_PATH):
        age_h = (datetime.datetime.now().timestamp() -
                 os.path.getmtime(CACHE_PATH)) / 3600
        if age_h < 6:
            try:
                df = _read_cache()
                log.info(f"  📦 使用缓存: {CACHE_PATH} ({age_h:.1f}h 前, {len(df)} 行)")
                return df
            except Exception as e:
                log.warning(f"  ⚠️ 读缓存失败: {e}")
                try: os.remove(CACHE_PATH)
                except: pass

    # 依次尝试数据源
    errors = []
    sources = [
        ("Investing.com", _fetch_investing),
        ("Stooq",         _fetch_stooq),
        ("Yahoo",         _fetch_yahoo),
    ]

    for name, func in sources:
        try:
            log.info(f"  📡 尝试 {name}...")
            df = func(start=start, end=end)
            _write_cache(df)
            log.info(f"  💾 缓存已保存: {CACHE_PATH} ({len(df)} 行)")
            return df
        except Exception as e:
            errors.append(f"{name}: {e}")
            log.warning(f"  ❌ {name} 失败: {e}")

    raise RuntimeError("全部数据源失败:\n  " + "\n  ".join(errors))


# ═════════════════════════════════════════════════════════
#  2. AHR999 计算（防御式）
# ═════════════════════════════════════════════════════════

def calculate_ahr999(df):
    """计算 AHR999 / MA200 / 幂律价 / 偏离度"""
    df = df.copy().sort_values("日期").reset_index(drop=True)

    # 200 日均价（定投成本）
    df["ma200"] = df["close"].rolling(200, min_periods=30).mean()

    # 幂律拟合价（简化版，用累计对数均值）
    valid = df["close"] > 0
    df["_log"] = np.where(valid, np.log(df["close"]), np.nan)
    df["_cum_log_mean"] = df["_log"].expanding().mean()
    df["power_price"] = np.exp(df["_cum_log_mean"])

    # AHR999 = (价格/MA200) * (价格/幂律价)  ← 防御除零
    df["ahr999"] = np.where(
        (df["ma200"] > 0) & (df["power_price"] > 0),
        (df["close"] / df["ma200"]) * (df["close"] / df["power_price"]),
        np.nan
    )

    # 实价价值 = MA200
    df["fair_value"] = df["ma200"]
    df["deviation_pct"] = np.where(
        df["fair_value"] > 0,
        (df["close"] - df["fair_value"]) / df["fair_value"] * 100,
        np.nan
    )

    # 涨跌幅
    df["daily_change_pct"] = df["close"].pct_change() * 100

    # 清理临时列
    df.drop(columns=["_log", "_cum_log_mean"], inplace=True, errors="ignore")

    valid_count = df["ahr999"].notna().sum()
    log.info(f"  📐 AHR999 有效数据: {valid_count}/{len(df)} 行")
    return df


# ═════════════════════════════════════════════════════════
#  3. 异常检测
# ═════════════════════════════════════════════════════════

def detect_anomalies(df):
    """标记异常 K 线"""
    df = df.copy()

    # 涨跌幅异常
    df["price_anomaly"] = df["daily_change_pct"].abs() > ANOMALY_CHANGE_PCT

    # 成交量异常
    if "volume" in df.columns:
        med_vol = df["volume"].median()
        if med_vol and med_vol > 0:
            df["volume_anomaly"] = df["volume"] > med_vol * ANOMALY_VOL_MULTIPLE
        else:
            df["volume_anomaly"] = False
    else:
        df["volume_anomaly"] = False

    df["anomaly"] = df["price_anomaly"] | df["volume_anomaly"]
    n = df["anomaly"].sum()
    log.info(f"  🔍 异常检测完成: {n} 根异常K线")
    return df


# ═════════════════════════════════════════════════════════
#  4. 区间标签
# ═════════════════════════════════════════════════════════

def assign_zone(df):
    """根据 AHR999 值给区间标签"""
    df = df.copy()

    def _zone(x):
        if pd.isna(x): return "数据不足"
        if x < ZONE_EXTREME_LOW: return "极度低估"
        if x < ZONE_DCA: return "定投区"
        if x < ZONE_REASONABLE: return "合理区"
        if x < ZONE_HIGH: return "偏高"
        return "高估"

    df["zone"] = df["ahr999"].apply(_zone)

    # 异常 + 区间 组合标签
    def _combo(row):
        z = row["zone"]
        if row.get("anomaly"):
            if z == "极度低估": return "极度低估+异常"
            if z in ("偏高", "高估"): return "高估+异常"
            return "合理偏高+异常"
        return z

    df["zone_combo"] = df.apply(_combo, axis=1)
    return df


# ═════════════════════════════════════════════════════════
#  5. 买卖记录 + 盈亏
# ═════════════════════════════════════════════════════════

def apply_trades(df, trades_path="manual_input.csv", fee_rate=0.001):
    """
    读取 manual_input.csv 合并到主表，计算持仓/均价/盈亏。
    支持列：日期, 操作(buy/sell), 价格, 数量, 金额, 手续费
    """
    df = df.copy()
    df["trade_action"] = ""
    df["trade_price"] = np.nan
    df["trade_amount"] = 0.0
    df["trade_qty"] = 0.0
    df["fee_paid"] = 0.0
    df["realized_pnl"] = 0.0
    df["hold_qty"] = 0.0
    df["hold_avg"] = np.nan

    if not os.path.exists(trades_path):
        log.info(f"  📭 无买卖记录文件: {trades_path}")
        return df

    try:
        t = pd.read_csv(trades_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        t = pd.read_csv(trades_path, encoding="gbk")

    log.info(f"  📥 读取交易记录: {len(t)} 条")

    # 标准化列名
    t.columns = [str(c).strip().lower() for c in t.columns]
    rename = {}
    for c in t.columns:
        if "日期" in c or c == "date": rename[c] = "日期"
        elif "操作" in c or c in ("action", "type"): rename[c] = "action"
        elif "价格" in c or c == "price": rename[c] = "price"
        elif "数量" in c or c in ("qty", "amount", "数量"): rename[c] = "qty"
        elif "金额" in c or c == "value": rename[c] = "amount"
        elif "手续费" in c or c == "fee": rename[c] = "fee"
    t = t.rename(columns=rename)

    t["日期"] = pd.to_datetime(t["日期"], errors="coerce")
    t = t.dropna(subset=["日期"]).sort_values("日期")

    # FIFO 模拟
    hold_qty = 0.0
    hold_cost = 0.0  # 总持仓成本
    realized = 0.0

    for _, row in t.iterrows():
        date = row["日期"]
        action = str(row.get("action", "")).strip().lower()
        price = pd.to_numeric(row.get("price"), errors="coerce")
        qty = pd.to_numeric(row.get("qty"), errors="coerce")
        amount = pd.to_numeric(row.get("amount"), errors="coerce")
        fee = pd.to_numeric(row.get("fee"), errors="coerce")

        if pd.isna(price) and not pd.isna(amount) and not pd.isna(qty) and qty != 0:
            price = amount / qty
        if pd.isna(fee): fee = 0.0

        mask = df["日期"] == date

        if action in ("buy", "买入", "b"):
            cost = price * qty * (1 + fee_rate) + fee
            hold_qty += qty
            hold_cost += cost
            if hold_qty > 0:
                avg = hold_cost / hold_qty
            else:
                avg = 0
            df.loc[mask, "trade_action"] = "买入"
            df.loc[mask, "trade_price"] = price
            df.loc[mask, "trade_qty"] = qty
            df.loc[mask, "trade_amount"] = price * qty
            df.loc[mask, "fee_paid"] = fee

        elif action in ("sell", "卖出", "s"):
            if hold_qty > 0:
                sell_qty = min(qty, hold_qty)
                avg_cost = hold_cost / hold_qty
                realized += (price - avg_cost) * sell_qty - fee
                hold_cost = avg_cost * (hold_qty - sell_qty)
                hold_qty -= sell_qty
            df.loc[mask, "trade_action"] = "卖出"
            df.loc[mask, "trade_price"] = price
            df.loc[mask, "trade_qty"] = qty
            df.loc[mask, "trade_amount"] = price * qty
            df.loc[mask, "fee_paid"] = fee

        if mask.any():
            df.loc[mask, "realized_pnl"] = realized
            df.loc[mask, "hold_qty"] = hold_qty
            avg_now = (hold_cost / hold_qty) if hold_qty > 0 else np.nan
            df.loc[mask, "hold_avg"] = avg_now

    # 向前填充持仓信息
    df["hold_qty"] = df["hold_qty"].replace(0, np.nan).ffill().fillna(0)
    df["hold_avg"] = df["hold_avg"].ffill()
    df["realized_pnl"] = df["realized_pnl"].ffill().fillna(0)

    buys = (df["trade_action"] == "买入").sum()
    sells = (df["trade_action"] == "卖出").sum()
    log.info(f"  💰 买卖记录: 买入{buys}次 / 卖出{sells}次")
    return df


# ═════════════════════════════════════════════════════════
#  6. 导出
# ═════════════════════════════════════════════════════════

def export_results(df, xlsx_path="BTC_AHR999.xlsx",
                  json_path="ahr999_data.json",
                  data_js_path=os.path.join(PAGES_DIR, "data.js")):
    """导出 Excel / JSON / data.js"""
    out = df.copy()

    # NaN → None（JSON 友好）
    out = out.where(pd.notna(out), None)

    # Excel
    out.to_excel(xlsx_path, index=False)
    log.info(f"  📊 导出 {xlsx_path}")

    # JSON
    records = out.to_dict(orient="records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, default=str)
    log.info(f"  📊 导出 {json_path}")

    # data.js (供静态网页内嵌)
    os.makedirs(PAGES_DIR, exist_ok=True)
    with open(data_js_path, "w", encoding="utf-8") as f:
        f.write("const AHR999_DATA = ")
        json.dump(records, f, ensure_ascii=False, default=str)
        f.write(";")
    log.info(f"  📊 导出 {data_js_path}")


# ═════════════════════════════════════════════════════════
#  7. 管线入口
# ═════════════════════════════════════════════════════════

def run_pipeline(force_refresh=False, start="2017-01-01"):
    """完整管线：拉数据 → 算指标 → 检测 → 标签 → 交易 → 导出"""
    print(f"\n{'='*60}")
    print(f"  ₿ BTC AHR999 Pipeline  |  {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*60}\n")

    # 1. 数据
    df = fetch_btc_data(force_refresh=force_refresh, start=start)

    # 2. AHR999
    df = calculate_ahr999(df)
    df = detect_anomalies(df)
    df = assign_zone(df)

    # 3. 交易
    df = apply_trades(df)

    # 4. 导出
    export_results(df)

    # 5. 打印摘要
    valid = df.dropna(subset=["ahr999"])
    if len(valid) > 0:
        latest = valid.iloc[-1]
        print(f"\n  📡 数据源: 见上方日志")
        print(f"  📈 最新 AHR999: {latest['ahr999']:.4f}")
        print(f"  🏷️ 区间: {latest['zone']}")
        if "hold_qty" in df.columns:
            last_hold = df["hold_qty"].iloc[-1]
            last_avg = df["hold_avg"].iloc[-1]
            last_price = df["close"].iloc[-1]
            print(f"  💰 持仓: {last_hold:.8f} BTC")
            if not pd.isna(last_avg) and last_avg > 0:
                print(f"  💰 加权均价: ${last_avg:,.2f}")
                pnl = (last_price - last_avg) * last_hold
                print(f"  💰 浮动盈亏: ${pnl:,.2f}")
        if "deviation_pct" in latest and not pd.isna(latest["deviation_pct"]):
            print(f"  📊 偏离MA200: {latest['deviation_pct']:+.2f}%")

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="  %(asctime)s │ %(message)s",
                        datefmt="%H:%M:%S")
    run_pipeline(force_refresh=True)
