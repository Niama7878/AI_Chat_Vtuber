# AI Chat VTuber 

一个多模态互动系统，通过集成实时聊天、语音识别、语音合成、音频播放、VTuber 控制以及动态文字显示的项目。

## 概述

本项目构建了一个端到端的实时互动平台，其主要功能包括：

- **实时聊天处理**  
  与 ChatGPT 实时对话、情绪检测以及自动抓取 YouTube 直播的聊天消息，实现动态互动。

- **语音识别与语音合成**  
  利用 Deepgram 将语音转换为文字，并通过 ElevenLabs 的 TTS 技术将文字转换为语音，搭配 ffplay 播放，带来自然流畅的语音交互体验。

- **VTuber 控制**  
  借助 VTube Studio 的 API，通过随机运动和热键触发等机制，使 VTuber 角色能够实时做出面部表情和动态动作。

- **动态文字显示**  
  采用 Pygame 与 OpenGL 实现打字机效果的实时文字展示，让屏幕上的对话内容生动有趣，还支持窗口拖动，随时调整观看位置。

- **聊天记录管理**  
  使用 SQLite 数据库存储和管理聊天记录，通过模糊匹配减少重复问题，并支持智能回答更新，形成有效的对话记忆。

## 环境配置

### Python 依赖

请在项目根目录下安装以下依赖（命令中包含具体版本要求）：

```bash
pip install websocket-client requests RapidFuzz==2.5.0 python-dotenv pydub pyaudio keyboard noise regex pygame opencv-python pyopengl freetype-py
```

### 系统依赖

- **FFmpeg 与 ffplay**  
  系统中需要安装 [FFmpeg](https://ffmpeg.org/)，并确保 `ffplay` 命令可用，以便支持音频播放功能。

- **Windows SDK（Windows Kits）**  
  在 Windows 平台上，需要使用 `noise` 包，请先安装 Windows SDK（即 Windows Kits），否则在构建时可能会遇到问题。

### 环境变量配置

在项目根找到 `.env` 文件，并填入以下 API 密钥：

```
OPENAI_API_KEY=
YOUTUBE_API_KEY=
DEEPGRAM_API_KEY=
ELEVENLABS_API_KEY=
```

## 运行方式

启动主程序非常简单，只需运行：

```bash
python main.py
```

系统会依次完成各个模块的初始化（4秒等待时间），开始抓取直播聊天、录音、生成回复、合成语音并通过 VTuber Studio 模块实时展示效果。按住空格键即可启动语音录制，释放后系统会自动处理并生成对应的互动反馈。

## 使用教程

[YouTube](https://youtu.be/3K6PtbxCHTs) [Bilibili](https://www.bilibili.com/video/BV1FRFNerEyU)