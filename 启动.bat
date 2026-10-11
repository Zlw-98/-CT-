@echo off
chcp 65001 >nul
title 腹部CT体成分分析工具 · 原型
cd /d "%~dp0"

rem ---- 运行环境（WorkBuddy 托管 venv，已装 PySide6/pydicom/numpy/scipy）----
set "VENV=C:\Users\Levin Zhang\.workbuddy\binaries\python\envs\default\Scripts"

if exist "%VENV%\pythonw.exe" (
    start "" "%VENV%\pythonw.exe" "%~dp0main.py"
    exit /b 0
)
if exist "%VENV%\python.exe" (
    start "" "%VENV%\python.exe" "%~dp0main.py"
    exit /b 0
)

echo.
echo   [错误] 未找到运行环境：
echo      %VENV%
echo.
echo   请确认 WorkBuddy 的 Python 环境路径是否变化，
echo   或用以下命令直接运行以便查看报错：
echo      "%VENV%\python.exe" "%~dp0main.py"
echo.
pause
exit /b 1
