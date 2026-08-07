# BTC AHR999 · 修复版使用说明

## 这次修了什么（为什么之前是合成数据）

| 问题 | 现象 | 修复 |
|---|---|---|
| `--force-refresh` 没透传 | 加了参数还是读缓存 | `start.py` 把参数真正传给 `fetch_btc_data(force_refresh=...)` |
| Binance 分页传了 `endTime` | API 忽略分页，只返回 1000 行 → 触发"全部失败" → 走合成数据 | 改成**只传 `startTime+limit`，靠推进 startTime 翻页** |
| AHR999 直接除 MA200 | 早期 MA200=0 → 除零 → 全表 AHR999=0 | `np.where` 防御，分母为 0 时返回 `NaN` |
| 幂律参数是 2013 年校准的 | 2026 年算出来天文数字 | 用 2013/2017/2021/2024/2026 关键点重新拟合 |
| 网页模板字段名写错 | 表格里操作/价格/手续费等列全空 | 已对齐 `micro_state / buy_price / hold_qty` 等字段 |

## 本地验证（最关键的一步）

```cmd
cd C:\Users\CBB1\Downloads\btc-ahr999-final

:: 装依赖（第一次需要）
pip install -r requirements.txt

:: 强制从 Binance 拉真实数据
py start.py --pages --force-refresh
```

**成功标志**（终端里应该看到）：
```
🔗 Binance 连通性测试通过
📡 数据源: Binance (公开API)
📄 Binance 数据: 4900+ 行 (2013-01-02 → 2026-08-08)
📐 AHR999 有效数据: 4800+/4900+ 行
...
💰 最新 AHR999: 1.xxxx   ← 不是 0.0000！
📊 区间: 定投区 / 合理偏高
📡 数据源: binance
```

如果看到 `📡 数据源: binance` + `AHR999: 非零` → ✅ 真实数据生效。

## 推送到 GitHub

```cmd
git add .
git commit -m "fix: force-refresh 生效 + Binance 分页修复 + 真实 AHR999"
git push
```

GitHub Actions 会自动：
1. 运行 `py start.py --pages --force-refresh`（每次都拉最新数据）
2. 验证 `data.js / ahr999_data.json` 是否存在
3. 检查 AHR999 是否非零
4. 部署到 GitHub Pages

## 文件清单

| 文件 | 作用 |
|---|---|
| `ahr999.py` | 核心：Binance 拉取 + AHR999 计算 + 异常检测 + 买卖记账 |
| `start.py` | 入口：`--pages --force-refresh` 生成静态站 |
| `config.py` | 配置：费率/阈值/幂律参数（2026 校准） |
| `.github/workflows/deploy-pages.yml` | CI/CD：每日自动更新 + 强制刷新 |
| `requirements.txt` | Python 依赖 |
| `.gitignore` | 忽略缓存/临时文件 |

## 常见问题

**Q: 终端显示 `Binance 失败: ...` 然后走了 Yahoo/缓存/合成？**
A: 你的网络可能访问不了 `api.binance.com`。试：
1. 挂代理后再跑
2. 或改成调用代理后的地址
3. 或等网络恢复，Yahoo 备选一般也能拉到

**Q: 怎么确认网页用的是真实数据？**
A: 页面顶部会显示数据源标识（🟢 Binance / 🔵 Yahoo / ⚠️ 合成数据）。
也可以看 AHR999 数值：真实数据通常在 0.3~5 之间波动，不会是 0.0000。

**Q: 改了买卖记录怎么更新？**
A: 编辑 `manual_input.csv` → `py start.py --pages --force-refresh` → `git push`。
或直接 push 到 GitHub，Actions 会自动重算。
