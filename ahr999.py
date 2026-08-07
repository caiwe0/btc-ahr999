#!/usr/bin/env python3
"""
₿ BTC AHR999 定投指标 · 主程序
====================================
功能：拉取 BTC 历史日线 → 计算 AHR999 → 异常检测 → 买卖记账 → 导出 Excel/JSON/HTML

数据源优先级（自动降级）：
  1. Binance 公开 API（最稳定，无需 Key）
  2. 本地缓存 CSV（离线可用）
  3. 合成数据（最后兜底，保证脚本永远能跑）

使用：
  from start import run_pipeline   # 一次性跑完
  或
  python start.py --web            # Web 模式
"""
import os
import json
import math
import time
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import config

# ── 日志 ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="  %(asctime)s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════
#  1. 数据获取（多源降级 + 缓存）
# ═════════════════════════════════════════════════════════
def fetch_btc_data(force_refresh=False):
    """获取 BTC 日线数据，多源降级 + 本地缓存"""
    cache = config.CACHE_FILE

    # 缓存命中（6小时内不重拉）
    if not force_refresh and os.path.exists(cache):
        age = datetime.now().timestamp() - os.path.getmtime(cache)
        if age < 3600 * 6:
            df = pd.read_csv(cache, parse_dates=["date"])
            log.info(f"  📂 使用缓存: {cache} ({(age/3600):.1f}h 前)")
            return df.sort_values("date").reset_index(drop=True)

    df = None

    # ── 源1: Binance 公开 REST API（最稳定） ──
    df = _fetch_binance()
    if df is not None and not df.empty:
        log.info("  📡 数据源: Binance (公开API)")
    else:
        # ── 源2: Yahoo Finance ──
        df = _fetch_yahoo()
        if df is not None and not df.empty:
            log.info("  📡 数据源: Yahoo Finance")
        else:
            # ── 源3: 本地缓存（即使过期也用） ──
            if os.path.exists(cache):
                df = pd.read_csv(cache, parse_dates=["date"])
                log.warning("  ⚠️ 使用过期缓存（联网失败）")
            else:
                # ── 源4: 合成数据兜底 ──
                log.warning("  ⚠️ 全部数据源失败，使用合成数据")
                df = _synthetic_data()

    df = df.sort_values("date").reset_index(drop=True)
    df.to_csv(cache, index=False)
    log.info(f"  💾 缓存已保存: {cache} ({len(df)} 行)")
    return df


def _fetch_binance():
    """从 Binance 公开 API 拉取 BTCUSDT 日线"""
    try:
        import urllib.request
        # 分批拉取（每次最多1000根）
        all_bars = []
        # 从 2013-01-01 开始
        start_ms = int(datetime(2013, 1, 1).timestamp() * 1000)
        end_ms = int(datetime.now().timestamp() * 1000)
        chunk = 1000 * 86400 * 1000  # 1000天的毫秒数

        current = start_ms
        req = urllib.request.Request(
            "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        # 先测试连通性
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass

        while current < end_ms:
            url = (f"https://api.binance.com/api/v3/klines"
                   f"?symbol=BTCUSDT&interval=1d"
                   f"&startTime={current}&endTime={min(current+chunk, end_ms)}"
                   f"&limit=1000")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                bars = json.loads(resp.read().decode())
            if not bars:
                break
            all_bars.extend(bars)
            current = bars[-1][0] + 86400000
            time.sleep(0.5)  # 避免限流

        if not all_bars:
            return None

        df = pd.DataFrame(all_bars, columns=[
            "ts","open","high","low","close","volume",
            "close_time","qav","ntrades","tbbav","tbqav","ignore"
        ])
        df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.tz_localize(None)
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df[["date","open","high","low","close","volume"]].dropna(subset=["close"])
    except Exception as e:
        log.warning(f"  ⚠️ Binance 失败: {e}")
        return None


def _fetch_yahoo():
    """从 Yahoo Finance 拉取 BTC-USD 日线"""
    try:
        import yfinance as yf
        t = yf.Ticker("BTC-USD")
        df = t.history(start="2013-01-01", auto_adjust=True)
        if df.empty:
            return None
        df = df.reset_index()[["Date","Open","High","Low","Close","Volume"]]
        df.columns = ["date","open","high","low","close","volume"]
        return df
    except Exception as e:
        log.warning(f"  ⚠️ Yahoo 失败: {e}")
        return None


def _synthetic_data():
    """离线兜底数据（保证脚本永远能跑）"""
    dates = pd.date_range("2013-01-01", datetime.now().strftime("%Y-%m-%d"))
    n = len(dates)
    np.random.seed(42)
    rets = np.random.normal(0.0015, 0.04, n)
    price = 100 * np.cumprod(1 + rets)
    for i in range(n):
        y = dates[i].year
        if y == 2013: price[i] *= 8
        if y == 2017: price[i] *= 20
        if y in (2020, 2021): price[i] *= 35
        if y >= 2024: price[i] *= 50
    return pd.DataFrame({
        "date": dates,
        "open": price * 0.99,
        "high": price * 1.02,
        "low": price * 0.98,
        "close": price,
        "volume": np.random.lognormal(10, 1, n),
    })


# ═══════════════════════════════════════════════════════
#  2. AHR999 计算
# ═══════════════════════════════════════════════════════
def compute_ahr999(df):
    """计算 AHR999 = (现价/200日均价) × (现价/幂律拟合价)"""
    c = config.Config()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    # 200日定投成本（MA200）
    df["ma200"] = df["close"].rolling(200, min_periods=30).mean()

    # 距创世区块天数
    genesis = pd.Timestamp("2009-01-03")
    df["days"] = ((df["date"] - genesis).dt.days).astype(float)

    # 幂律拟合价格
    df["power_price"] = c.POWER_LAW_A * df["days"] ** c.POWER_LAW_B

    # AHR999
    df["ahr999"] = (df["close"] / df["ma200"]) * (df["close"] / df["power_price"])

    # 实价价值 = MA200
    df["fair_value"] = df["ma200"]
    df["deviation_pct"] = (df["close"] - df["fair_value"]) / df["fair_value"] * 100

    return df


# ═══════════════════════════════════════════════════════
#  3. 异常检测（单根K五态）
# ═══════════════════════════════════════════════════════
def detect_anomalies(df):
    """单根K线五态分类（不借多根）"""
    c = config.Config()
    df = df.copy()

    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14, min_periods=5).median()
    df["vma20"] = df["volume"].rolling(20, min_periods=5).mean()

    body = (df["close"] - df["open"]).abs()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    body_ratio = (body / rng).values
    atr_vals = df["atr"].values
    vma_vals = df["vma20"].values
    vol_vals = df["volume"].values
    open_vals = df["open"].values
    close_vals = df["close"].values

    n = len(df)
    states = ["正常"] * n

    for i in range(n):
        a = atr_vals[i]
        if pd.isna(a) or a == 0:
            continue
        br = body_ratio[i]
        if pd.isna(br):
            br = 0.0
        vr = vol_vals[i] / vma_vals[i] if not pd.isna(vma_vals[i]) and vma_vals[i] > 0 else 1.0
        b = body.iloc[i] if not pd.isna(body.iloc[i]) else 0.0

        is_big = bool(br > 0.7 and b > c.ATR_MULT_EXTREME * a)
        is_small = bool(br < 0.2 or b < c.ATR_MULT_BODY * a)
        is_high_vol = bool(vr > c.VOL_MULT_HIGH)
        is_low_vol = bool(vr < c.VOL_MULT_LOW)
        close_up = bool(close_vals[i] > open_vals[i])

        if is_big and is_high_vol:
            states[i] = "极端上涨" if close_up else "极端下跌"
        elif is_small and is_high_vol:
            states[i] = "横盘放量"
        elif (not close_up) and is_low_vol and br > 0.3:
            states[i] = "量价背离↓"
        elif close_up and is_low_vol and br > 0.3:
            states[i] = "量价背离↑"

    df["micro_state"] = states
    return df


# ═══════════════════════════════════════════════════════
#  4. 区间判定 + 颜色
# ═══════════════════════════════════════════════════════
def assign_zone(df):
    """根据 AHR999 值 + 异常状态分配区间和颜色"""
    c = config.Config()
    zones, colors = [], []

    for _, row in df.iterrows():
        a = row["ahr999"]
        anomalous = row["micro_state"] != "正常"

        if pd.isna(a):
            zones.append("数据不足"); colors.append("#666666")
        elif a < c.EXTREME_LOW:
            if anomalous: zones.append("极度低估+异常"); colors.append(c.COLORS["extreme_low_anom"])
            else:        zones.append("极度低估");       colors.append(c.COLORS["extreme_low"])
        elif a < c.DIP_ZONE:
            if anomalous: zones.append("定投区+异常"); colors.append(c.COLORS["dip_zone_anom"])
            else:        zones.append("定投区");       colors.append(c.COLORS["dip_zone"])
        elif a < c.FAIR_HIGH:
            if anomalous: zones.append("合理偏高+异常"); colors.append(c.COLORS["fair_high_anom"])
            else:        zones.append("合理偏高");     colors.append(c.COLORS["fair_high"])
        else:
            if anomalous: zones.append("高估+异常"); colors.append(c.COLORS["overvalued_anom"])
            else:        zones.append("高估");       colors.append(c.COLORS["overvalued"])

    df["zone"] = zones
    df["bg_color"] = colors
    return df


# ═══════════════════════════════════════════════════════
#  5. 买卖操作 + FIFO 盈亏
# ═══════════════════════════════════════════════════════
def load_manual_trades():
    """读取 manual_input.csv"""
    path = config.MANUAL_CSV
    if not os.path.exists(path):
        return pd.DataFrame(columns=["date", "action", "price", "amount"])
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


def apply_trades(df, trades):
    """应用买卖操作，计算持仓/成本/FIFO盈亏"""
    c = config.Config()
    fee = c.FEE_RATE

    df = df.copy()
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")

    for col in ["action", "buy_price", "buy_amount", "buy_qty",
                "sell_price", "sell_amount", "sell_qty",
                "fee_paid", "hold_qty", "hold_avg", "realized_pnl_row"]:
        if col == "action":
            df[col] = ""
        else:
            df[col] = 0.0

    stack = []
    total_invested = 0
    total_fee = 0
    realized_pnl = 0
    total_sell_cash = 0
    buy_count = sell_count = 0

    if not trades.empty:
        trades_sorted = trades.copy()
        trades_sorted["date"] = pd.to_datetime(trades_sorted["date"]).dt.strftime("%Y-%m-%d")
        trades_sorted = trades_sorted.sort_values("date").reset_index(drop=True)
    else:
        trades_sorted = trades

    for _, t in trades_sorted.iterrows():
        d = t["date"]
        act = str(t.get("action", "")).strip().lower()
        price = t.get("price", 0) or 0
        amount = t.get("amount", 0) or 0

        row_idx = df.index[df["date_str"] == d]
        if len(row_idx) == 0:
            continue
        idx = row_idx[0]
        close = df.loc[idx, "close"]

        if act == "buy":
            p = float(price) if price else close
            a = float(amount)
            if a <= 0:
                continue
            buy_count += 1
            qty = a * (1 - fee) / p
            total_invested += a
            fee_paid = a * fee
            total_fee += fee_paid
            stack.append((p, qty, a))
            df.loc[idx, "action"] = "买入"
            df.loc[idx, "buy_price"] = p
            df.loc[idx, "buy_amount"] = a
            df.loc[idx, "buy_qty"] = round(qty, 8)
            df.loc[idx, "fee_paid"] = round(fee_paid, 4)

        elif act == "sell":
            p = float(price) if price else close
            a = float(amount)
            if a <= 0:
                continue
            sell_count += 1
            qty_to_sell = a / p
            fee_paid = a * fee
            total_fee += fee_paid
            total_sell_cash += a
            remaining = qty_to_sell
            sell_cost = 0.0
            row_pnl = 0.0
            new_stack = []
            for (sp, sq, sc) in stack:
                if remaining <= 0:
                    new_stack.append((sp, sq, sc))
                    continue
                if sq <= remaining:
                    sell_cost += sc
                    row_pnl += sp * sq - sc
                    remaining -= sq
                else:
                    portion = remaining / sq
                    sell_cost += sc * portion
                    row_pnl += sp * remaining - sc * portion
                    new_stack.append((sp, sq - remaining, sc * (1 - portion)))
                    remaining = 0
            stack = new_stack
            realized_pnl += a * (1 - fee) - sell_cost
            df.loc[idx, "action"] = "卖出"
            df.loc[idx, "sell_price"] = p
            df.loc[idx, "sell_amount"] = a
            df.loc[idx, "sell_qty"] = round(qty_to_sell, 8)
            df.loc[idx, "fee_paid"] = round(fee_paid, 4)
            df.loc[idx, "realized_pnl_row"] = round(a * (1 - fee) - sell_cost, 2)

    # 逐行构建持仓快照
    running_stack = []
    hold_qty_hist = []
    hold_avg_hist = []
    for i in range(len(df)):
        act_row = df.loc[i, "action"]
        if act_row == "买入":
            p = df.loc[i, "buy_price"]
            q = df.loc[i, "buy_qty"]
            cost = df.loc[i, "buy_amount"]
            running_stack.append((p, q, cost))
        elif act_row == "卖出":
            sq = df.loc[i, "sell_qty"]
            rem = sq
            new_s = []
            for (sp, sq0, sc) in running_stack:
                if rem <= 0:
                    new_s.append((sp, sq0, sc))
                    continue
                if sq0 <= rem:
                    rem -= sq0
                else:
                    new_s.append((sp, sq0 - rem, sc * (1 - rem / sq0)))
                    rem = 0
            running_stack = new_s
        total_q = sum(x[1] for x in running_stack)
        total_c = sum(x[2] for x in running_stack)
        avg = total_c / total_q if total_q > 0 else 0
        hold_qty_hist.append(round(total_q, 8))
        hold_avg_hist.append(round(avg, 2))

    df["hold_qty"] = hold_qty_hist
    df["hold_avg"] = hold_avg_hist

    current_price = df["close"].iloc[-1]
    current_hold = hold_qty_hist[-1]
    avg_cost = hold_avg_hist[-1]
    market_value_gross = current_hold * current_price
    market_value_net = market_value_gross * (1 - fee)
    floating_pnl = market_value_net - total_invested

    summary = {
        "buy_count": buy_count,
        "sell_count": sell_count,
        "total_invested": round(total_invested, 2),
        "total_fee": round(total_fee, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_sell_cash": round(total_sell_cash, 2),
        "current_hold": round(current_hold, 8),
        "avg_cost": round(avg_cost, 2),
        "current_price": round(current_price, 2),
        "breakeven_price": round(avg_cost / (1 - fee), 2) if avg_cost > 0 else 0,
        "floating_pnl": round(floating_pnl, 2),
        "total_pnl": round(floating_pnl + realized_pnl, 2),
        "total_pnl_pct": round((floating_pnl + realized_pnl) / total_invested * 100, 2) if total_invested > 0 else 0,
        "last_date": str(df["date"].iloc[-1].strftime("%Y-%m-%d")),
        "row_count": len(df),
        "ahr999": round(df["ahr999"].iloc[-1], 4) if not pd.isna(df["ahr999"].iloc[-1]) else 0,
        "zone": df["zone"].iloc[-1] if not pd.isna(df["zone"].iloc[-1]) else "未知",
        "fair_value": round(df["fair_value"].iloc[-1], 2) if not pd.isna(df["fair_value"].iloc[-1]) else 0,
        "deviation_pct": round(df["deviation_pct"].iloc[-1], 2) if not pd.isna(df["deviation_pct"].iloc[-1]) else 0,
    }
    return df, summary


# ═══════════════════════════════════════════════════════
#  6. 导出
# ═══════════════════════════════════════════════════════
def export_excel(df, summary):
    """导出 Excel（含持仓汇总 sheet）"""
    out = config.EXCEL_FILE
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_out = df.copy()
        df_out["date"] = df_out["date"].dt.strftime("%Y-%m-%d")
        keep = ["date","ahr999","open","high","low","close","volume",
                "change_pct","micro_state","zone","bg_color",
                "action","buy_price","buy_amount","buy_qty",
                "sell_price","sell_amount","sell_qty",
                "fee_paid","hold_qty","hold_avg","realized_pnl_row",
                "fair_value","deviation_pct"]
        df_out = df_out[[c for c in keep if c in df_out.columns]]
        df_out.to_excel(w, sheet_name="AHR999数据", index=False)

        s = summary
        rows = [
            ["当前价格", s["current_price"]],
            ["持仓数量(BTC)", s["current_hold"]],
            ["加权均价($)", s["avg_cost"]],
            ["盈亏平衡价($)", s["breakeven_price"]],
            ["浮动盈亏($)", s["floating_pnl"]],
            ["已实现盈亏($)", s["realized_pnl"]],
            ["总盈亏($)", s["total_pnl"]],
            ["总收益率(%)", s["total_pnl_pct"]],
            ["总投入($)", s["total_invested"]],
            ["总手续费($)", s["total_fee"]],
            ["买入次数", s["buy_count"]],
            ["卖出次数", s["sell_count"]],
            ["最新AHR999", s["ahr999"]],
            ["区间", s["zone"]],
            ["实价价值($)", s["fair_value"]],
            ["偏离幅度(%)", s["deviation_pct"]],
        ]
        pd.DataFrame(rows, columns=["项目","数值"]).to_excel(w, sheet_name="持仓汇总", index=False)
    log.info(f"  ✅ 导出 {out}")


def write_json(df, summary):
    """导出 JSON（供前端读取）"""
    out = config.JSON_FILE
    df_out = df.copy()
    df_out["date"] = df_out["date"].dt.strftime("%Y-%m-%d")

    records = []
    for _, r in df_out.iterrows():
        records.append({
            "date": r.get("date",""),
            "ahr999": r.get("ahr999", None),
            "open": r.get("open", 0),
            "high": r.get("high", 0),
            "low": r.get("low", 0),
            "close": r.get("close", 0),
            "volume": r.get("volume", 0),
            "change_pct": r.get("change_pct", 0),
            "micro_state": r.get("micro_state", ""),
            "zone": r.get("zone", ""),
            "bg": r.get("bg_color", "#000000"),
            "fg": "#000" if _is_light(r.get("bg_color","")) else "#fff",
            "action": r.get("action", ""),
            "buy_price": r.get("buy_price", 0),
            "buy_amount": r.get("buy_amount", 0),
            "buy_qty": r.get("buy_qty", 0),
            "sell_price": r.get("sell_price", 0),
            "sell_amount": r.get("sell_amount", 0),
            "sell_qty": r.get("sell_qty", 0),
            "fee_paid": r.get("fee_paid", 0),
            "realized_profit": r.get("realized_pnl_row", 0),
            "hold_qty": r.get("hold_qty", 0),
            "hold_avg": r.get("hold_avg", 0),
            "fair_value": r.get("fair_value", 0),
            "deviation_pct": r.get("deviation_pct", 0),
        })

    payload = {
        "updated": summary["last_date"],
        "fee_rate": config.FEE_RATE,
        "fair_value": summary["fair_value"],
        "deviation_pct": summary["deviation_pct"],
        "summary": {
            "position_qty": summary["current_hold"],
            "avg_cost": summary["avg_cost"],
            "break_even": summary["breakeven_price"],
            "unrealized_profit": summary["floating_pnl"],
            "realized_profit": summary["realized_pnl"],
            "total_profit": summary["total_pnl"],
            "total_profit_pct": summary["total_pnl_pct"],
            "total_buy_cash": summary["total_invested"],
            "total_sell_cash": summary["total_sell_cash"],
            "net_invested": summary["total_invested"] - summary["total_sell_cash"],
            "net_value": summary["current_hold"] * summary["current_price"] * (1 - config.FEE_RATE),
            "total_fee": summary["total_fee"],
            "buy_count": summary["buy_count"],
            "sell_count": summary["sell_count"],
            "current_price": summary["current_price"],
            "fair_value": summary["fair_value"],
            "deviation_pct": summary["deviation_pct"],
            "is_profit": bool(summary["floating_pnl"] >= 0),
        },
        "data": records,
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), default=str)
    log.info(f"  ✅ 导出 {out}")


def generate_html(df, summary):
    """生成 index.html（Flask 模式，内嵌数据）"""
    tpl_path = "templates/index.html"
    if not os.path.exists(tpl_path):
        return
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()

    # 构建内嵌 JSON
    import io
    buf = io.StringIO()
    json.dump({
        "updated": summary["last_date"],
        "fee_rate": config.FEE_RATE,
        "fair_value": summary["fair_value"],
        "deviation_pct": summary["deviation_pct"],
        "summary": {
            "position_qty": summary["current_hold"],
            "avg_cost": summary["avg_cost"],
            "break_even": summary["breakeven_price"],
            "unrealized_profit": summary["floating_pnl"],
            "realized_profit": summary["realized_pnl"],
            "total_profit": summary["total_pnl"],
            "total_profit_pct": summary["total_pnl_pct"],
            "total_buy_cash": summary["total_invested"],
            "total_sell_cash": summary["total_sell_cash"],
            "net_invested": summary["total_invested"] - summary["total_sell_cash"],
            "net_value": summary["current_hold"] * summary["current_price"] * (1 - config.FEE_RATE),
            "total_fee": summary["total_fee"],
            "buy_count": summary["buy_count"],
            "sell_count": summary["sell_count"],
            "current_price": summary["current_price"],
            "fair_value": summary["fair_value"],
            "deviation_pct": summary["deviation_pct"],
            "is_profit": bool(summary["floating_pnl"] >= 0),
        },
        "data": _df_to_records(df),
    }, buf, ensure_ascii=False, separators=(",", ":"), default=str)
    data_json = buf.getvalue()

    replacements = {
        "__DATA_PLACEHOLDER__": data_json,
    }
    for k, v in replacements.items():
        tpl = tpl.replace(k, str(v))

    out = "index.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(tpl)
    log.info(f"  ✅ 生成 {out}（内嵌数据）")


def _df_to_records(df):
    records = []
    for _, r in df.iterrows():
        records.append({
            "date": r["date"].strftime("%Y-%m-%d") if hasattr(r.get("date"), "strftime") else r.get("date",""),
            "ahr999": r.get("ahr999", None),
            "open": r.get("open", 0),
            "high": r.get("high", 0),
            "low": r.get("low", 0),
            "close": r.get("close", 0),
            "volume": r.get("volume", 0),
            "change_pct": r.get("change_pct", 0),
            "micro_state": r.get("micro_state", ""),
            "zone": r.get("zone", ""),
            "bg": r.get("bg_color", "#000000"),
            "fg": "#000" if _is_light(r.get("bg_color","")) else "#fff",
            "action": r.get("action", ""),
            "buy_price": r.get("buy_price", 0),
            "buy_amount": r.get("buy_amount", 0),
            "buy_qty": r.get("buy_qty", 0),
            "sell_price": r.get("sell_price", 0),
            "sell_amount": r.get("sell_amount", 0),
            "sell_qty": r.get("sell_qty", 0),
            "fee_paid": r.get("fee_paid", 0),
            "realized_profit": r.get("realized_pnl_row", 0),
            "hold_qty": r.get("hold_qty", 0),
            "hold_avg": r.get("hold_avg", 0),
            "fair_value": r.get("fair_value", 0),
            "deviation_pct": r.get("deviation_pct", 0),
        })
    return records


def _is_light(hex_color):
    if not hex_color or not isinstance(hex_color, str) or len(hex_color) != 7:
        return False
    try:
        r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
        return (0.299*r + 0.587*g + 0.114*b) > 160
    except:
        return False


def print_summary(summary):
    """打印持仓摘要到终端"""
    s = summary
    print(f"\n{'='*60}")
    print(f"  💰 持仓: {s['current_hold']:.8f} BTC")
    print(f"  💰 加权均价: ${s['avg_cost']:,.2f}")
    print(f"  💰 浮动盈亏: ${s['floating_pnl']:,.2f}")
    print(f"  ✅ 已实现盈亏: ${s['realized_pnl']:,.2f}")
    print(f"  📈 总收益率: {s['total_pnl_pct']:.2f}%")
    print(f"  📈 总盈亏: ${s['total_pnl']:,.2f}")
    print(f"  💵 总投入: ${s['total_invested']:,.2f} | 手续费: ${s['total_fee']:,.2f}")
    print(f"  🎯 实价价值: ${s['fair_value']:,.2f} (偏离 {s['deviation_pct']:+.2f}%)")
    print(f"{'='*60}\n")
