# AIDJ 🎧🙉
你的私人专属DJ，为此时此刻的你提供符合你心意的歌曲。
只需要准备：
- 支持OpenAI API的平台的BaseURL和对应的APIKey
- 一个音乐解析API，我使用的是本地搭建的API，见[这个仓库](https://github.com/Binaryify/NeteaseCloudMusicApi/tree/185031ddcefad34e294df6933418e44cc70ec31f?tab=readme-ov-file) 🔗（PS:下载zip然后偷偷用就行了，不要告诉别人哦🤫🙊）

# 目录
- [支持的功能](#支持的功能)
- [支持的平台](#支持的平台)
- [运行截图](#运行截图)
- [构建](#构建)
- [支持的命令](#支持的命令)
- [没本地曲库咋办](#没本地曲库咋办)

# 支持的功能
| 功能 | 详情 |
| :--: | :--: |
| 自然语言交互 | 说出你想听的歌曲类型，你的心情，甚至是一些意义不明的情绪化句子，本软件便能为你生成一个不错的歌单，源自于你的本地音乐库。歌曲质量你本身已经审核了😱😲😯😮🤯 |
| 随心搭配AI | 不局限于DeepSeekAI，只要支持OpenAI的API格式，稍加配置你就可以尽情畅聊🥰 |
| 私有曲库 | 我不提供歌曲下载方式而是使用你的本地歌曲，这不仅可以帮我避免版权问题也可以让你在你精心下载的音乐中畅游🌊🌊 |
| 歌曲元数据增量生成 | 基于你本地的曲库利用AI结合音乐解析API获取的歌曲信息，热评信息自动生成歌曲的元数据并且会在曲库增加的时候自动生成 🤖 |
| RichUI | 利用AI结合rich库vibe除了十分美丽的UI界面，同时DJ输出的信息也进行了Markdown解析，十分好看😍 |
| 多重播放器支持 | 支持启动mpv或者vlc来播放生成的歌单。什么？你不使用这两个，你使用smplayer?😱😱😱😱我们还支持DBUS控制，因此在Linux平台，只要你的软件实现了dbus，就能运行。什么？你是windows并且不使用vlc和mpv？那我没辙了，自己clone vibe去吧 |
| 等待的时候还能玩游戏 | 当你的metadata数据量太大时，AI的推荐耗时可能会高达40多秒，这是不可忍受的，因此我vibe出来了等待时的小游戏界面，支持随机观看老虎机，玩pingpong，玩贪吃蛇，玩永远都跳不过第一个obstacle的恐龙游戏 🎲🎮 |
| 超多命令支持 | 类bash的听歌体验，下文有一个section将讲述所有命令 |

# 支持的平台
- Linux
- MacOS(Maybe)
如果你希望在Windows系统也有这个体验，可以自己拿main.py和wait_game.py拿给AI vibe出来。

# 运行截图
歌单推荐
![歌单推荐](./screenshots/1.png)
启动时截图
![启动时截图](./screenshots/2.png)
和AIDJ对话
![和AIDJ对话](./screenshots/3.png)
## 新版本截图
等待中
![等待中](./screenshots/waiting.png)
完成
![完成](./screenshots/finished.png)

# 构建
## 前置要求
你需要有python，建议使用uv进行局部管理，接着建议拥有mpv/vlc中的一个。
在ArchLinux中安装步骤如下：
```bash
sudo pacman -S uv mpv vlc mpv-mpris # mpv-mpris是为了让mpv支持dbus控制
```

## 克隆仓库
```bash
git clone https://github.com/aaaa0ggMC/AIDJ.git
cd AIDJ
```

## 创建虚拟环境，安装依赖
```bash
uv venv -p 3.10 # 选择python3.10
uv pip install -r requirements.txt # 安装依赖
```

## 创建配置文件
在main.py目录下创建config.json，其中preferences不是必选项目，可以不写，程序后自动生成，其他为必选项目。
```json
{
    "music_folders": [
        "本地音乐库地址"
    ],
    "secrets": {
        "deepseek": "你的API密钥"
    },
    "ai_settings": {
        "base_url": "你选择的endpoint",
        "available_models": [
            "deepseek/deepseek-v3.2",
            "deepseek/deepseek-r1-turbo",
            "deepseek/deepseek-r1-0528",
            "moonshotai/kimi-k2-thinking",
            "minimax/minimax-m2",
            "zai-org/glm-4.7",
            "一堆模型，可以通过/model打开tui然后切换chat_model"
        ],
        "metadata_model": "deepseek/deepseek-v3.2",
        "chat_model": "deepseek/deepseek-r1-turbo"
    },
    "preferences": {
        "model": "deepseek-reasoner",
        "verbose": false,
        "auto_play": false,
        "saved_trigger": "mpv",
        "dbus_target": "vlc"
    }
}
```

## 运行程序
```bash
uv run main.py
```

# 支持的命令
| 命令 (别名) | 参数 | 详情 |
| :--- | :--- | :--- |
| **系统与设置** | | |
| `exit` `quit` `q` | - | 退出程序 |
| `help` `?` | - | 获取帮助信息 |
| `status` `check` `conf` | - | 查看当前系统配置、模型状态及歌单长度 |
| `verbose` | - | 切换详细日志输出模式（Debug用） |
| `model` | - | 进入模型选择界面，切换 AI 模型 (如 deepseek, gpt-4 等) |
| **AI 生成与控制** | | |
| `p` `prompt` `gen` | `<提示词>` | 发送提示词给 AI，返回 AI 的语音介绍以及生成的歌单 |
| `r` | `<数量>` | 从曲库中**完全随机**抽取指定数量的歌曲生成歌单 |
| `pr` | `<数量>` | **AI 筛选随机**：先随机抽取一批歌曲，再交给 AI 进行筛选、排序和删减，生成更有逻辑的歌单 |
| `refresh` | - | 刷新会话（保留歌单），用于更新 AI 上下文中的禁播列表，防止重复推荐 |
| `reset` | - | **重置会话**：清空 AI 的聊天历史和记忆，相当于开始一个新的 Session |
| `auto` | `mpv` `vlc` `send` `off` | 设置生成歌单后的自动行为。例如 `auto mpv` 会在 `p` 命令结束后自动调用 mpv 播放 |
| **播放器控制 (DBus/本地)** | | |
| `mpv` | - | 使用 MPV 播放器启动当前歌单 |
| `vlc` | - | 使用 VLC 播放器启动当前歌单 |
| `send` | - | 将当前歌单发送给已绑定的 DBus 播放器（如 Spotify, Rhythmbox 等） |
| `ls` `players` | - | 列出当前系统内活跃的 DBus 媒体播放器 |
| `init` | `<播放器名>` | 绑定特定的 DBus 播放器对象 (如 `init spotify`)，后续的控制命令将针对该播放器 |
| `play` | - | 发送 DBus 消息：开始播放 |
| `pause` | - | 发送 DBus 消息：暂停播放 |
| `toggle` | - | 发送 DBus 消息：切换 播放/暂停 |
| `stop` | - | 发送 DBus 消息：停止播放 |
| `next` `n` | - | 发送 DBus 消息：下一首 |
| `prev` `b` | - | 发送 DBus 消息：上一首 |
| **歌单管理 & 编辑** | | |
| `view` `list` `pl` `queue`| - | 查看当前播放列表详情 |
| `save` | `<文件名>` | 将当前歌单保存到 `./playlists/文件名.txt` |
| `load` | `(可选)<文件名>` | 加载歌单文件。如果不填文件名，则进入交互式选择界面 |
| `add` `insert` | `<歌名>` | 搜索本地曲库并将指定歌曲添加到当前歌单末尾 |
| `rm` `del` `remove` | `<序号>` | 删除指定序号的歌曲 (序号从1开始，如 `rm 1` 删除第一首) |
| `mv` `move` | `<原序号> <新序号>` | 移动歌曲位置。例如 `mv 5 1` 将第5首歌移动到第1位 |
| `swap` `sw` | `<序号1> <序号2>` | 交换两首歌的位置 |
| `top` | `<序号>` | 将指定序号的歌曲直接置顶 (移动到第1位) |
| `shuffle` `mix` | - | 打乱当前歌单顺序 |
| `reverse` `rev` | - | 反转当前歌单顺序 |
| `dedup` `unique` | - | **去重**：自动移除歌单中重复的歌曲 |
| `clear` `cls` | - | 清空当前歌单 |
| **工具与扩展** | | |
| `show` | `<歌名>` | 模糊搜索歌曲并显示其详细元数据 (Metadata) |
| `dlyrics` `lrc` | `(可选)[播放器名] [immersive]` | **桌面歌词**：同步显示当前播放歌曲的歌词。<br>• `dlyrics`：普通模式<br>• `dlyrics immersive`：**沉浸模式** (清空屏幕+居中大字)<br>• `dlyrics spotify`：指定监听 Spotify |


# 没本地曲库咋办
方法总比困难多，因此你能找到方法的！！！

# 关于这个项目
90%是AI写的，我因为甚至连python的语法都没学完，因此写了个框架main.old.py就全部拿给AI vibe出来了。

