#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版DLC更新脚本
基于原有update_dlc.py，添加了获取隐藏DLC的功能

修改内容：
1. 添加已知隐藏DLC维护
2. 添加ID范围扫描功能
3. 改进DLC获取策略
"""

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

# 名称稳定模式：已有非泛化名称则保持不变，避免API名称来回波动
STABLE_NAME_MODE = True

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
    "Victoria 3": 529340,
    "Europa Universalis V": 3450310
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
    1206030: "Hearts of Iron IV: La Resistance Pre-Order Bonus",
    1785140: "Hearts of Iron IV: No Step Back - Katyusha (Pre-Order Bonus)",
    1880660: "Hearts of Iron IV: By Blood Alone (Pre-Order Bonus)",
    2280250: "Hearts of Iron IV: Arms Against Tyranny - Sakkijarven Polkka",
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
    472030: "Europa Universalis IV: Fredman Epistles",
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

def normalize_dlc_name(dlc_name):
    """规范化DLC名称：移除单引号以防止配置文件问题"""
    if isinstance(dlc_name, str):
        return dlc_name.replace("'", "")
    return dlc_name

def canonicalize_dlc_name(dlc_name):
    """用于比较的名称规范化（忽略大小写/多空格/破折号差异）"""
    if not dlc_name:
        return ""
    name = normalize_dlc_name(dlc_name)
    name = name.replace("\u2013", "-").replace("\u2014", "-")
    name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name.casefold()

def is_generic_dlc_name(dlc_id, dlc_name):
    """判断是否为泛化名称（避免用劣质名称覆盖已有名称）"""
    if not dlc_name:
        return True
    name = normalize_dlc_name(dlc_name)
    return name in {f"DLC {dlc_id}", f"Unknown DLC {dlc_id}"}

def should_update_dlc_name(dlc_id, old_name, new_name):
    if not new_name:
        return False
    if old_name is None:
        return True
    if is_generic_dlc_name(dlc_id, old_name) and not is_generic_dlc_name(dlc_id, new_name):
        return True
    if is_generic_dlc_name(dlc_id, new_name):
        return False
    if STABLE_NAME_MODE:
        return False
    return canonicalize_dlc_name(new_name) != canonicalize_dlc_name(old_name)

def compute_file_hash(file_path):
    if not os.path.exists(file_path):
        return None
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def compute_files_hash(file_paths):
    """计算多个文件的联合哈希"""
    hasher = hashlib.md5()
    for file_path in file_paths:
        if not os.path.exists(file_path):
            continue
        with open(file_path, "rb") as f:
            hasher.update(f.read())
    return hasher.hexdigest()

def load_last_pack_hash(state_path):
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("hash")
    except Exception:
        return None

def save_last_pack_hash(state_path, hash_value):
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"hash": hash_value}, f, ensure_ascii=False)
    except Exception:
        pass

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
                        dlc_name = normalize_dlc_name(dlc_details.get('name', f'Unknown DLC {dlc_appid}'))
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
                            dlc_name = normalize_dlc_name(dlc_data.get('name', f"DLC {dlc_id}"))
                            dlc_dict[dlc_id] = dlc_name
                            logging.info(f"获取DLC名称: {dlc_id} = {dlc_name}")
                        else:
                            # API返回失败，尝试使用后备名称映射
                            try:
                                fallback_name = FALLBACK_DLC_NAMES.get(int(dlc_id))
                                if fallback_name:
                                    fallback_name = normalize_dlc_name(fallback_name)
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
                                fallback_name = normalize_dlc_name(fallback_name)
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
                            fallback_name = normalize_dlc_name(fallback_name)
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

def parse_existing_dlc_names_from_ini(ini_path):
    """解析cream_api.ini中每个游戏的DLC名称映射"""
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
            dlc_id, dlc_name = [s.strip() for s in line_strip.split('=', 1)]
            game_dlc.setdefault(current_game, {})[dlc_id] = normalize_dlc_name(dlc_name)
    return game_dlc

def parse_existing_dlc_names_from_txt(txt_path):
    """解析DLC.txt中每个游戏的DLC名称映射"""
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
            dlc_id, dlc_name = [s.strip() for s in line_strip.split('=', 1)]
            game_dlc.setdefault(current_game, {})[dlc_id] = normalize_dlc_name(dlc_name)
    return game_dlc

def append_new_dlc_to_ini(ini_path, new_dlc_dict, latest_dlc_by_game=None):
    """将新DLC追加到cream_api.ini对应区块末尾，避免重复和异常空格"""
    if not os.path.exists(ini_path):
        logging.error(f"找不到 {ini_path}")
        return
    with open(ini_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 解析现有DLC（用于去重与名称更新）
    existing_dlc_map = {}  # {game_name: {dlc_id: dlc_name}}
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
            dlc_id, dlc_name = [s.strip() for s in line_strip.split('=', 1)]
            if current_game not in existing_dlc_map:
                existing_dlc_map[current_game] = {}
            existing_dlc_map[current_game][dlc_id] = normalize_dlc_name(dlc_name)
    
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
        # 复制区块并移除DLC块内空行
        segment = lines[current_pos:end]
        if game_name in existing_dlc_map:
            segment_lines = []
            in_dlc = False
            for line in segment:
                line_strip = line.strip()
                if line_strip == '[dlc]':
                    in_dlc = True
                    segment_lines.append(line)
                    continue
                if line_strip.startswith('[') and line_strip != '[dlc]':
                    in_dlc = False
                if in_dlc and not line_strip:
                    continue
                segment_lines.append(line)
            segment = segment_lines
        output_lines.extend(segment)
        
        if game_name in new_dlc_dict and new_dlc_dict[game_name]:
            # 过滤掉已存在的DLC，避免重复
            existing_ids = set(existing_dlc_map.get(game_name, {}).keys())
            new_dlcs_to_add = {dlc_id: dlc_name for dlc_id, dlc_name in new_dlc_dict[game_name].items()
                               if dlc_id not in existing_ids}
            
            if new_dlcs_to_add:
                # 检查是否需要添加空行分隔符
                if output_lines and output_lines[-1].strip():
                    output_lines.append('\n')
                
                for dlc_id, dlc_name in sorted(new_dlcs_to_add.items(), key=lambda x: int(x[0])):
                    normalized_name = normalize_dlc_name(dlc_name)
                    output_lines.append(f"{dlc_id} = {normalized_name}\n")
                
                logging.info(f"{game_name} 追加 {len(new_dlcs_to_add)} 个新DLC到cream_api.ini")
            else:
                logging.info(f"{game_name} 没有新DLC需要添加（已全部存在）")

        # 如果已有DLC但名称不同，则替换名称
        if game_name in existing_dlc_map:
            updated_lines = []
            in_dlc = False
            for line in output_lines:
                line_strip = line.strip()
                if line_strip.startswith(';') and not line_strip.startswith(';lowviolence'):
                    in_dlc = False
                if line_strip == '[dlc]':
                    in_dlc = True
                if in_dlc and '=' in line_strip:
                    dlc_id, dlc_name = [s.strip() for s in line_strip.split('=', 1)]
                    latest_name = (latest_dlc_by_game or {}).get(game_name, {}).get(dlc_id)
                    if latest_name and should_update_dlc_name(dlc_id, dlc_name, latest_name):
                        normalized_name = normalize_dlc_name(latest_name)
                        updated_lines.append(f"{dlc_id} = {normalized_name}\n")
                        continue
                updated_lines.append(line)
            output_lines = updated_lines
        
        current_pos = end
    
    output_lines.extend(lines[current_pos:])
    
    with open(ini_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)

def append_new_dlc_to_txt(txt_path, new_dlc_dict, latest_dlc_by_game=None):
    """将新DLC追加到DLC.txt对应游戏区块中，避免重复和异常空格"""
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

        # 构建现有DLC的映射（用于去重与名称更新）
        existing_dlc_ids = set()
        existing_dlc_map = {}
        for line in dlc_lines:
            if '=' in line:
                dlc_id = line.split('=', 1)[0].strip()
                existing_dlc_ids.add(dlc_id)
                existing_dlc_map[dlc_id] = line

        new_dlc = new_dlc_dict.get(game_name, {})

        # 只添加不存在的DLC
        if new_dlc:
            for dlc_id, dlc_name in sorted(new_dlc.items(), key=lambda x: int(x[0])):
                if dlc_id not in existing_dlc_ids:
                    dlc_line = f"{dlc_id} = {normalize_dlc_name(dlc_name)}"
                    dlc_lines.append(dlc_line)
                else:
                    # 已存在则更新名称
                    old_line = existing_dlc_map.get(dlc_id, "")
                    old_name = old_line.split('=', 1)[1].strip() if '=' in old_line else ""
                    if should_update_dlc_name(dlc_id, old_name, dlc_name):
                        existing_dlc_map[dlc_id] = f"{dlc_id} = {normalize_dlc_name(dlc_name)}"

        # 用最新名称替换已有条目（无新增也会执行）
        if latest_dlc_by_game and game_name in latest_dlc_by_game:
            for dlc_id, dlc_name in latest_dlc_by_game[game_name].items():
                if dlc_id in existing_dlc_ids:
                    old_line = existing_dlc_map.get(dlc_id, "")
                    old_name = old_line.split('=', 1)[1].strip() if '=' in old_line else ""
                    if should_update_dlc_name(dlc_id, old_name, dlc_name):
                        existing_dlc_map[dlc_id] = f"{dlc_id} = {normalize_dlc_name(dlc_name)}"

        # 按DLC ID排序，规范化格式
        dlc_lines_dict = {}
        for line in dlc_lines:
            if '=' in line:
                parts = line.split('=', 1)
                dlc_id = parts[0].strip()
                dlc_name = normalize_dlc_name(parts[1].strip())
                dlc_lines_dict[int(dlc_id)] = f"{dlc_id} = {dlc_name}"
        for dlc_id, line in existing_dlc_map.items():
            if dlc_id.isdigit():
                dlc_lines_dict[int(dlc_id)] = line

        # 按ID排序后重新构建
        sorted_dlc_lines = [dlc_lines_dict[dlc_id] for dlc_id in sorted(dlc_lines_dict.keys())]
        section_content = f"# {game_name}\n" + '\n'.join(sorted_dlc_lines)
        output_sections.append(section_content)

        if new_dlc:
            newly_added = sum(1 for dlc_id in new_dlc.keys() if dlc_id not in existing_dlc_ids)
            if newly_added > 0:
                logging.info(f"{game_name} 追加 {newly_added} 个新DLC到DLC.txt")
            else:
                logging.info(f"{game_name} 没有新DLC需要添加（已全部存在）")
    
    # 用两个换行符分隔游戏区块
    output_content = '\n\n'.join(output_sections)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(output_content)

def clean_duplicate_dlc_in_ini(ini_path):
    """清理cream_api.ini中重复的DLC条目，并规范化空格"""
    if not os.path.exists(ini_path):
        logging.warning(f"找不到 {ini_path}，跳过清理")
        return
    
    with open(ini_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    output_lines = []
    current_game = None
    seen_dlc_ids = {}  # {game_name: {dlc_id, ...}}
    in_dlc_block = False
    
    for line in lines:
        line_strip = line.strip()
        
        # 识别游戏区块
        if line_strip.startswith(';') and not line_strip.startswith(';lowviolence'):
            if output_lines and output_lines[-1].strip():
                output_lines.append('\n')
            current_game = line_strip[1:].strip()
            if current_game not in seen_dlc_ids:
                seen_dlc_ids[current_game] = set()
            in_dlc_block = False
            output_lines.append(line)
        # 识别DLC区块开始
        elif line_strip == '[dlc]':
            in_dlc_block = True
            output_lines.append(line)
        # 识别其他区块（结束DLC块）
        elif line_strip.startswith('[') and line_strip != '[dlc]':
            in_dlc_block = False
            output_lines.append(line)
        # 处理DLC行
        elif in_dlc_block and '=' in line_strip and current_game:
            dlc_id = line_strip.split('=', 1)[0].strip()
            dlc_name = normalize_dlc_name(line_strip.split('=', 1)[1].strip())
            
            # 检查是否重复
            if dlc_id not in seen_dlc_ids[current_game]:
                # 规范化空格：id = name
                output_lines.append(f"{dlc_id} = {dlc_name}\n")
                seen_dlc_ids[current_game].add(dlc_id)
            else:
                logging.debug(f"移除重复DLC: {current_game} - {dlc_id}")
        else:
            if in_dlc_block and not line_strip:
                continue
            output_lines.append(line)
    
    with open(ini_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)
    
    logging.info("成功清理cream_api.ini中的重复DLC条目")

def clean_duplicate_dlc_in_txt(txt_path):
    """清理DLC.txt中重复的DLC条目，并规范化空格"""
    if not os.path.exists(txt_path):
        logging.warning(f"找不到 {txt_path}，跳过清理")
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
        dlc_lines = lines[1:]
        
        # 去重并规范化格式
        seen_dlc_ids = set()
        cleaned_dlc_lines = []
        
        for line in dlc_lines:
            line_strip = line.strip()
            if not line_strip:
                continue
            
            if '=' in line_strip:
                dlc_id = line_strip.split('=', 1)[0].strip()
                dlc_name = normalize_dlc_name(line_strip.split('=', 1)[1].strip())
                
                if dlc_id not in seen_dlc_ids:
                    # 规范化空格：id = name
                    cleaned_dlc_lines.append(f"{dlc_id} = {dlc_name}")
                    seen_dlc_ids.add(dlc_id)
        
        # 按DLC ID排序
        cleaned_dlc_lines_dict = {}
        for line in cleaned_dlc_lines:
            if '=' in line:
                dlc_id = int(line.split('=')[0].strip())
                cleaned_dlc_lines_dict[dlc_id] = line
        
        sorted_lines = [cleaned_dlc_lines_dict[dlc_id] for dlc_id in sorted(cleaned_dlc_lines_dict.keys())]
        section_content = f"# {game_name}\n" + '\n'.join(sorted_lines)
        output_sections.append(section_content)
    
    output_content = '\n\n'.join(output_sections)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(output_content)
    
    logging.info("成功清理DLC.txt中的重复DLC条目")

def update_cream_api_ini_and_dlc_txt():
    """主流程：更新DLC配置文件，返回新增条目数量 (ini_count, txt_count)"""
    ini_path = os.path.join(正版补丁目录, 'cream_api.ini')
    txt_path = os.path.join(局域网补丁目录, 'steam_settings', 'DLC.txt')
    
    ini_existing = parse_existing_dlc_from_ini(ini_path)
    txt_existing = parse_existing_dlc_from_txt(txt_path)
    ini_existing_names = parse_existing_dlc_names_from_ini(ini_path)
    txt_existing_names = parse_existing_dlc_names_from_txt(txt_path)
    
    new_dlc_for_ini = {}
    new_dlc_for_txt = {}
    ini_name_changed = 0
    txt_name_changed = 0
    ini_name_changes = []
    txt_name_changes = []
    latest_dlc_by_game = {}
    
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
                
                latest_dlc_by_game[game_name] = latest_dlc

                # ini处理
                ini_game_dlc = ini_existing.get(game_name, set())
                ini_new = {dlc_id: dlc_name for dlc_id, dlc_name in latest_dlc.items() if dlc_id not in ini_game_dlc}
                if ini_new:
                    new_dlc_for_ini[game_name] = ini_new
                for dlc_id, dlc_name in latest_dlc.items():
                    old_name = ini_existing_names.get(game_name, {}).get(dlc_id)
                    if old_name and should_update_dlc_name(dlc_id, old_name, dlc_name):
                        ini_name_changed += 1
                        ini_name_changes.append((game_name, dlc_id, old_name, dlc_name))
                
                # txt处理
                txt_game_dlc = txt_existing.get(game_name, set())
                txt_new = {dlc_id: dlc_name for dlc_id, dlc_name in latest_dlc.items() if dlc_id not in txt_game_dlc}
                if txt_new:
                    new_dlc_for_txt[game_name] = txt_new
                for dlc_id, dlc_name in latest_dlc.items():
                    old_name = txt_existing_names.get(game_name, {}).get(dlc_id)
                    if old_name and should_update_dlc_name(dlc_id, old_name, dlc_name):
                        txt_name_changed += 1
                        txt_name_changes.append((game_name, dlc_id, old_name, dlc_name))
                    
            except Exception as e:
                logging.error(f"处理游戏 {game_name} 的DLC时发生错误: {str(e)}")
    
    append_new_dlc_to_ini(ini_path, new_dlc_for_ini, latest_dlc_by_game)
    append_new_dlc_to_txt(txt_path, new_dlc_for_txt, latest_dlc_by_game)
    ini_added = sum(len(v) for v in new_dlc_for_ini.values())
    txt_added = sum(len(v) for v in new_dlc_for_txt.values())
    logging.info(f"所有新DLC追加完成：ini新增 {ini_added} 条，txt新增 {txt_added} 条")
    if ini_name_changed or txt_name_changed:
        logging.info(f"检测到名称变化：ini {ini_name_changed} 条，txt {txt_name_changed} 条")
        try:
            changes_path = os.path.join(log_dir, "name_changes.txt")
            with open(changes_path, "w", encoding="utf-8") as f:
                f.write(f"time = {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                for game_name, dlc_id, old_name, new_name in ini_name_changes:
                    f.write(f"INI | {game_name} | {dlc_id} | {old_name} => {new_name}\n")
                for game_name, dlc_id, old_name, new_name in txt_name_changes:
                    f.write(f"TXT | {game_name} | {dlc_id} | {old_name} => {new_name}\n")
            logging.info(f"名称变化明细已写入: {changes_path}")
        except Exception as e:
            logging.warning(f"写入名称变化明细失败: {e}")
    return ini_added, txt_added, ini_name_changed, txt_name_changed

def create_zip_archive():
    """创建带日期的zip压缩包"""
    try:
        current_date = datetime.now().strftime("%Y.%m.%d")
        current_time = datetime.now().strftime("%H%M%S")
        temp_dir = os.path.join(base_dir, "temp_backup")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        src_ini_path = os.path.join(正版补丁目录, 'cream_api.ini')
        src_txt_path = os.path.join(局域网补丁目录, 'steam_settings', 'DLC.txt')

        shutil.copytree(正版补丁目录, os.path.join(temp_dir, "正版DLC破解补丁"))
        shutil.copytree(局域网补丁目录, os.path.join(temp_dir, "局域网DLC破解补丁"))

        temp_ini_path = os.path.join(temp_dir, "正版DLC破解补丁", 'cream_api.ini')
        temp_txt_path = os.path.join(temp_dir, "局域网DLC破解补丁", 'steam_settings', 'DLC.txt')
        
        # 写入构建信息，便于确认打包来源
        ini_mtime = datetime.fromtimestamp(os.path.getmtime(src_ini_path)).strftime("%Y-%m-%d %H:%M:%S") if os.path.exists(src_ini_path) else "N/A"
        txt_mtime = datetime.fromtimestamp(os.path.getmtime(src_txt_path)).strftime("%Y-%m-%d %H:%M:%S") if os.path.exists(src_txt_path) else "N/A"
        src_ini_hash = compute_file_hash(src_ini_path)
        src_txt_hash = compute_file_hash(src_txt_path)
        temp_ini_hash = compute_file_hash(temp_ini_path)
        temp_txt_hash = compute_file_hash(temp_txt_path)
        content_hash = compute_files_hash([src_ini_path, src_txt_path])
        build_info_path = os.path.join(temp_dir, "build_info.txt")
        with open(build_info_path, "w", encoding="utf-8") as f:
            f.write(f"build_time = {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"ini_mtime = {ini_mtime}\n")
            f.write(f"txt_mtime = {txt_mtime}\n")
            f.write(f"content_hash = {content_hash}\n")
            f.write(f"src_ini_hash = {src_ini_hash}\n")
            f.write(f"src_txt_hash = {src_txt_hash}\n")
            f.write(f"temp_ini_hash = {temp_ini_hash}\n")
            f.write(f"temp_txt_hash = {temp_txt_hash}\n")

        zip_filename = os.path.join(output_dir, f"【{current_date}-{current_time}】P社游戏DLC补丁.zip")
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)

        # 校验压缩包内文件与源文件一致
        zip_ini_path = "正版DLC破解补丁/cream_api.ini"
        zip_txt_path = "局域网DLC破解补丁/steam_settings/DLC.txt"
        zip_ini_hash = None
        zip_txt_hash = None
        with zipfile.ZipFile(zip_filename, 'r') as zipf:
            if zip_ini_path in zipf.namelist():
                zip_ini_hash = hashlib.md5(zipf.read(zip_ini_path)).hexdigest()
            if zip_txt_path in zipf.namelist():
                zip_txt_hash = hashlib.md5(zipf.read(zip_txt_path)).hexdigest()

        if (src_ini_hash and zip_ini_hash and src_ini_hash != zip_ini_hash) or (src_txt_hash and zip_txt_hash and src_txt_hash != zip_txt_hash):
            logging.error("压缩包内文件与源文件不一致，已删除压缩包")
            os.remove(zip_filename)
            return
        
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
        
        # 第一步：清理现有的重复DLC条目
        logging.info("第一步：清理现有配置文件中的重复条目和异常空格...")
        clean_duplicate_dlc_in_ini(ini_path)
        clean_duplicate_dlc_in_txt(txt_path)
        
        # 第二步：更新并追加新DLC
        logging.info("第二步：检查并追加新DLC...")
        ini_added, txt_added, ini_name_changed, txt_name_changed = update_cream_api_ini_and_dlc_txt()
        has_changes = (ini_added + txt_added + ini_name_changed + txt_name_changed) > 0

        # 第三步：基于文件内容哈希判断是否需要打包
        state_path = os.path.join(log_dir, "last_pack_hash.json")
        current_hash = compute_files_hash([ini_path, txt_path])
        last_hash = load_last_pack_hash(state_path)
        hash_changed = (current_hash != last_hash)
        has_changes = has_changes or hash_changed
        
        if has_changes:
            logging.info("检测到DLC更新，开始创建新的压缩包...")
            create_zip_archive()
            logging.info("压缩包创建完成")
            save_last_pack_hash(state_path, current_hash)
        else:
            logging.info("未检测到DLC更新，跳过创建压缩包")
            
        logging.info("所有任务完成")
    except Exception as e:
        logging.error(f"执行过程中发生错误: {str(e)}")

if __name__ == "__main__":
    main()
