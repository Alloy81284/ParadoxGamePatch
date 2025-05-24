# ParadoxGamePatch
P社游戏DLC破解补丁

这是一个用于Paradox Interactive游戏系列DLC解锁功能的工具。本项目仅供学习和研究使用。

## 功能特性

### 支持的游戏
- 城市：天际线 (Cities: Skylines)
- 城市：天际线2 (Cities: Skylines II)
- 十字军之王2 (Crusader Kings II)
- 十字军之王3 (Crusader Kings III)
- 欧陆风云4 (Europa Universalis IV)
- 钢铁雄心4 (Hearts of Iron IV)
- 英白拉多：罗马 (Imperator: Rome)
- 群星 (Stellaris)
- 维多利亚3 (Victoria 3)

### 主要功能
1. DLC解锁
   - 支持所有已发布的DLC内容
   - 自动更新DLC列表
   - 兼容Steam正版游戏

2. 联机模式
   - 正版联机：可与正版玩家一起游戏
   - 局域网联机：支持局域网内玩家联机

## 使用方法
1. 确保系统已安装Python 3.x
2. 编辑update_dlc.py中的文件路径
3. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   ```
   可能你要在虚拟环境中运行
   ```bash
   python update_dlc.py
   ```

### 安装步骤
1. 完成后会输出对应最新版本的压缩包
2. 解压文件
3. 根据游戏类型选择安装位置：
   - 对于《城市：天际线》《十字军之王2》《欧陆风云4》《钢铁雄心4》《群星》：
     - 将文件覆盖到游戏根目录
   - 对于《十字军之王3》《英白拉多：罗马》《维多利亚3》：
     - 将文件覆盖到游戏根目录的`binaries`文件夹

## 项目结构
```
.
├── README.md                 # 项目说明文档
├── requirements.txt          # Python依赖包列表
├── update_dlc.py             # DLC更新脚本
├── setup_cron.sh             # 自动更新设置脚本
├── setup_task.bat            # 自动更新设置脚本
├── logs/                     # 日志文件夹
│   └── dlc_updater.log       # 更新日志
├── 正版联机&DLC破解补丁/       # 正版补丁
│   ├── cream_api.ini         # DLC配置文件
│   └── 使用说明.txt           # 使用说明
└── 局域网联机&DLC破解补丁/     # 局域网补丁
    ├── steam_settings/DLC.txt # DLC配置文件
    └── 使用说明.txt           # 使用说明
```

## 注意事项
1. 本项目仅用于学习和研究目的
2. 使用本工具可能违反Steam服务条款

## 更新日志
- 2025.05.24: 版本发布

## 常见问题
1. Q: 为什么游戏无法启动？
   A: 请确保补丁文件已正确覆盖到对应目录，并检查游戏版本是否兼容。

2. Q: 如何更新DLC列表？
   A: 手动运行`update_dlc.py`脚本。

## 许可证
本项目采用MIT许可证。详见[LICENSE](LICENSE)文件。

## 免责声明
本项目仅供学习和研究使用，作者不对使用本工具造成的任何后果负责。使用本工具即表示您同意承担所有相关风险。 
