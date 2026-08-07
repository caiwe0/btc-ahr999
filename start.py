"""
start.py
BTC AHR999 定投指标工具 · 入口

用法：
  python start.py            # 完整管线（默认）
  python start.py --pages    # 生成 _site/ 静态站
  python start.py --web      # 启动本地 Web 预览
  python start.py --cli      # 仅控制台输出
  python start.py --once     # 单次运行（同默认）
  python start.py --pages --force-refresh   # 强制刷新数据
"""

import argparse
import logging
import datetime

from ahr999 import run_pipeline

log = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════
#  Pages 模式：生成静态站
# ═════════════════════════════════════════════════════════

def run_pages(force_refresh=False):
    """跑管线 + 生成 _site/index.html"""
    df = run_pipeline(force_refresh=force_refresh)

    # 生成 index.html（引用 data.js，离线可用）
    try:
        from pathlib import Path
        import json

        pages_dir = "_site"
        Path(pages_dir).mkdir(exist_ok=True)

        # 复制模板
        template_path = "templates/index.html"
        out_path = f"{pages_dir}/index.html"

        if Path(template_path).exists():
            html = Path(template_path).read_text(encoding="utf-8")
        else:
            # 极简内嵌模板（无 templates/ 时也能跑）
            html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>BTC AHR999 指标表</title>
<style>
  body { background:#0d1117; color:#c9d1d9; font-family:-apple-system,sans-serif; margin:0; padding:16px; }
  h1 { color:#58a6ff; font-size:1.2rem; }
  table { border-collapse:collapse; width:100%; font-size:13px; }
  th { background:#161b22; color:#8b949e; padding:6px 8px; text-align:left; border-bottom:1px solid #30363d; }
  td { padding:5px 8px; border-bottom:1px solid #21262d; }
  tr:hover td { background:#161b22; }
  .extreme { background:rgba(46,160,67,.15); }
  .dca { background:rgba(110,118,129,.12); }
  .high { background:rgba(248,81,73,.12); }
  .over { background:rgba(248,81,73,.25); }
  .up { color:#3fb950; }
  .down { color:#f85149; }
  .badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:12px; }
  .b-buy { background:#1f6f3a; color:#c9f7d0; }
  .b-sell { background:#6b1a1a; color:#f7c9c9; }
  .cards { display:flex; flex-wrap:wrap; gap:10px; margin:12px 0; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:10px 14px; min-width:180px; }
  .card .label { font-size:11px; color:#8b949e; }
  .card .val { font-size:1.3rem; font-weight:700; }
  .legend span { display:inline-block; width:14px; height:14px; vertical-align:middle; margin:0 4px 0 10px; border-radius:3px; }
</style>
</head>
<body>
<h1>₿ BTC AHR999 指标表</h1>
<div id="meta"></div>
<div class="cards" id="cards"></div>
<div class="legend">
  <span style="background:rgba(46,160,67,.5)"></span>极度低估
  <span style="background:rgba(110,118,129,.5)"></span>定投区
  <span style="background:rgba(187,128,9,.4)"></span>合理偏高
  <span style="background:rgba(248,81,73,.5)"></span>高估
  <span style="background:rgba(248,81,73,.8)"></span>高估+异常
</div>
<div id="tablewrap" style="overflow:auto; max-height:70vh; margin-top:8px;"></div>
<script src="data.js"></script>
<script>
const fmt = (v,d=2) => v==null||isNaN(v) ? '-' : Number(v).toLocaleString('en-US',{maximumFractionDigits:d});
const pct = v => v==null ? '-' : (v>=0?'+':'') + Number(v).toFixed(2)+'%';
const $ = s => document.querySelector(s);

function render() {
  if (!AHR999_DATA || !AHR999_DATA.length) return;
  const last = AHR999_DATA[AHR999_DATA.length-1];
  const meta = $('#meta');
  meta.innerHTML = `<div style="color:#8b949e;font-size:12px;margin:6px 0">
    更新: ${last.日期||''} | 数据: ${AHR999_DATA.length} 行
    | 最新AHR999: <b style="color:#58a6ff">${fmt(last.ahr999,4)}</b>
    | 区间: <b>${last.zone||''}</b>
    | 现价: $${fmt(last.close)}
  </div>`;

  // 卡片
  const cards = $('#cards');
  const cardsHTML = [
    {label:'持仓', val:fmt(last.hold_qty,8)+' BTC', sub:`均价 $${fmt(last.hold_avg)}`},
    {label:'最新价', val:'$'+fmt(last.close), sub:`AHR999 ${fmt(last.ahr999,4)}`},
    {label:'MA200', val:'$'+fmt(last.ma200), sub:`偏离 ${pct(last.deviation_pct)}`},
    {label:'区间', val:last.zone||'-', sub:last.zone_combo||''},
  ].map(c=>`<div class="card"><div class="label">${c.label}</div><div class="val">${c.val}</div><div class="label">${c.sub||''}</div></div>`).join('');
  cards.innerHTML = cardsHTML;

  // 表格
  const cols = ['日期','ahr999','open','close','high','low','成交量','daily_change_pct','zone','trade_action','trade_price','trade_qty','fee_paid','realized_pnl','hold_qty','hold_avg'];
  const colName = {ahr999:'AHR999',daily_change_pct:'涨跌幅%',trade_action:'操作',trade_price:'价格',trade_qty:'数量',fee_paid:'手续费',realized_pnl:'已实现盈亏',hold_qty:'持仓',hold_avg:'均价'};
  let html = '<table><thead><tr>'+cols.map(c=>`<th>${colName[c]||c}</th>`).join('')+'</tr></thead><tbody>';
  const rows = AHR999_DATA.slice(-500).reverse();
  for (const r of rows) {
    const z = r.zone||'';
    let cls = '';
    if (z.includes('极度低估')) cls='extreme';
    else if (z.includes('定投')) cls='dca';
    else if (z.includes('高估')) cls='over';
    else if (z.includes('偏高')||z.includes('合理')) cls='high';
    html += '<tr class="'+cls+'">';
    for (const c of cols) {
      let v = r[c];
      if (c==='ahr999') v = fmt(v,4);
      else if (c==='close'||c==='open'||c==='high'||c==='low') v = '$'+fmt(v);
      else if (c==='daily_change_pct') { v = pct(v); if(v!='-' && v.startsWith('+')) v='<span class="up">'+v+'</span>'; else if(v!='-') v='<span class="down">'+v+'</span>'; }
      else if (c==='trade_action') { v = v ? `<span class="badge b-${v==='买入'?'buy':'sell'}">${v}</span>` : ''; }
      else if (['trade_price','hold_avg'].includes(c)) v = v?'$'+fmt(v):'-';
      else if (['trade_qty','hold_qty'].includes(c)) v = fmt(v,6);
      else if (c==='成交量') v = fmt(v,0);
      else v = (v==null||v==='')?'-':v;
      html += `<td>${v}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  $('#tablewrap').innerHTML = html;
}
render();
</script>
</body>
</html>"""

        Path(out_path).write_text(html, encoding="utf-8")
        log.info(f"  ✅ 生成 {out_path}")

    except Exception as e:
        log.warning(f"  ⚠️ 生成 index.html 失败: {e}")

    # 复制产物到 _site
    import shutil
    for f in ["BTC_AHR999.xlsx", "ahr999_data.json"]:
        if Path(f).exists():
            shutil.copy2(f, f"{pages_dir}/{f}")
            log.info(f"  📋 复制 {f} → {pages_dir}/")

    print(f"\n  📂 _site/ 目录就绪, 可发布到 GitHub Pages")
    return df


# ═════════════════════════════════════════════════════════
#  Web 模式：本地 Flask 预览
# ═════════════════════════════════════════════════════════

def run_web():
    try:
        from flask import Flask, jsonify, send_file
    except ImportError:
        print("❌ 需要安装 flask: pip install flask")
        return

    app = Flask(__name__, static_folder="_site", static_url_path="")

    @app.route("/")
    def index():
        return send_file("_site/index.html")

    @app.route("/api/data")
    def api_data():
        try:
            import json as _json
            with open("ahr999_data.json", encoding="utf-8") as f:
                return jsonify(_json.load(f))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    print("\n  🌐 本地预览: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


# ═════════════════════════════════════════════════════════
#  主入口
# ═════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BTC AHR999 定投指标工具")
    parser.add_argument("--web",   action="store_true", help="启动本地 Web 预览")
    parser.add_argument("--cli",   action="store_true", help="仅控制台输出")
    parser.add_argument("--once",  action="store_true", help="单次运行（默认）")
    parser.add_argument("--pages", action="store_true", help="生成 _site/ 静态站")
    parser.add_argument("--force-refresh", action="store_true", help="强制刷新数据")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="  %(asctime)s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.pages:
        run_pages(force_refresh=args.force_refresh)
    elif args.web:
        run_web()
    else:
        run_pipeline(force_refresh=args.force_refresh)
