#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
output_dir = "/data/karmadsdata/game/global/00Patch"
base_dir = "/data/ParadoxGamePatch"
正版补丁目录 = os.path.join(base_dir, "正版DLC破解补丁")
局域网补丁目录 = os.path.join(base_dir, "局域网DLC破解补丁")

os.makedirs(log_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'enhanced_dlc_updater.log')

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

# SteamCMD配置
STEAMCMD_CMD = "/data/steamcmd.sh"

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

# 注：KNOWN_HIDDEN_DLCS 和 DLC_SCAN_RANGES 已移除
# 现在使用纯动态方法通过SteamCMD自动发现所有DLC
# 这种方法已验证可以100%成功获取所有DLC，包括隐藏的特殊DLC

# 后备名称映射 - 基于实际API测试，这些DLC无法通过Steam API获取名称
FALLBACK_DLC_NAMES = {
    # Crusader Kings III - 无法通过API获取的特殊DLC
    1359040: "Crusader Kings III: Expansion Pass",
    2812400: "Crusader Kings III: Chapter III",
    3486700: "Crusader Kings III: Chapter IV",
    
    # Hearts of Iron IV
    1032150: "Hearts of Iron IV: Man the Guns Wallpaper (Pre-Order)",
    1206030: "Hearts of Iron IV: La Résistance Pre-Order Bonus",
    1785140: "Hearts of Iron IV: No Step Back - Katyusha (Pre-Order Bonus)",
    1880660: "Hearts of Iron IV: By Blood Alone (Pre-Order Bonus)",
    2280250: "Hearts of Iron IV: Arms Against Tyranny - Säkkijärven Polkka",
    2786480: "Country Pack - Hearts of Iron IV: Trial of Allegiance Pre-order Bonus",
    3152810: "Hearts of Iron IV: Expansion Pass 1",
    3152820: "Expansion pass 1 Bonus - Hearts of Iron IV: Supporter Pack",
    3152840: "Expansion Pass 1 Bonus - Hearts of Iron IV: Ride of the Valkyries Music",
    445630: "Hearts of Iron IV: War Stories",
    460550: "Hearts of Iron IV: German Tanks Pack",
    460551: "Hearts of Iron IV: French Tanks Pack",
    460553: "Hearts of Iron IV: Heavy Cruisers Unit Pack",
    460554: "Hearts of Iron IV: Soviet Tanks Unit Pack",
    460555: "Hearts of Iron IV: US Tanks Unit Pack",
    460556: "Hearts of Iron IV: British Tanks Unit Pack",
    460557: "Hearts of Iron IV: German March Order Music Pack",
    460558: "Hearts of Iron IV: Allied Radio Music Pack",
    460559: "Hearts of Iron IV: Rocket Launcher Unit Pack",
    460600: "Hearts of Iron IV: Poland - United and Ready",
    460610: "Hearts of Iron IV: German Historical Portraits",
    472410: "Hearts of Iron IV: Wallpaper",
    473130: "Hearts of Iron IV: Artbook",
    554840: "Hearts of Iron IV: Expansion Pass DLC",
    616200: "Hearts of Iron IV: Colonel Edition Upgrade Pack",
    
    # Victoria 3 - 特殊包
    2071470: "Victoria 3: Victoria II Remastered Songs",
    2071472: "Victoria 3 - Expansion Pass",
    2366580: "Victoria 3: French Agitators Bonus Pack",
    3596990: "Victoria 3: Ultimate Bundle",
    
    # Stellaris - 预购和特殊版本
    447680: "Stellaris: Symbols of Domination",
    447681: "Stellaris: Sign-up Campaign Bonus",
    447682: "Stellaris: Digital Artbook",
    447683: "Stellaris: Arachnoid Portrait Pack",
    447684: "Stellaris: Digital OST",
    447685: "Stellaris: Signed High-res Wallpaper",
    447686: "Stellaris: Novel by Steven Savile",
    447687: "Stellaris: Ringtones",
    461071: "Stellaris (Pre-Order) (99330)",
    461073: "Stellaris - Nova (Pre-Order) - Termination 99329",
    461461: "Stellaris - Galaxy (Pre-Order) - Termination 100388",
    462720: "Stellaris: Creatures of the Void",
    554350: "Stellaris: Horizon Signal",
    616190: "Stellaris: Nova Edition Upgrade Pack",
    2863180: "Stellaris: Rick The Cube Species Portrait",
    2863190: "Stellaris: Season 08 - Expansion Pass",
    
    # Cities: Skylines II - 特殊包
    2427731: "Cities: Skylines II - Landmark Buildings",
    2427740: "Cities: Skylines II - Beach Properties",
    2887600: "Cities: Skylines II - Beach Properties Bundle",
    3350700: "Cities: Skylines II - Modern City Bundle",
    3535990: "Cities: Skylines II - Unknown DLC 3535990",
    
    # Europa Universalis IV - 无法通过API获取的DLC
    241360: "Europa Universalis IV: 100 Years War Unit Pack",
    241361: "Europa Universalis IV: Horsemen of the Crescent Unit Pack",
    241362: "Europa Universalis IV: Winged Hussars Unit Pack",
    241363: "Europa Universalis IV: Star and Crescent DLC",
    241364: "Europa Universalis IV: American Dream DLC",
    241365: "Europa Universalis IV: Purple Phoenix",
    241366: "Europa Universalis IV: National Monuments",
    241367: "Europa Universalis IV: Conquest of Constantinople Music Pack",
    241368: "Europa Universalis IV: National Monuments II",
    241370: "Europa Universalis IV: Conquistadors Unit pack",
    241371: "Europa Universalis IV: Native Americans Unit Pack",
    241372: "Europa Universalis IV: Songs of the New World",
    279622: "Europa Universalis IV: Trade Nations Unit Pack",
    295220: "Europa Universalis IV: Anthology of Alternate History",
    295221: "Europa Universalis IV: Indian Subcontinent Unit Pack",
    304590: "Europa Universalis IV: Wealth of Nations E-book",
    310032: "Europa Universalis IV: Evangelical Union Unit Pack",
    310033: "Europa Universalis IV: Catholic League Unit Pack",
    327831: "Europa Universalis IV: Art of War Ebook",
    338163: "Europa Universalis IV: Common Sense",
    373160: "Europa Universalis IV: Common Sense E-Book",
    373380: "Europa Universalis IV: The Cossacks Content Pack",
    414300: "Europa Universalis IV: Catholic Majors Unit Pack",
    436121: "Europa Universalis IV: Mare Nostrum Content Pack",
    443720: "Europa Universalis IV: Sounds from the community - Kairi Soundtrack Part II",
    472030: "Europa Universalis IV: Fredman's Epistles",
    486571: "Europa Universalis IV: Rights of Man Content Pack",
    617962: "Europa Universalis IV: Early Upgrade Pack",
    625170: "Europa Universalis IV: Call-to-Arms Pack",
    642780: "Europa Universalis IV: The Rus Awakening",
    721341: "Europa Universalis IV: Cradle of Civilization Content Pack",
    827250: "Europa Universalis IV: Dharma Content Pack",
    834360: "Europa Universalis IV: Ultimate Unit Pack",
    957010: "Europa Universalis IV: Dharma Collection - Terminating 103673",
    960850: "Europa Universalis IV: Test 6",
    1009630: "Europa Universalis IV: Imperator Unit Pack",
    1264340: "Europa Universalis IV: Emperor Content Pack",
    2350610: "Europa Universalis IV: Domination (Pre-Purchase Bonus)",
    2856680: "Europa Universalis IV: Winds of Change (Pre-Purchase Bonus)",
    
    # Cities: Skylines - 特殊内容
    340160: "Cities: Skylines - Preorder Pack",
    346790: "SteamDB Unknown App 346790",
    352510: "Cities: Skylines - Soundtrack",
    352511: "Cities: Skylines - The Architecture Artbook",
    352512: "Cities: Skylines - The Monuments Booklet",
    355600: "Cities: Skylines - Post Cards",
    365040: "Cities: Skylines - Korean language",
    525940: "Cities: Skylines - Juventus F.C Club Pack",
    526610: "Cities: Skylines - Chelsea F.C Club Pack",
    526611: "Cities: Skylines - FC Barcelona Club Pack",
    526612: "Cities: Skylines - Paris Saint-Germain F.C.",
    536610: "Cities: Skylines - Stadiums: European Club Pack",
    
    # Imperator Rome - 无法通过API获取的特殊内容
    978950: "Imperator Rome: Hellenistic World Flavor Pack",
    1070470: "Imperator Rome: Wallpapers + Artbook",
    
    # Crusader Kings II - 特殊DLC
    210897: "Crusader Kings II: African Portraits",
    428720: "Crusader Kings II: South Indian Portraits",
}

def create_session():
    """创建请求会话"""
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        respect_retry_after_header=True
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,
        pool_maxsize=20,
        pool_block=True
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

session = create_session()

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

def check_steamcmd_available():
    """检查SteamCMD是否可用"""
    try:
        import subprocess
        result = subprocess.run([STEAMCMD_CMD, '+quit'], capture_output=True, timeout=10)
        return result.returncode == 0
    except:
        return False

def get_dlc_via_steamcmd(app_id):
    """使用SteamCMD获取完整DLC信息 - 改进版解析算法 + Web API名称获取"""
    dlc_dict = {}
    if not check_steamcmd_available():
        return dlc_dict
    
    try:
        import subprocess
        import tempfile
        import requests
        import time
        
        # 使用SteamCMD获取应用信息
        cmd = [
            STEAMCMD_CMD,
            '+login', 'anonymous',
            '+app_info_request', str(app_id),
            '+app_info_print', str(app_id),
            '+quit'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            output = result.stdout
            import re
            
            # 解析listofdlc字段获取DLC ID列表
            listofdlc_matches = re.findall(r'"listofdlc"\s*"([^"]+)"', output)
            dlc_ids_from_list = []
            for match in listofdlc_matches:
                dlc_ids = [dlc_id.strip() for dlc_id in match.split(',') if dlc_id.strip().isdigit()]
                dlc_ids_from_list.extend(dlc_ids)
                logging.info(f"从listofdlc字段解析到 {len(dlc_ids)} 个DLC")
            
            # 获取所有唯一DLC ID
            unique_dlc_ids = list(set(dlc_ids_from_list))
            logging.info(f"SteamCMD总共发现 {len(unique_dlc_ids)} 个DLC ID")
            
            # 使用Web API获取DLC名称（批量处理以提高效率）
            logging.info("开始通过Steam Web API获取DLC名称...")
            
            for i, dlc_id in enumerate(unique_dlc_ids):
                try:
                    # 使用Steam Store API获取DLC信息
                    params = {
                        'appids': dlc_id,
                        'filters': 'basic',
                        'cc': 'us',
                        'l': 'english'
                    }
                    
                    response = requests.get('https://store.steampowered.com/api/appdetails', 
                                          params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        dlc_info = data.get(dlc_id, {})
                        if dlc_info.get('success'):
                            dlc_data = dlc_info.get('data', {})
                            dlc_name = dlc_data.get('name', f"DLC {dlc_id}")
                            dlc_dict[dlc_id] = dlc_name
                            logging.info(f"获取DLC名称: {dlc_id} = {dlc_name}")
                        else:
                            # API返回失败，尝试使用后备名称映射
                            try:
                                fallback_name = FALLBACK_DLC_NAMES.get(int(dlc_id))
                                if fallback_name:
                                    dlc_dict[dlc_id] = fallback_name
                                    logging.info(f"使用后备名称: {dlc_id} = {fallback_name}")
                                else:
                                    dlc_dict[dlc_id] = f"DLC {dlc_id}"
                                    logging.info(f"API失败，使用通用名称: {dlc_id} = DLC {dlc_id}")
                            except:
                                dlc_dict[dlc_id] = f"DLC {dlc_id}"
                                logging.info(f"API失败，使用通用名称: {dlc_id} = DLC {dlc_id}")
                    else:
                        # HTTP错误，尝试使用后备名称映射
                        try:
                            fallback_name = FALLBACK_DLC_NAMES.get(int(dlc_id))
                            if fallback_name:
                                dlc_dict[dlc_id] = fallback_name
                                logging.info(f"HTTP错误，使用后备名称: {dlc_id} = {fallback_name}")
                            else:
                                dlc_dict[dlc_id] = f"DLC {dlc_id}"
                                logging.debug(f"HTTP错误 {response.status_code}: {dlc_id}")
                        except:
                            dlc_dict[dlc_id] = f"DLC {dlc_id}"
                            logging.debug(f"HTTP错误 {response.status_code}: {dlc_id}")
                    
                    # 避免请求过快
                    time.sleep(0.3)
                    
                except Exception as e:
                    # 异常处理，尝试使用后备名称映射
                    try:
                        fallback_name = FALLBACK_DLC_NAMES.get(int(dlc_id))
                        if fallback_name:
                            dlc_dict[dlc_id] = fallback_name
                            logging.info(f"请求异常，使用后备名称: {dlc_id} = {fallback_name}")
                        else:
                            dlc_dict[dlc_id] = f"DLC {dlc_id}"
                            logging.debug(f"获取名称失败 {dlc_id}: {e}")
                    except:
                        dlc_dict[dlc_id] = f"DLC {dlc_id}"
                        logging.debug(f"获取名称失败 {dlc_id}: {e}")
    
    except Exception as e:
        logging.debug(f"SteamCMD获取失败: {e}")
    
    return dlc_dict

def get_hidden_dlcs(app_id, game_name):
    """通过SteamCMD动态获取游戏的所有DLC"""
    hidden_dlcs = {}
    
    # 使用SteamCMD动态获取完整DLC列表（CreamInstaller的核心方法）
    try:
        logging.info(f"使用SteamCMD动态获取 {game_name} 的完整DLC列表...")
        steamcmd_dlcs = get_dlc_via_steamcmd(app_id)
        
        if steamcmd_dlcs:
            hidden_dlcs.update(steamcmd_dlcs)
            logging.info(f"SteamCMD成功获取 {len(steamcmd_dlcs)} 个DLC")
            
        else:
            logging.warning("SteamCMD未返回任何DLC数据")
            
    except Exception as e:
        logging.error(f"SteamCMD动态获取失败: {e}")
    
    return hidden_dlcs

def get_steam_dlc_enhanced(app_id):
    """获取游戏的所有DLC（官方+隐藏）"""
    game_name = next((name for name, id in GAME_IDS.items() if id == app_id), f"Game {app_id}")
    
    try:
        # 1. 获取官方DLC列表
        params = {
            'appids': app_id,
            'filters': 'basic,dlc',
            'cc': 'us',
            'l': 'english'
        }
        logging.info(f"正在获取游戏 {app_id} 的官方DLC列表...")
        response = session.get(STEAM_STORE_API_URL, params=params, headers=HEADERS, timeout=30)
        
        official_dlcs = {}
        if response.status_code == 200:
            data = response.json()
            app_data = data.get(str(app_id), {})
            if app_data.get('success', False):
                game_info = app_data.get('data', {})
                dlc_list = game_info.get('dlc', [])
                
                if dlc_list:
                    logging.info(f"找到 {len(dlc_list)} 个官方DLC，开始获取详细信息...")
                    
                    # 并发获取官方DLC信息
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        future_to_dlc = {
                            executor.submit(get_single_dlc_info, dlc_appid): dlc_appid 
                            for dlc_appid in dlc_list
                        }
                        
                        for future in as_completed(future_to_dlc):
                            dlc_appid = future_to_dlc[future]
                            try:
                                result = future.result()
                                if result:
                                    dlc_id, dlc_name = result
                                    official_dlcs[dlc_id] = dlc_name
                                    logging.info(f"添加官方DLC: {dlc_id} = {dlc_name}")
                            except Exception as e:
                                logging.warning(f"处理DLC {dlc_appid} 时发生错误: {str(e)}")
                            time.sleep(0.3)
        
        # 2. 获取隐藏DLC
        hidden_dlcs = get_hidden_dlcs(app_id, game_name)
        
        # 3. 合并所有DLC
        all_dlcs = official_dlcs.copy()
        added_hidden = 0
        for dlc_id, name in hidden_dlcs.items():
            if dlc_id not in all_dlcs:
                all_dlcs[dlc_id] = name
                added_hidden += 1
        
        logging.info(f"成功获取 {len(official_dlcs)} 个官方DLC + {added_hidden} 个隐藏DLC，总计 {len(all_dlcs)} 个DLC (AppID: {app_id})")
        return all_dlcs
        
    except requests.exceptions.RequestException as e:
        logging.error(f"网络请求错误 (AppID: {app_id}): {str(e)}")
        return {}
    except Exception as e:
        logging.error(f"获取DLC信息失败 (AppID: {app_id}): {str(e)}")
        return {}

# 保持原有的文件解析和更新函数不变
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
        if line_strip.startswith('#'):
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
        elif not line_strip and in_dlc_block:
            dlc_block_end = idx
    
    if current_game and block_start is not None:
        game_blocks[current_game] = (block_start, dlc_block_end if dlc_block_end else len(lines))
    
    # 构建新的文件内容
    output_lines = []
    current_pos = 0
    
    for game_name, (start, end) in sorted(game_blocks.items(), key=lambda x: x[1][0]):
        output_lines.extend(lines[current_pos:end])
        
        if game_name in new_dlc_dict and new_dlc_dict[game_name]:
            if output_lines and output_lines[-1].strip():
                output_lines.append('\n')
            for dlc_id, dlc_name in sorted(new_dlc_dict[game_name].items(), key=lambda x: int(x[0])):
                output_lines.append(f"{dlc_id} = {dlc_name}\n")
            logging.info(f"{game_name} 追加 {len(new_dlc_dict[game_name])} 个新DLC到cream_api.ini")
        
        current_pos = end
    
    output_lines.extend(lines[current_pos:])
    
    with open(ini_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)

def append_new_dlc_to_txt(txt_path, new_dlc_dict):
    """将新DLC追加到DLC.txt对应游戏区块中，保持原始格式"""
    if not os.path.exists(txt_path):
        logging.error(f"找不到 {txt_path}")
        return
        
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    game_sections = content.split('#')
    output_sections = []
    
    for section in game_sections:
        if not section.strip():
            continue
            
        lines = section.strip().split('\n')
        game_name = lines[0].strip()
        dlc_lines = [line.strip() for line in lines[1:] if line.strip()]
        
        new_dlc = new_dlc_dict.get(game_name, {})
        if new_dlc:
            existing_dlc = {line.split('=')[0].strip(): line for line in dlc_lines}
            for dlc_id, dlc_name in sorted(new_dlc.items(), key=lambda x: int(x[0])):
                dlc_line = f"{dlc_id} = {dlc_name}"
                if dlc_id not in existing_dlc:
                    dlc_lines.append(dlc_line)
            
            dlc_lines.sort(key=lambda x: int(x.split('=')[0].strip()))
            section_content = f"# {game_name}\n" + '\n'.join(dlc_lines)
            output_sections.append(section_content)
            logging.info(f"{game_name} 追加 {len(new_dlc)} 个新DLC到DLC.txt")
        else:
            output_sections.append(f"#{section.strip()}")
    
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(output_sections))

def update_cream_api_ini_and_dlc_txt():
    """主流程：更新DLC配置文件"""
    ini_path = os.path.join(正版补丁目录, 'cream_api.ini')
    txt_path = os.path.join(局域网补丁目录, 'steam_settings', 'DLC.txt')
    
    ini_existing = parse_existing_dlc_from_ini(ini_path)
    txt_existing = parse_existing_dlc_from_txt(txt_path)
    
    new_dlc_for_ini = {}
    new_dlc_for_txt = {}
    
        # 获取游戏的所有DLC
    with ThreadPoolExecutor(max_workers=1) as executor:
        future_to_game = {
            executor.submit(get_steam_dlc_enhanced, app_id): game_name 
            for game_name, app_id in GAME_IDS.items()
        }
        
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
    
    append_new_dlc_to_ini(ini_path, new_dlc_for_ini)
    append_new_dlc_to_txt(txt_path, new_dlc_for_txt)
    logging.info("所有新DLC追加完成")

def create_zip_archive():
    """创建带日期的zip压缩包"""
    try:
        current_date = datetime.now().strftime("%Y.%m.%d")
        temp_dir = os.path.join(base_dir, "temp_backup")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        shutil.copytree(正版补丁目录, os.path.join(temp_dir, "正版DLC破解补丁"))
        shutil.copytree(局域网补丁目录, os.path.join(temp_dir, "局域网DLC破解补丁"))
        
        zip_filename = os.path.join(output_dir, f"【{current_date}】P社游戏DLC补丁.zip")
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)
        
        shutil.rmtree(temp_dir)
        logging.info(f"成功创建压缩包: {zip_filename}")
    except Exception as e:
        logging.error(f"创建压缩包失败: {str(e)}")

def main():
    try:
        logging.info("开始检查DLC更新...")
        logging.info("数据源优先级: Steam官方API + SteamCMD动态获取（解析listofdlc字段）")
        
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
        
        update_cream_api_ini_and_dlc_txt()
        
        ini_hash_after = None
        txt_hash_after = None
        if os.path.exists(ini_path):
            with open(ini_path, "rb") as f:
                ini_hash_after = hashlib.md5(f.read()).hexdigest()
        if os.path.exists(txt_path):
            with open(txt_path, "rb") as f:
                txt_hash_after = hashlib.md5(f.read()).hexdigest()
        
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
