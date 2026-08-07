# ₿ BTC AHR999 定投指标站

> 自动计算比特币 AHR999 囤币指标，部署到 GitHub Pages，每日自动更新。

## ✨ 功能

- **AHR999 指标**：`(现价/200日均价) × (现价/幂律拟合价)`
- **区间标签**：极度低估 / 定投区 / 合理区 / 偏高 / 高估
- **异常检测**：单日涨跌幅 >15% 或成交量异常放大
- **买卖记账**：FIFO 计算持仓均价、浮动盈亏、已实现盈亏
- **静态站点**：纯 HTML + JS，无需服务器，GitHub Pages 免费托管

## 📊 数据源（三级降级）

| 优先级 | 数据源 | 说明 |
|:---:|---------|------|
| 1 | **Investing.com** | 用户指定，中文环境友好，免费无需 Key |
| 2 | **Stooq** | `stooq.com` 免费 CSV 下载，极稳定 |
| 3 | **Yahoo Finance** | `yfinance` 库兜底 |

缓存 6 小时，强制刷新时删除旧缓存重新拉取。

## 🚀 快速开始

### 本地运行

```cmd
cd C:\你的项目路径\btc-ahr999

:: 安装依赖（首次）
pip install -r requirements.txt

:: 生成静态站点（强制刷新数据）
py start.py --pages --force-refresh
```

成功后 `_site/` 目录包含：
- `index.html` — 网页入口
- `data.js` — 内嵌数据（离线可用）
- `ahr999_data.json` — 原始 JSON
- `BTC_AHR999.xlsx` — Excel 导出

### 部署到 GitHub Pages

```cmd
git add .
git commit -m "update: BTC AHR999 data"
git push
```

GitHub Actions 会自动：
1. 清理旧缓存
2. 运行 `py start.py --pages --force-refresh`
3. 验证产物完整性
4. 部署到 GitHub Pages

## 📁 文件结构

```
btc-ahr999/
├── .github/workflows/deploy-pages.yml   # CI/CD 自动部署
├── templates/index.html                  # 网页模板
├── ahr999.py                           # 核心：数据获取 + AHR999 计算
├── start.py                             # 入口：--pages/--web/--cli
├── config.py                            # 配置（费率/阈值/幂律参数）
├── requirements.txt                     # Python 依赖
├── manual_input.csv                     # 你的买卖记录
├── .gitignore                          # 忽略缓存/临时文件
└── README.md
```

## 📝 记录买卖操作

编辑 `manual_input.csv`：

```csv
日期,操作,价格,数量,手续费
2024-01-15,buy,42000,0.1,4.2
2024-06-20,sell,65000,0.05,3.25
```

列说明：
- **日期**：`YYYY-MM-DD` 格式
- **操作**：`buy` 或 `sell`
- **价格**：单 BTC 价格（USD）
- **数量**：BTC 数量
- **手续费**：本次手续费（USD）

改完后重新运行 `py start.py --pages --force-refresh` 并推送。

## ⚙️ 命令行参数

| 参数 | 说明 |
|------|------|
| `--pages` | 生成 `_site/` 静态站点 |
| `--web` | 启动本地 Flask 预览（默认 `http://localhost:5000`） |
| `--cli` | 仅控制台输出摘要 |
| `--once` | 单次运行（默认行为） |
| `--force-refresh` | 强制删除缓存，重新拉取数据 |

## 🔧 常见问题

**Q: 终端显示数据源失败怎么办？**
A: 检查网络能否访问 `cn.investing.com`。如果在中国大陆，可能需要代理。三个数据源都失败时会抛出明确错误。

**Q: AHR999 数值为 0 或 NaN？**
A: 数据不足 200 天时会显示 NaN（正常）。如果长期为 0，检查数据是否成功拉取。

**Q: GitHub Actions 部署后 404？**
A: 确认 Settings → Pages → Source 选的是 **GitHub Actions**。

**Q: 怎么修改幂律参数？**
A: 编辑 `ahr999.py` 中的 `POWER_LAW_A` 和 `POWER_LAW_B` 常量。

## 📄 License

MIT
