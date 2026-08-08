"""
入口：python start.py [--pages] [--src btc_cache.csv]
"""
import argparse
import sys
import os
import json
import pandas as pd
import numpy as np

import ahr999 as ahr

# ═══════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════

def _clean_for_json(df: pd.DataFrame) -> pd.DataFrame:
    """把 NaN/Inf 替换成 None，避免 JSON 报错"""
    df = df.replace([np.inf, -np.inf], np.nan)
    return df.where(pd.notna(df), None)

def _build_cards(df: pd.DataFrame) -> dict:
    """构造网页顶部 4 张卡片数据（无"实现价值"）"""
    valid = df.dropna(subset=["ahr999"])
    if valid.empty:
        return {}
    latest = valid.iloc[-1]
    return {
        "date": latest["date"].strftime("%Y-%m-%d"),
        "close": float(latest["close"]),
        "ahr999": float(latest["ahr999"]),
        "deviation_pct": float(latest["deviation_pct"]),
        "sma200": float(latest["sma200"]),
        "index_growth_val": float(latest["index_growth_val"]),
        "zone": latest["zone"],
        "rows": int(len(df)),
    }

# ═══════════════════════════════════════════════════════
# Pages 模式：生成 _site/
# ═══════════════════════════════════════════════════════

def run_pages(src: str = "btc_cache.csv"):
    df = ahr.run_pipeline(src)

    os.makedirs("_site", exist_ok=True)

    # 1) data.js（前端渲染用）
    out = df.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out = _clean_for_json(out)
    records = out.to_dict(orient="records")
    cards = _build_cards(df)

    with open("_site/data.js", "w", encoding="utf-8") as f:
        f.write("window.BTC_DATA = ")
        json.dump(records, f, ensure_ascii=False)
        f.write(";\nwindow.BTC_CARDS = ")
        json.dump(cards, f, ensure_ascii=False)
        f.write(";")

    # 2) index.html（极简展示页）
    html = _render_html(cards, len(records))
    with open("_site/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ _site/ 生成完成")
    print(f"  📄 data.js  ({os.path.getsize('_site/data.js')/1024:.0f} KB)")
    print(f"  📄 index.html ({os.path.getsize('_site/index.html')/1024:.0f} KB)")

# ═══════════════════════════════════════════════════════
# 简易 HTML 模板（4 张卡片：现价 / AHR999 / 偏离幅度 / 区间）
# ═══════════════════════════════════════════════════════

ZONE_COLORS = {
    "极度低估": "#00e676",
    "定投区":   "#76ff03",
    "合理区":   "#ffd600",
    "偏高":     "#ff9100",
    "高估":     "#ff1744",
    "数据不足": "#9e9e9e",
}

def _render_html(cards: dict, rows: int) -> str:
    if not cards:
        return "<h1>BTC AHR999</h1><p>暂无有效数据</p>"

    zone = cards["zone"]
    color = ZONE_COLORS.get(zone, "#9e9e9e")
    dev = cards["deviation_pct"]
    dev_sign = "+" if dev >= 0 else ""
    dev_class = "up" if dev >= 0 else "down"

    return f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>BTC AHR999 指标</title>
<style>
  body {{ font-family:-apple-system,Segoe UI,Roboto,sans-serif;
         background:#0e1117;color:#e6e6e6;margin:0;padding:24px; }}
  h1 {{ margin:0 0 4px;font-size:20px; }}
  .meta {{ color:#888;font-size:13px;margin-bottom:20px; }}
  .cards {{ display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px; }}
  .card {{ background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px; }}
  .card .label {{ font-size:12px;color:#8b949e;margin-bottom:6px; }}
  .card .value {{ font-size:22px;font-weight:700; }}
  .card .sub {{ font-size:12px;color:#8b949e;margin-top:4px; }}
  .up {{ color:#00e676; }} .down {{ color:#ff1744; }}
  .zone-badge {{ display:inline-block;padding:4px 10px;border-radius:20px;
                background:{color}22;color:{color};font-weight:600;font-size:13px; }}
  table {{ width:100%;border-collapse:collapse;margin-top:24px;font-size:13px; }}
  th,td {{ padding:6px 10px;text-align:right;border-bottom:1px solid #21262d; }}
  th {{ background:#161b22;color:#8b949e;position:sticky;top:0; }}
  tr:hover td {{ background:#161b22; }}
  .dot {{ display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle; }}
</style>
</head>
<body>
<h1>₿ BTC AHR999 定投指标</h1>
<div class="meta">更新时间: {cards['date']} · 数据: {rows} 行 · 数据源: 用户上传</div>

<div class="cards">
  <div class="card">
    <div class="label">最新价</div>
    <div class="value">${cards['close']:,.2f}</div>
    <div class="sub">AHR999: <b>{cards['ahr999']:.4f}</b></div>
  </div>
  <div class="card">
    <div class="label">区间</div>
    <div class="value"><span class="zone-badge">{zone}</span></div>
    <div class="sub">SMA200: ${cards['sma200']:,.2f}</div>
  </div>
  <div class="card">
    <div class="label">较 SMA200 幅度</div>
    <div class="value {dev_class}">{dev_sign}{dev:.2f}%</div>
    <div class="sub">幂律估值: ${cards['index_growth_val']:,.0f}</div>
  </div>
  <div class="card">
    <div class="label">操作提示</div>
    <div class="value" style="font-size:15px;line-height:1.5;">
      {"⚠️ 极度低估，分批抄底" if zone=="极度低估" else
       "🟢 定投区，逢低买入" if zone=="定投区" else
       "🟡 合理区，持有观望" if zone=="合理区" else
       "🟠 偏高，减少买入" if zone=="偏高" else
       "🔴 高估，考虑减仓"}
    </div>
  </div>
</div>

<div id="table-root"></div>

<script src="data.js"></script>
<script>
const ZONE_COLORS = {json.dumps(ZONE_COLORS)};
const data = window.BTC_DATA || [];
const root = document.getElementById('table-root');

function fmt(n, d=2) {{
  if (n==null) return '-';
  return Number(n).toLocaleString('en-US', {{minimumFractionDigits:d, maximumFractionDigits:d}});
}}

let html = '<table><thead><tr>' +
  '<th>日期</th><th>AHR999</th><th>收盘</th><th>高</th><th>低</th>' +
  '<th>涨跌幅%</th><th>区间</th><th>SMA200</th></tr></thead><tbody>';

// 只渲染最近 500 行，避免 DOM 过大
const slice = data.slice(-500).reverse();
for (const r of slice) {{
  const c = ZONE_COLORS[r.zone] || '#9e9e9e';
  const chg = r.change_pct == null ? '-' : (r.change_pct>=0?'+':'') + Number(r.change_pct).toFixed(2) + '%';
  const chgCls = r.change_pct == null ? '' : (r.change_pct>=0 ? 'up' : 'down');
  html += '<tr>' +
    '<td>' + r.date + '</td>' +
    '<td><b>' + fmt(r.ahr999,4) + '</b></td>' +
    '<td>$' + fmt(r.close) + '</td>' +
    '<td>$' + fmt(r.high) + '</td>' +
    '<td>$' + fmt(r.low) + '</td>' +
    '<td class="' + chgCls + '">' + chg + '</td>' +
    '<td><span class="dot" style="background:' + c + '"></span>' + (r.zone||'') + '</td>' +
    '<td>$' + fmt(r.sma200) + '</td>' +
  '</tr>';
}}
html += '</tbody></table>';
root.innerHTML = html;
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="BTC AHR999 工具")
    parser.add_argument("--pages", action="store_true", help="生成 _site/ 静态站点")
    parser.add_argument("--src", default="btc_cache.csv", help="BTC 数据 CSV 路径")
    args = parser.parse_args()

    if args.pages:
        run_pages(args.src)
    else:
        ahr.run_pipeline(args.src)

if __name__ == "__main__":
    main()
