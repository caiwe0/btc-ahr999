# ₿ BTC AHR999 指标表 + GitHub Pages 自动部署

BTC AHR999 定投指标看板，自动计算 AHR999 指数、异常K线检测、买卖盈亏核算，部署到 GitHub Pages 免费托管。

## ✨ 功能

- **AHR999 实时计算**：200日定投成本 × 幂律拟合价
- **实价价值 + 偏离幅度**：顶部状态栏一目了然
- **异常K线五态检测**：极端涨跌 / 横盘放量 / 量价背离
- **FIFO 买卖盈亏**：精确核算每笔卖出利润
- **6 区块汇总面板**：持仓 / 均价 / 浮动盈亏 / 已实现盈亏 / 总收益率 / 实价价值
- **完全免费托管**：GitHub Pages + Actions 自动更新

## 🚀 快速部署（Windows）

### 第一步：准备环境

1. **安装 Python**（勾选 "Add to PATH"）：https://python.org/downloads/
2. **安装 Git**（选 "Git from command line"）：https://git-scm.com/download/win
3. **创建 GitHub Personal Access Token**：
   - GitHub → Settings → Developer settings → Personal access tokens
   - 勾选 `repo` + `workflow` 权限
   - **保存好这个 Token，只显示一次！**

### 第二步：双击部署

1. 解压项目到任意目录（建议 `D:\code\btc-ahr999\`）
2. 双击 **`deploy.bat`**
3. 按提示输入：
   - GitHub 用户名
   - 仓库名（默认 `BTC-AHR999`）
   - 密码栏填你的 **Personal Access Token**
4. 等待推送完成

### 第三步：开启 GitHub Pages

1. 浏览器打开 `https://github.com/你的用户名/BTC-AHR999/settings/pages`
2. **Source** 选择 `GitHub Actions`
3. 保存

### 第四步：访问网站

等待 1-3 分钟，打开：

```
https://你的用户名.github.io/BTC-AHR999/
```

## 📝 修改买卖记录后更新

编辑 `manual_input.csv`：

```csv
date,action,price,amount
2020-03-13,buy,5000,1000
2024-08-05,buy,52000,500
2025-03-10,sell,95000,100000
```

然后 **双击 `update.bat`** → 自动重算 + 推送 → 网页自动更新。

## 📊 数据来源

自动降级策略：
1. **Binance 公开 API**（主源，最稳定，无需 Key）
2. **Yahoo Finance**（备用）
3. **本地缓存**（离线可用）
4. **合成数据**（最后兜底，保证脚本永远能跑）

## 📁 项目结构

```
btc-ahr999/
├── .github/workflows/deploy-pages.yml   # GitHub Actions 自动部署
├── templates/index.html                   # 网页模板
├── .gitignore
├── README.md
├── ahr999.py                             # 核心逻辑
├── config.py                             # 配置（费率/阈值/颜色）
├── start.py                              # 启动入口
├── manual_input.csv                      # 买卖记录（编辑这个！）
├── requirements.txt                      # Python 依赖
├── deploy.bat                           # 首次部署（双击）
├── update.bat                           # 更新数据（双击）
└── run_pages.bat                        # 仅生成本地 _site/
```

## ⚙️ 配置说明

编辑 `config.py`：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `FEE_RATE` | 0.001 | 手续费率（0.1%） |
| `EXTREME_LOW` | 0.45 | AHR999 极度低估阈值 |
| `DIP_ZONE` | 1.2 | 定投区上限 |
| `FAIR_HIGH` | 4.0 | 合理偏高上限 |
| `POWER_LAW_A/B` | 1.51e-11 / 5.82 | 幂律拟合参数 |

## 🔧 手动命令行

```bash
python start.py --pages   # 生成 _site/ 静态文件
python start.py --web     # 本地 Flask 服务 (localhost:5000)
python start.py --cli     # 只生成 Excel/JSON
```

## 📄 License

MIT
