@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   BTC AHR999 - 更新数据并推送到 GitHub
echo ============================================================
echo.

REM 拉最新
echo [*] 拉取远程最新...
git pull origin main 2>nul

REM 运行管道
echo.
echo [*] 清除旧缓存...
if exist btc_cache.csv del btc_cache.csv

echo.
echo [*] 重新生成数据...
python start.py --pages

if %errorlevel% neq 0 (
    echo.
    echo [X] 生成失败，请检查上方错误
    pause
    exit /b 1
)

REM 提交推送
echo.
echo [*] 提交并推送...
git add .
git commit -m "update data: %date% %time%"
git push origin main

if %errorlevel% neq 0 (
    echo.
    echo [X] 推送失败
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   ✅ 完成! 1-3 分钟后访问你的 GitHub Pages 网址
echo ============================================================
echo.
pause
