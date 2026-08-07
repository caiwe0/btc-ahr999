#!/usr/bin/env python3
"""
BTC AHR999 启动入口（修复版）
================================
修复：
  - --force-refresh 现在真正透传给 fetch_btc_data()
  - Pages 模式把 data_source 注入到页面顶部状态栏
  - 所有模式统一走 run_pipeline(force_refresh=...)

用法:
  python start.py                # 默认 Web 模式
  python start.py --web          # Web 模式 (Flask)
  python start.py --cli          # 命令行模式 (只生成文件)
  python start.py --once         # 跑一次后退出
  python start.py --pages        # 生成 GitHub Pages 静态文件
  python start.py --pages --force-refresh   # 强制拉最新数据
"""
import sys
import os
import argparse
from datetime import datetime

import config
from ahr999 import (
    fetch_btc_data,
    compute_ahr999,
    detect_anomalies,
    assign_zone,
    load_manual_trades,
    apply_trades,
    export_excel,
    write_json,
    generate_html,
    print_summary,
    LAST_DATA_SOURCE,
)


def run_pipeline(force_refresh=False):
    """完整数据管道：拉数据 → 计算 → 导出"""
    print(f"\n{'='*60}")
    print(f"  ₿ BTC AHR999 Pipeline  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if force_refresh:
        print(f"  🔄 强制刷新模式：将忽略缓存，从网络拉取最新数据")
    print(f"{'='*60}\n")

    # 1. 获取行情（force_refresh 透传）
    df = fetch_btc_data(force_refresh=force_refresh)
    print(f"  ✅ 行情数据: {len(df)} 行 ({df['date'].min()} → {df['date'].max()})")

    # 2. 计算 AHR999
    df = compute_ahr999(df)
    df["change_pct"] = df["close"].pct_change() * 100
    print(f"  ✅ AHR999 计算完成")

    # 3. 异常检测
    df = detect_anomalies(df)
    anomaly_count = (df['micro_state'] != '正常').sum()
    print(f"  ✅ 异常检测完成: {anomaly_count} 根异常K线")

    # 3b. 区间 + 颜色
    df = assign_zone(df)

    # 4. 买卖操作
    trades = load_manual_trades()
    df, summary = apply_trades(df, trades)
    print(f"  ✅ 买卖记录: 买入{summary['buy_count']}次 / 卖出{summary['sell_count']}次")

    # 5. 导出
    export_excel(df, summary)
    write_json(df, summary)
    generate_html(df, summary)
    print(f"  ✅ Excel / JSON / HTML 已生成")

    # 6. 打印摘要
    print_summary(summary)

    return df, summary


def run_web(force_refresh=False):
    """启动 Flask Web 服务"""
    from flask import Flask, render_template, jsonify
    import threading
    import time

    app = Flask(__name__, template_folder="templates")

    # 启动时先跑一次
    df, summary = run_pipeline(force_refresh=force_refresh)

    # 定时调度
    def scheduler_loop():
        while True:
            now = datetime.now()
            if (now.hour == config.SCHEDULE_HOUR and
                now.minute == config.SCHEDULE_MINUTE):
                try:
                    run_pipeline(force_refresh=False)
                except Exception as e:
                    print(f"  ⚠️ 定时任务出错: {e}")
                time.sleep(60)
            time.sleep(30)

    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/data")
    def api_data():
        import json
        with open(config.JSON_FILE, "r") as f:
            return jsonify(json.load(f))

    @app.route("/api/refresh", methods=["POST"])
    def api_refresh():
        run_pipeline(force_refresh=True)
        return jsonify({"status": "ok", "time": datetime.now().isoformat()})

    print(f"\n  🌐 Web 服务启动: http://localhost:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)


def _generate_pages_html(summary):
    """生成 _site/index.html —— 引用 data.js，不内嵌大数据"""
    import shutil
    tpl_path = "templates/index.html"
    if not os.path.exists(tpl_path):
        if os.path.exists("index.html"):
            shutil.copy("index.html", "_site/index.html")
            print(f"  ✅ 复制 index.html → _site/ (回退)")
            return
        else:
            print(f"  ⚠️ 模板文件不存在: {tpl_path}")
            return

    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()

    pnl_color = "#00FF7F" if summary.get("floating_pnl", 0) >= 0 else "#FF6347"
    is_profit = summary.get("floating_pnl", 0) >= 0
    profit_sign = "+" if is_profit else ""
    invested = summary.get("total_invested", 0) or 1
    unreal_pct = (summary.get("floating_pnl", 0) / invested) * 100
    dev_sign = "+" if summary.get("deviation_pct", 0) >= 0 else ""
    dev_cls  = "hdr-up" if summary.get("deviation_pct", 0) >= 0 else "hdr-down"
    data_src = summary.get("data_source", "unknown")
    src_label = {
        "binance": "🟢 Binance",
        "yahoo": "🔵 Yahoo",
        "cache": "📂 缓存",
        "cache-stale": "⚠️ 过期缓存",
        "synthetic": "⚠️ 合成数据",
    }.get(data_src, data_src)

    replacements = {
        "__UPDATED__":   summary.get("last_date", ""),
        "__ROWCOUNT__":  str(summary.get("row_count", 0)),
        "__AHR999__":   str(summary.get("ahr999", 0)),
        "__ZONE__":      summary.get("zone", ""),
        "__ZONECOLOR__": _zone_color(summary.get("zone", "")),
        "__FAIRVALUE__": f'{summary.get("fair_value", 0):,.2f}',
        "__DEVIATION__": f'{summary.get("deviation_pct", 0):.2f}',
        "__DEV_SIGN__":  dev_sign,
        "__DEV_CLS__":   dev_cls,
        "__HOLDQTY__":   f'{summary.get("current_hold", 0):.8f}',
        "__BUYCNT__":    str(summary.get("buy_count", 0)),
        "__SELLCNT__":   str(summary.get("sell_count", 0)),
        "__AVGCOST__":   f'{summary.get("avg_cost", 0):,.2f}',
        "__BREAKEVEN__": f'{summary.get("breakeven_price", 0):,.2f}',
        "__FLOATPPL__":  f'{profit_sign}{summary.get("floating_pnl", 0):,.2f}',
        "__FLOATPCT__":  f'{profit_sign}{unreal_pct:.2f}',
        "__NETMV__":     f'{summary.get("current_hold", 0)*summary.get("current_price", 0)*(1-config.Config().FEE_RATE):,.2f}',
        "__REALIZED__":  f'{"+" if summary.get("realized_pnl", 0)>=0 else ""}{summary.get("realized_pnl", 0):,.2f}',
        "__TOTALPCT__":  f'{summary.get("total_pnl_pct", 0):.2f}',
        "__TOTALPNL__":  f'{"+" if summary.get("total_pnl", 0)>=0 else ""}{summary.get("total_pnl", 0):,.2f}',
        "__INVESTED__":  f'{summary.get("total_invested", 0):,.2f}',
        "__TOTALFEE__":  f'{summary.get("total_fee", 0):,.2f}',
        "__PRICE__":     f'{summary.get("current_price", 0):,.2f}',
        "__PNLCOLOR__":  pnl_color,
        "__ISPROFIT__":  "true" if is_profit else "false",
        "__DATASRC__":   src_label,
        # Pages 模式：不内嵌数据
        "__DATA_PLACEHOLDER__": "null",
    }
    for k, v in replacements.items():
        tpl = tpl.replace(k, str(v))

    os.makedirs("_site", exist_ok=True)
    out = "_site/index.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(tpl)
    print(f"  ✅ 生成 {out}（引用 data.js | 数据源: {src_label}）")


def _zone_color(zone):
    return {
        "极度低估": "#90EE90", "定投区": "#FFFFFF",
        "合理偏高": "#FFCCCC", "高估": "#FF0000",
    }.get(zone, "#FFCCCC")


def run_pages(force_refresh=False):
    """
    GitHub Pages 模式：
    1. 跑完整管道 → 生成 index.html + ahr999_data.json
    2. 把 index.html 和 ahr999_data.json 复制到 _site/
    3. 同时生成一个 data.js（JSON 内嵌），让 index.html 可完全离线
    """
    print(f"\n{'='*60}")
    print(f"  📄 GitHub Pages 静态生成模式")
    if force_refresh:
        print(f"  🔄 强制刷新：忽略缓存，从网络拉取")
    print(f"{'='*60}\n")

    df, summary = run_pipeline(force_refresh=force_refresh)

    # 确保 _site 目录存在
    os.makedirs("_site", exist_ok=True)

    # 生成 Pages 版 HTML
    _generate_pages_html(summary)

    # 复制 Excel
    import shutil
    if os.path.exists(config.EXCEL_FILE):
        shutil.copy(config.EXCEL_FILE, f"_site/{config.EXCEL_FILE}")
        print(f"  ✅ 复制 {config.EXCEL_FILE} → _site/")

    # 生成 data.js（内嵌 JSON，让 HTML 完全离线可用）
    if os.path.exists(config.JSON_FILE):
        shutil.copy(config.JSON_FILE, f"_site/{config.JSON_FILE}")
        print(f"  ✅ 复制 {config.JSON_FILE} → _site/")
        with open(config.JSON_FILE, "r", encoding="utf-8") as f:
            js_data = f.read()
        with open("_site/data.js", "w", encoding="utf-8") as f:
            f.write(f"const BTC_DATA = {js_data};")
        print(f"  ✅ 生成 _site/data.js（内嵌数据，离线可用）")
    else:
        print(f"  ⚠️ {config.JSON_FILE} 不存在，跳过 data.js 生成")

    # 生成 _site 的 README
    readme = f"""# BTC AHR999 指标表 — GitHub Pages

- `index.html` — 主页面（自动加载同目录 data.js）
- `data.js` — 内嵌 JSON 数据（每日自动更新）
- `ahr999_data.json` — 原始 JSON（供程序读取）
- `BTC_AHR999.xlsx` — Excel 下载

最后更新: {summary.get('last_date', 'N/A')}
数据源: {summary.get('data_source', 'unknown')}
"""
    with open("_site/README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    # 列出 _site 内容确认
    print(f"\n  📂 _site/ 目录内容:")
    for f_name in sorted(os.listdir("_site")):
        f_path = os.path.join("_site", f_name)
        size = os.path.getsize(f_path)
        print(f"     {f_name} ({size:,} bytes)")

    print(f"\n  🎉 _site/ 目录就绪，可发布到 GitHub Pages")
    print(f"  📊 数据: {summary.get('row_count', 0)} 行")
    print(f"  💰 最新 AHR999: {summary.get('ahr999', 0)}")
    print(f"  📡 数据源: {summary.get('data_source', 'unknown')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BTC AHR999 定投指标工具")
    parser.add_argument("--web",    action="store_true", help="启动 Web 服务")
    parser.add_argument("--cli",    action="store_true", help="命令行模式（只生成文件）")
    parser.add_argument("--once",   action="store_true", help="跑一次后退出")
    parser.add_argument("--pages",  action="store_true", help="生成 GitHub Pages 静态文件")
    parser.add_argument("--force-refresh", action="store_true",
                        help="强制从网络拉取最新数据，忽略本地缓存")
    args = parser.parse_args()

    if args.pages:
        run_pages(force_refresh=args.force_refresh)
    elif args.cli or args.once:
        run_pipeline(force_refresh=args.force_refresh)
    else:
        run_web(force_refresh=args.force_refresh)
