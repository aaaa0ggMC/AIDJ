# AIDJ 🎧🤖✨

你的私人 AI 专属 DJ！🙅‍♂️拒绝千篇一律的算法推荐，它拥有硅基大脑，听得懂你的碎碎念，只为你播放本地珍藏的高品质音乐。

你需要准备：
1.  **DeepSeek API Key** (便宜又大碗，R1/V3 随便切) 🧠
2.  **本地搭建音乐 API** (用于补全歌词、流派、情绪等元数据)
    * 见 [这个网址](https://github.com/Binaryify/NeteaseCloudMusicApi/tree/185031ddcefad34e294df6933418e44cc70ec31f?tab=readme-ov-file) 🔗
    * 自己 `下载zip` 下来 `node app.js` 跑起来就行，**嘘！自己用，不要告诉别人哦** 🤫

---

# 目录 📑

- [支持的功能](#支持的功能)
- [前置要求](#前置要求)
- [运行截图](#运行截图)
- [构建与运行](#构建)
- [那我没有本地歌曲咋办](#那我没有本地歌曲咋办)
- [后记](#后记)

---

# 支持的功能 🚀🔥

* 🗣️ **自然语言交互**：不再是死板的搜索框！你可以说 *"来点适合半夜三更偷偷eemo的歌，像 'it's 6pm...' 那种感觉"*，AI 瞬间懂你。
* 🧠 **DeepSeek 强力驱动**：支持 `deepseek-chat` (V3) 和 `deepseek-reasoner` (R1) 模型切换，不仅推荐歌，还能陪你聊聊选曲逻辑。
* 📂 **本地私有曲库**：扫描你硬盘里的 `.mp3`, `.flac`，保护隐私，拒绝版权变灰，只有你拥有的歌才会被播放。
* 📊 **元数据自动补全**：新歌入库？系统会自动调用 NCM API 获取歌词，丢给 AI 分析出 **流派 (Genre)**、**情绪 (Emotion)** 和 **语言** 并缓存。
* 🎨 **工业级 TUI 界面**：基于 `Rich` 库打造，漂亮的表格、进度条、Emoji，看着就赏心悦目。
* 🔍 **Rapidfuzz 模糊匹配**：AI 记不清歌名全称？拼写错误？没关系，强力模糊匹配算法能精准找到你想听的那首。
* 🕹️ **播放器控制**：支持 `mpv` 和 `vlc`，通过 DBus 协议无缝控制，后台静默播放，不抢终端焦点。
* ⚡ **持久化 Trigger**：可以设置自动触发器，生成歌单后自动推送到播放器，解放双手。

---

# 前置要求 🛠️

除了 Python 环境，你还需要在系统里安装播放器（二选一）：

* **MPV** (推荐 🌟): `sudo pacman -S mpv` / `brew install mpv`
* **VLC**: `sudo pacman -S vlc` / `brew install --cask vlc`

---

# 运行截图
![歌单推荐](./screenshots/1.png)
![启动时截图](./screenshots/2.png)
![和AIDJ对话](./screenshots/3.png)


# 构建 🏗️

## 1. 克隆仓库
```bash
git clone https://github.com/aaaa0ggMC/AIDJ.git
cd AIDJ
```

## 2. 安装依赖
推荐使用 `uv` (因为它快得像火箭 🚀)，也可以用普通的 `pip`。

```bash
# 创建环境 (可选)
uv venv -p 3.10
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
uv pip install -r requirements.txt
```
## 3. 运行即可
```bash
uv run main.py
```

---

# 那我没有本地歌曲咋办 🤷‍♂️

有个软件叫什么什么 **dump** (XXXDump)，或者各种 **Music Downloader**... 懂的都懂。🤐

你可以去 GitHub 搜索一下，把网易云/Spotify 的歌单“搬运”到本地。构建自己的无损库才是王道！🏴‍☠️

---

# 后记 📝🤯

**Q: 你是怎么只了解 Python 一点语法就能一天做出这个玩意儿的啊？**

**A:** 哈哈哈哈！😱 因为我只写了第一个版本（也就是个支持 metadata dump 的简陋脚本），剩下的全部——没错，**全部**——都交给 AI 了！

* 架构设计？Gemini 3 Pro 搞定的。🧠
* 界面美化 (`Rich`)？Gemini 3 Pro 写的。🎨
* 模糊匹配逻辑？Gemini 3 Pro 建议的。💡
* 连你现在看到的这个 **README.md**，都是我写了个大纲，让 AI 帮我填充润色的！
