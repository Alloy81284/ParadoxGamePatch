#!/bin/bash

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PYTHON_PATH=$(which python3)

# 创建crontab条目
CRON_JOB="0 0 * * * cd ${SCRIPT_DIR} && ${PYTHON_PATH} ${SCRIPT_DIR}/update_dlc.py >> ${SCRIPT_DIR}/logs/cron.log 2>&1"

# 检查是否已存在相同的crontab条目
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "${SCRIPT_DIR}/update_dlc.py")

if [ -z "$EXISTING_CRON" ]; then
    # 添加新的crontab条目
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "已成功添加计划任务！"
    echo "任务将在每天00:00自动运行"
else
    echo "计划任务已存在，无需重复添加"
fi

# 显示当前的crontab配置
echo -e "\n当前的crontab配置："
crontab -l

# 设置脚本执行权限
chmod +x "${SCRIPT_DIR}/update_dlc.py"
chmod +x "${SCRIPT_DIR}/setup_cron.sh"

echo -e "\n设置完成！" 