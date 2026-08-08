import argparse
import os
import pandas as pd

from btc_data import load_and_clean_btc_data
from ahr999 import run_pipeline

def run_pages(src_path="btc_cache.csv"):
    print("🚀 开始生成静态站点...")

    if not os.path.exists(src_path):
        raise FileNotFoundError(
            f"❌ 错误: 找不到数据文件 '{src_path}'，请检查文件名或 --src 参数"
        )

    # 只从本地 CSV 读取并计算
    df = run_pipeline(src_path=src_path)

    # 取最新一根 K 线
    latest = df.dropna(subset=["ahr999"]).iloc[-1]

    site_dir = "_site"
    os.makedirs(site_dir, exist_ok=True)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>BTC AHR999 指标</title>
<style>
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  max-width: 820px; margin: 40px auto; padding: 0 20px;
  background: #f5f6fa; color: #222;
}}
.card {{
  background: #fff; padding: 24px; border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}}
.highlight {{ font-size: 1.25em; font-weight: 600; color: #d35400; }}
.zone {{
  font-size: 1.6em; font-weight: 700;
  color: {("#27ae60" if latest["zone"]=="极度低估" else "#e67e22")};
}}
.meta {{ color: #666; font-size: 0.95em; }}
</style>
</head>
<body>
<h1>₿ BTC AHR999 仪表盘</h1>

<div class="card">
  <p class="meta">📅 最新日期：<strong>{latest.name.strftime("%Y-%m-%d")}</strong></p>
  <p>📈 现价：<span class="highlight">${latest["close"]:,.2f}</span></p>
  <p>📐 AHR999：<span class="highlight">{latest["ahr999"]:.4f}</span></p>
  <p>🏷️ 区间：<span class="zone">{latest["zone"]}</span></p>
  <p>📊 较 SMA200 偏离幅度：{latest["deviation_pct"]:.2f}%</p>
  <p>🌐 幂律估值：${latest["index_growth_val"]:,.2f}</p>
</div>

<p class="meta" style="margin-top:16px;">
数据来源：本地 btc_cache.csv · 每日手动更新
</p>
</body>
</html>
"""

    with open(f"{site_dir}/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ 静态站点已生成到 ./{site_dir}/index.html")


def main():
    parser = argparse.ArgumentParser(description="BTC AHR999 静态站点生成器")
    parser.add_argument("--pages", action="store_true", help="生成静态站点文件")
    parser.add_argument("--src", default="btc_cache.csv", help="本地 BTC CSV 数据路径")

    args = parser.parse_args()

    if args.pages:
        run_pages(src_path=args.src)
    else:
        print("ℹ️ 未指定 --pages，不执行任何操作。")


if __name__ == "__main__":
    main()
