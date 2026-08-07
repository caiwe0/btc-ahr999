@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   BTC AHR999 - GitHub Pages 静态生成
echo ============================================================
echo.

REM 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python 未安装或未加入 PATH
    echo     请访问 https://python.org 下载安装，勾选 "Add to PATH"
    pause
    exit /b 1
)
echo [OK] Python 已就绪

REM 安装依赖
echo.
echo [*] 安装/更新依赖...
python -m pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo [X] 依赖安装失败
    pause
    exit /b 1
)
echo [OK] 依赖就绪

REM 删除旧缓存，强制拉新数据
echo.
echo [*] 清除旧缓存...
if exist btc_cache.csv del btc_cache.csv

REM 运行 Pages 模式
echo.
echo [*] 运行数据管道 + 生成静态文件...
echo.
python start.py --pages

if %errorlevel% neq 0 (
    echo.
    echo [X] 运行失败，请检查上方错误信息
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   检查 _site 目录内容:
echo ============================================================
dir _site /B

echo.
echo [OK] 完成! 接下来:
echo   1. git add .
echo   2. git commit -m "update data"
echo   3. git push
echo.
pause
