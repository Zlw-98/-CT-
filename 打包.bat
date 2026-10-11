@echo off
chcp 65001 >nul
title 打包 腹部CT体成分面积分析工具
cd /d "%~dp0"

rem ---- 运行环境（WorkBuddy 托管 venv）----
set "VENV=C:\Users\Levin Zhang\.workbuddy\binaries\python\envs\default\Scripts"

if not exist "%VENV%\python.exe" (
    echo   [错误] 未找到 Python 环境：%VENV%
    pause
    exit /b 1
)

echo   正在打包（onedir）……
"%VENV%\python.exe" -m PyInstaller --noconfirm build.spec
if errorlevel 1 (
    echo   [错误] 打包失败，请查看上面的输出。
    pause
    exit /b 1
)

echo.
echo   打包完成，产物目录： dist\腹部CT体成分分析工具\
echo   双击其中的「腹部CT体成分分析工具.exe」即可运行。
pause
