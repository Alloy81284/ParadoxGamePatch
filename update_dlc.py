import os
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import zipfile
from datetime import datetime
import shutil
import logging
from pathlib import Path
import re
import sys
import time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import islice
import random
import hashlib

# 配置日志和输出目录
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
# 修改输出目录
output_dir = "F:/NEW"
# 配置源文件目录的绝对路径
base_dir = "F:/NEW"  # 脚本所在目录的绝对路径
正版补丁目录 = os.path.join(base_dir, "正版DLC破解补丁")
局域网补丁目录 = os.path.join(base_dir, "局域网DLC破解补丁")

os.makedirs(log_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'dlc_updater.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Steam API配置
STEAM_API_URL = "https://api.steampowered.com/ISteamApps/GetAppList/v2"
STEAM_STORE_API_URL = "https://store.steampowered.com/api/appdetails"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive'
}

GAME_IDS = {
    "Cities: Skylines": 255710,
    "Cities: Skylines II": 949230,
    "Crusader Kings II": 203770,
    "Crusader Kings III": 1158310,
    "Europa Universalis IV": 236850,
    "Hearts of Iron IV": 394360,
    "Imperator: Rome": 859580,
    "Stellaris": 281990,
    "Victoria 3": 529340
}

# 配置请求会话
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # 增加重试次数
        backoff_factor=2,  # 增加退避因子
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        respect_retry_after_header=True  # 尊重服务器的重试建议
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,  # 从1增加到20
        pool_maxsize=20,     # 从1增加到20
        pool_block=True      # 改为True，连接池满时阻塞等待
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# 创建全局会话
session = create_session()

def get_app_list():
    """获取Steam应用列表"""
    try:
        response = session.get(STEAM_API_URL, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get('applist', {}).get('apps'):
                return {app['appid']: app['name'] for app in data['applist']['apps']}
        return {}
    except Exception as e:
        logging.error(f"获取应用列表失败: {str(e)}")
        return {}

def get_single_dlc_info(dlc_appid):
    """获取单个DLC的详细信息"""
    max_retries = 3
    retry_count = 0
    while retry_count < max_retries:
        try:
            params = {
                'appids': dlc_appid,
                'filters': 'basic',
                'cc': 'us',
                'l': 'english'
            }
            response = session.get(STEAM_STORE_API_URL, params=params, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                data = response.json()
                dlc_info = data.get(str(dlc_appid), {})
                if isinstance(dlc_info, dict) and dlc_info.get('success', False):
                    dlc_details = dlc_info.get('data', {})
                    if isinstance(dlc_details, dict):
                        dlc_name = dlc_details.get('name', f'Unknown DLC {dlc_appid}')
                        return str(dlc_appid), dlc_name
            return None
        except Exception as e:
            retry_count += 1
            time.sleep(2)
            continue
    return None

def get_steam_dlc(app_id):
    """使用 Steam 商店 API 获取DLC信息（并发逐个请求模式）"""
    try:
        # 获取应用详情，获得 DLC AppID 列表
        params = {
            'appids': app_id,
            'filters': 'basic,dlc',
            'cc': 'us',
            'l': 'english'
        }
        logging.info(f"正在获取游戏 {app_id} 的DLC列表...")
        response = session.get(STEAM_STORE_API_URL, params=params, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            logging.error(f"Steam 商店 API请求失败 (AppID: {app_id}): HTTP {response.status_code}")
            return {}
        
        data = response.json()
        if not isinstance(data, dict):
            logging.error(f"无效的API响应格式 (AppID: {app_id}): {type(data)}")
            return {}
            
        app_data = data.get(str(app_id), {})
        if not app_data:
            logging.error(f"未找到游戏数据 (AppID: {app_id})")
            return {}
            
        if not app_data.get('success', False):
            logging.error(f"Steam 商店 API返回错误 (AppID: {app_id}): {app_data.get('error', 'Unknown error')}")
            return {}
            
        game_info = app_data.get('data', {})
        if not isinstance(game_info, dict):
            logging.error(f"无效的游戏信息格式 (AppID: {app_id}): {type(game_info)}")
            return {}
            
        dlc_list = game_info.get('dlc', [])
        if not dlc_list:
            logging.warning(f"未找到DLC列表 (AppID: {app_id})")
            return {}
            
        logging.info(f"找到 {len(dlc_list)} 个DLC，开始并发获取详细信息...")
        
        # 使用线程池并发获取DLC信息，降低并发数
        dlc_dict = {}
        with ThreadPoolExecutor(max_workers=3) as executor:  # 降低到3个并发
            # 创建任务，每个DLC一个任务
            future_to_dlc = {
                executor.submit(get_single_dlc_info, dlc_appid): dlc_appid 
                for dlc_appid in dlc_list
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_dlc):
                dlc_appid = future_to_dlc[future]
                try:
                    result = future.result()
                    if result:
                        dlc_id, dlc_name = result
                        dlc_dict[dlc_id] = dlc_name
                        logging.info(f"添加DLC: {dlc_id} = {dlc_name}")
                except Exception as e:
                    logging.warning(f"处理DLC {dlc_appid} 时发生错误: {str(e)}")
                time.sleep(0.3)  # 增加延迟到0.3秒
        
        if not dlc_dict:
            logging.warning(f"未找到任何DLC (AppID: {app_id})")
        else:
            logging.info(f"成功获取 {len(dlc_dict)} 个DLC (AppID: {app_id})")
            
        return dlc_dict
        
    except requests.exceptions.RequestException as e:
        logging.error(f"网络请求错误 (AppID: {app_id}): {str(e)}")
        return {}
    except Exception as e:
        logging.error(f"获取DLC信息失败 (AppID: {app_id}): {str(e)}")
        return {}

def parse_existing_dlc_from_ini(ini_path):
    """解析cream_api.ini中每个游戏的已存在DLC ID集合"""
    if not os.path.exists(ini_path):
        return {}
    with open(ini_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    game_dlc = {}
    current_game = None
    in_dlc_block = False
    for line in lines:
        line_strip = line.strip()
        if line_strip.startswith(';') and not line_strip.startswith(';lowviolence'):
            # 识别游戏名
            current_game = line_strip[1:].strip()
            in_dlc_block = False
        elif line_strip == '[dlc]':
            in_dlc_block = True
        elif line_strip.startswith('[') and line_strip != '[dlc]':
            in_dlc_block = False
        elif in_dlc_block and '=' in line_strip and current_game:
            dlc_id = line_strip.split('=', 1)[0].strip()
            game_dlc.setdefault(current_game, set()).add(dlc_id)
    return game_dlc

def parse_existing_dlc_from_txt(txt_path):
    """解析DLC.txt中每个游戏的已存在DLC ID集合"""
    if not os.path.exists(txt_path):
        return {}
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    game_dlc = {}
    current_game = None
    for line in lines:
        line_strip = line.strip()
        if line_strip.startswith(';'):
            current_game = line_strip[1:].strip()
        elif '=' in line_strip and current_game:
            dlc_id = line_strip.split('=', 1)[0].strip()
            game_dlc.setdefault(current_game, set()).add(dlc_id)
    return game_dlc

def append_new_dlc_to_ini(ini_path, new_dlc_dict):
    """将新DLC追加到cream_api.ini对应区块末尾"""
    if not os.path.exists(ini_path):
        logging.error(f"找不到 {ini_path}")
        return
    with open(ini_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 找到每个游戏区块的结束位置
    game_blocks = {}
    current_game = None
    block_start = None
    in_dlc_block = False
    dlc_block_end = None
    
    for idx, line in enumerate(lines):
        line_strip = line.strip()
        if line_strip.startswith(';') and not line_strip.startswith(';lowviolence'):
            if current_game and block_start is not None:
                game_blocks[current_game] = (block_start, dlc_block_end if dlc_block_end else idx)
            current_game = line_strip[1:].strip()
            block_start = idx
            in_dlc_block = False
            dlc_block_end = None
        elif line_strip == '[dlc]':
            in_dlc_block = True
        elif line_strip.startswith('[') and line_strip != '[dlc]':
            if in_dlc_block:
                dlc_block_end = idx
            in_dlc_block = False
        elif not line_strip and in_dlc_block:  # 找到DLC区块中的空行
            dlc_block_end = idx
    
    # 处理最后一个区块
    if current_game and block_start is not None:
        game_blocks[current_game] = (block_start, dlc_block_end if dlc_block_end else len(lines))
    
    # 构建新的文件内容
    output_lines = []
    current_pos = 0
    
    for game_name, (start, end) in sorted(game_blocks.items(), key=lambda x: x[1][0]):
        # 添加区块开始到结束的内容
        output_lines.extend(lines[current_pos:end])
        
        # 如果有新DLC，添加到区块末尾
        if game_name in new_dlc_dict and new_dlc_dict[game_name]:
            # 确保在区块末尾添加一个空行
            if output_lines and output_lines[-1].strip():
                output_lines.append('\n')
            # 添加新DLC，按ID排序
            for dlc_id, dlc_name in sorted(new_dlc_dict[game_name].items(), key=lambda x: int(x[0])):
                output_lines.append(f"{dlc_id} = {dlc_name}\n")
            logging.info(f"{game_name} 追加 {len(new_dlc_dict[game_name])} 个新DLC到cream_api.ini")
        
        current_pos = end
    
    # 添加剩余内容
    output_lines.extend(lines[current_pos:])
    
    with open(ini_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)

def append_new_dlc_to_txt(txt_path, new_dlc_dict):
    """将新DLC追加到DLC.txt对应游戏区块中，保持原始格式"""
    if not os.path.exists(txt_path):
        logging.error(f"找不到 {txt_path}")
        return
        
    # 读取现有内容
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 按游戏名分割内容
    game_sections = content.split('#')
    output_sections = []
    
    # 处理每个游戏区块
    for section in game_sections:
        if not section.strip():
            continue
            
        # 分离游戏名和DLC列表
        lines = section.strip().split('\n')
        game_name = lines[0].strip()
        dlc_lines = [line.strip() for line in lines[1:] if line.strip()]
        
        # 获取该游戏的新DLC
        new_dlc = new_dlc_dict.get(game_name, {})
        if new_dlc:
            # 将新DLC添加到现有DLC列表中
            existing_dlc = {line.split('=')[0].strip(): line for line in dlc_lines}
            for dlc_id, dlc_name in sorted(new_dlc.items(), key=lambda x: int(x[0])):
                dlc_line = f"{dlc_id} = {dlc_name}"
                if dlc_id not in existing_dlc:
                    dlc_lines.append(dlc_line)
            
            # 重新排序所有DLC
            dlc_lines.sort(key=lambda x: int(x.split('=')[0].strip()))
            
            # 构建新的游戏区块
            section_content = f"# {game_name}\n" + '\n'.join(dlc_lines)
            output_sections.append(section_content)
            logging.info(f"{game_name} 追加 {len(new_dlc)} 个新DLC到DLC.txt")
        else:
            # 如果没有新DLC，保持原样
            output_sections.append(f"#{section.strip()}")
    
    # 写入文件
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(output_sections))

def update_cream_api_ini_and_dlc_txt():
    """主流程：只追加新DLC，原有内容不变"""
    ini_path = os.path.join(正版补丁目录, 'cream_api.ini')
    txt_path = os.path.join(局域网补丁目录, 'steam_settings', 'DLC.txt')
    
    # 解析原有DLC
    ini_existing = parse_existing_dlc_from_ini(ini_path)
    txt_existing = parse_existing_dlc_from_txt(txt_path)
    
    # 使用线程池并发获取最新DLC，降低并发数
    new_dlc_for_ini = {}
    new_dlc_for_txt = {}
    
    with ThreadPoolExecutor(max_workers=1) as executor:  # 降低到1个并发
        # 创建任务
        future_to_game = {
            executor.submit(get_steam_dlc, app_id): game_name 
            for game_name, app_id in GAME_IDS.items()
        }
        
        # 处理完成的任务
        for future in as_completed(future_to_game):
            game_name = future_to_game[future]
            try:
                latest_dlc = future.result()
                # ini处理
                ini_game_dlc = ini_existing.get(game_name, set())
                ini_new = {dlc_id: dlc_name for dlc_id, dlc_name in latest_dlc.items() if dlc_id not in ini_game_dlc}
                if ini_new:
                    new_dlc_for_ini[game_name] = ini_new
                # txt处理
                txt_game_dlc = txt_existing.get(game_name, set())
                txt_new = {dlc_id: dlc_name for dlc_id, dlc_name in latest_dlc.items() if dlc_id not in txt_game_dlc}
                if txt_new:
                    new_dlc_for_txt[game_name] = txt_new
            except Exception as e:
                logging.error(f"处理游戏 {game_name} 的DLC时发生错误: {str(e)}")
    
    # 追加新DLC
    append_new_dlc_to_ini(ini_path, new_dlc_for_ini)
    append_new_dlc_to_txt(txt_path, new_dlc_for_txt)
    logging.info("所有新DLC追加完成")

def create_zip_archive():
    """创建带日期的zip压缩包"""
    try:
        # 获取当前日期
        current_date = datetime.now().strftime("%Y.%m.%d")
        
        # 创建临时目录
        temp_dir = os.path.join(base_dir, "temp_backup")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        # 复制文件到临时目录
        shutil.copytree(正版补丁目录, os.path.join(temp_dir, "正版DLC破解补丁"))
        shutil.copytree(局域网补丁目录, os.path.join(temp_dir, "局域网DLC破解补丁"))
        
        # 创建zip文件（修改输出路径到output目录）
        zip_filename = os.path.join(output_dir, f"【{current_date}】P社游戏DLC破解补丁.zip")
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)
        
        # 清理临时目录
        shutil.rmtree(temp_dir)
        
        logging.info(f"成功创建压缩包: {zip_filename}")
    except Exception as e:
        logging.error(f"创建压缩包失败: {str(e)}")

def main():
    try:
        logging.info("开始检查DLC更新...")
        
        # 获取更新前的文件哈希值
        ini_path = os.path.join(正版补丁目录, 'cream_api.ini')
        txt_path = os.path.join(局域网补丁目录, 'steam_settings', 'DLC.txt')
        
        ini_hash_before = None
        txt_hash_before = None
        if os.path.exists(ini_path):
            with open(ini_path, "rb") as f:
                ini_hash_before = hashlib.md5(f.read()).hexdigest()
        if os.path.exists(txt_path):
            with open(txt_path, "rb") as f:
                txt_hash_before = hashlib.md5(f.read()).hexdigest()
        
        # 更新DLC
        update_cream_api_ini_and_dlc_txt()
        
        # 获取更新后的文件哈希值
        ini_hash_after = None
        txt_hash_after = None
        if os.path.exists(ini_path):
            with open(ini_path, "rb") as f:
                ini_hash_after = hashlib.md5(f.read()).hexdigest()
        if os.path.exists(txt_path):
            with open(txt_path, "rb") as f:
                txt_hash_after = hashlib.md5(f.read()).hexdigest()
        
        # 检查是否有文件发生变化
        has_changes = (ini_hash_before != ini_hash_after) or (txt_hash_before != txt_hash_after)
        
        if has_changes:
            logging.info("检测到DLC更新，开始创建新的压缩包...")
            create_zip_archive()
            logging.info("压缩包创建完成")
        else:
            logging.info("未检测到DLC更新，跳过创建压缩包")
            
        logging.info("所有任务完成")
    except Exception as e:
        logging.error(f"执行过程中发生错误: {str(e)}")

if __name__ == "__main__":
    main() 