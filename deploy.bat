@echo off
chcp 65001 >nul
echo ══════════════════════════════════════
echo   BTC AHR999 — 一键部署到 GitHub Pages
echo ══════════════════════════════════════
echo.

REM 1. 安装依赖
echo [1/4] 检查并安装 Python 依赖...
py -m pip install -r requirements.txt --quiet 2>&1 | findstr /V "WARNING"
if errorlevel 1 (
    python -m pip install -r requirements.txt --quiet 2>&1 | findstr /V "WARNING"
)
echo     ✅ 依赖就绪
echo.

REM 2. 生成静态文件
echo [2/4] 生成静态站点文件（拉取真实 BTC 数据）...
py start.py --pages --force-refresh
if errorlevel 1 (
    echo     ⚠️ 拉取失败，尝试使用缓存/合成数据...
    py start.py --pages
)
echo.

REM 3. Git 初始化 + 提交
echo [3/4] 提交到 Git...
if not exist .git (
    git init -b main 2>nul
)
git add .
git commit -m "feat: add BTC AHR999 with real Binance data" 2>nul
echo     ✅ 已提交
echo.

REM 4. 提示推送
echo [4/4] 推送到 GitHub
echo ──────────────────────────────────────
echo  下一步：
echo    1. 在 GitHub 网页上创建仓库 "BTC-AHR999"
echo    2. 运行以下命令关联并推送：
echo.
echo    git remote add origin https://github.com/YOUR_USERNAME/BTC-AHR999.git
echo    git push -u origin main
echo.
echo    3. Settings → Pages → Source 选 "GitHub Actions"
echo    4. 访问 https://YOUR_USERNAME.github.io/BTC-AHR999/
echo ──────────────────────────────────────
echo.
pause
