@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   BTC AHR999 - 一键部署到 GitHub Pages
echo ============================================================
echo.

REM 检查 Git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Git 未安装或未加入 PATH
    echo     请访问 https://git-scm.com/download/win 下载安装
    echo     安装时选择 "Git from the command line and also from 3rd-party software"
    pause
    exit /b 1
)
echo [OK] Git 已就绪

REM 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python 未安装或未加入 PATH
    pause
    exit /b 1
)
echo [OK] Python 已就绪

echo.
set /p USERNAME="请输入 GitHub 用户名: "
set /p REPONAME="请输入仓库名 (默认: BTC-AHR999): "
if "%REPONAME%"=="" set REPONAME=BTC-AHR999

echo.
echo [*] 仓库地址: https://github.com/%USERNAME%/%REPONAME%.git
echo.
set /p CONFIRM="确认继续? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo 已取消
    pause
    exit /b 0
)

echo.
echo [*] 安装依赖...
python -m pip install -q -r requirements.txt

echo.
echo [*] 清除旧缓存，重新拉取数据...
if exist btc_cache.csv del btc_cache.csv

echo.
echo [*] 运行管道 + 生成 _site...
python start.py --pages

if %errorlevel% neq 0 (
    echo.
    echo [X] 管道运行失败，请检查上方错误
    pause
    exit /b 1
)

echo.
echo [*] 初始化 Git 仓库...
if not exist .git (
    git init -b main
) else (
    echo     (已有 Git 仓库，跳过 init)
)

echo.
echo [*] 添加文件 + 提交...
git add .
git commit -m "update: BTC AHR999 data %date%"

echo.
echo [*] 关联远程仓库...
git remote remove origin 2>nul
git remote add origin https://github.com/%USERNAME%/%REPONAME%.git

echo.
echo [*] 推送到 GitHub...
echo     注意: 密码栏请填 Personal Access Token (不是登录密码)
echo.
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [X] 推送失败
    echo     常见原因:
    echo     1. Token 权限不够 (需要 repo + workflow)
    echo     2. 仓库不存在 (请先在 GitHub 网页创建空仓库)
    echo     3. 用户名/仓库名拼写错误
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   ✅ 推送成功!
echo ============================================================
echo.
echo   接下来手动操作 (一次性):
echo   1. 打开 https://github.com/%USERNAME%/%REPONAME%/settings/pages
echo   2. Source 选择 "GitHub Actions"
echo   3. 保存
echo.
echo   然后访问:
echo   https://%USERNAME%.github.io/%REPONAME%/
echo.
echo   之后修改 manual_input.csv 后，双击 run_pages.bat 即可更新
echo.
pause
