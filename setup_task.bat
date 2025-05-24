@echo off
setlocal enabledelayedexpansion

:: 获取脚本所在目录的绝对路径
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: 获取Python路径
for /f "tokens=*" %%i in ('where python') do set "PYTHON_PATH=%%i"

:: 创建任务名称
set "TASK_NAME=P社游戏DLC更新任务"

:: 检查任务是否已存在
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo 任务已存在，正在更新...
    schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo 创建新任务...
)

:: 创建新任务
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%\update_dlc.py\"" /sc daily /st 00:00 /ru SYSTEM /f

if %errorlevel% equ 0 (
    echo 任务创建成功！
    echo 任务将在每天00:00自动运行
) else (
    echo 任务创建失败，请以管理员身份运行此脚本
    pause
    exit /b 1
)

:: 显示当前任务配置
echo.
echo 当前任务配置：
schtasks /query /tn "%TASK_NAME%" /v /fo list

echo.
echo 设置完成！
pause 