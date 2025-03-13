import os
import json
import websocket
import base64
import threading
import time
from dotenv import load_dotenv
from status import update_status, processing
import queue
from pydub import AudioSegment
from play import AudioPlayer
import tempfile
import word 

# 加载环境变量
load_dotenv()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# 设置语音ID和模型ID
VOICE_ID = "hkfHEbBvdQFNX4uWHqRF" 
MODEL_ID = "eleven_flash_v2_5"

request_payload = {
    "text": "",
    "voice_settings": {
        "stability": 0.5, # 降低稳定性，加快生成速度
        "similarity_boost": 0.8, # 提高相似度，减少计算量
        "use_speaker_boost": True # 启用加速
        },
    "generation_config": {
        "chunk_length_schedule": [120, 160, 250, 290], # 建议使用官方配置
        },
    "xi_api_key": ELEVENLABS_API_KEY,
    "flush": True  # 立即输出语音，减少等待时间
}

ws_global = None  # 全局 WebSocket 连接
lock = threading.Lock()  # 线程锁

buffer = [] # 实时缓存的字体
buffer_time = 0 # 开始缓存的时间
is_waiting = False # 等待状态
is_pending = False # 预处理事件
backup_time = None # 播放开始时间备份
audio_queue = queue.Queue()  # 音频数据队列
start_time = None  # 记录播放开始时间
estimated_duration = 0  # 记录音频总时长
player = AudioPlayer() # 初始化播放器
display_word = "" # 用于前端显示的字体

def audio_player():
    # 音频播放线程，持续从队列获取音频片段，合并并播放
    global start_time, estimated_duration

    while True:
        try:
            chunks = []
            start_time_for_chunk = time.time()

            while True:
                try:
                    chunk = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    chunk = None

                if chunk:
                    chunks.append(chunk)
                    start_time_for_chunk = time.time()

                if time.time() - start_time_for_chunk > 1:
                    break  

            if chunks:
                merged_audio = b"".join(chunks)  # 合并音频片段
                fd, temp_audio_path = tempfile.mkstemp(suffix=".mp3") # 使用 tempfile 生成唯一临时文件，避免冲突
                os.close(fd)  # 关闭文件描述符，防止文件锁定

                try:
                    with open(temp_audio_path, "wb") as temp_mp3:
                        temp_mp3.write(merged_audio)

                    time.sleep(0.1)  # 让操作系统完成文件刷新（Windows 可能需要）

                    audio = AudioSegment.from_file(temp_audio_path, format="mp3") # 解析 MP3 获取时长
                    estimated_duration = len(audio) / 1000
                    start_time = time.time()
                    
                    with open(temp_audio_path, "rb") as temp_mp3: # 读取 MP3 文件的二进制数据
                        audio_bytes = temp_mp3.read()

                    player.add_audio(audio_bytes)  # 传入 bytes 数据
                    word.add_text(display_word) # 打印信息到前端
                    update_status(display_word) # 终端打印信息

                finally:
                    time.sleep(0.1)  # 给 ffplay 释放文件的时间
                    os.remove(temp_audio_path)
                    chunks.clear()  # 清空已合并的音频片段
                    merged_audio = b""  # 清空临时音频片段

        except Exception as e:
            update_status(f"音频播放线程异常：{e}")

def check_playback_progress():
    # 后台线程：监测播放进度，70% 时清空队列并等待新数据
    global start_time, estimated_duration, is_waiting, is_pending, backup_time

    while True:
        if start_time and estimated_duration > 0:
            is_waiting = False # 解除等待状态
            elapsed_time = time.time() - start_time
            progress = elapsed_time / estimated_duration if estimated_duration > 0 else 0

            if progress > 0.7:
                audio_queue.queue.clear() # 清空队列
                backup_time = time.time() # 备份播放时间
                start_time = None  # 重置播放时间
                estimated_duration = 0  # 重置总时长
                is_pending = True # 启动预处理事件

        elif is_pending and time.time() - backup_time > 0.6: # TTS 事件结束时触发 
            is_pending = False
            backup_time = None
            processing(False) # 取消处理状态

        time.sleep(0.1) 

def on_message(ws, message):
    # 接收收到的音频数据
    try:
        data = json.loads(message)
        if "audio" in data and isinstance(data["audio"], str):
            chunk = base64.b64decode(data["audio"])
            audio_queue.put(chunk)  # 添加音频到播放队列
    
    except Exception as e:
        update_status(f"Elevenlabs WebSocket 处理消息时出错：{e}")

def on_open(ws):
    # 连接成功打开时的事件
    pass

def on_close(ws, close_status_code, close_msg):
    # 连接关闭时的事件
    #update_status(f"Elevenlabs WebSocket 连接关闭：{close_status_code}, {close_msg}")
    connect_ws()  # 重新连接 WebSocket

def on_error(ws, error):
    # 连接发生错误时打印报错
    #update_status(f"Elevenlabs WebSocket 错误：{error}")
    pass

def keep_alive():
    # 发送心跳包以保持 WebSocket 连接 
    while True:
        try:
            time.sleep(15)
            request_payload["text"] = " "
            ws_global.send(json.dumps(request_payload))
        except Exception as e:
            pass

def connect_ws():
    # 建立 WebSocket 连接 
    global ws_global

    uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input?model_id={MODEL_ID}"
    
    try:
        ws_global = websocket.WebSocketApp(
            uri,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error
        )
        threading.Thread(target=ws_global.run_forever, daemon=True).start()

    except Exception as e:
        update_status(f"Elevenlabs WebSocket 连接失败：{e}")

def process_tts(): 
    # 处理 TTS 发送内容和更新状态
    global buffer, is_waiting, is_pending

    chunk = buffer[:40] if len(buffer) >= 40 else buffer[:]  # 取前 40 个，或者所有剩余文本
    text_to_speech_ws(''.join(chunk))
    buffer = buffer[len(chunk):]  # 删除已发送部分
    is_waiting = True # 开启等待状态
    is_pending = False # 关闭预处理

def add_buffer(text):
    # 把文本加入到 buffer 列表
    global buffer, buffer_time
    buffer.append(text)
    buffer_time = time.time()

def flush_buffer(): 
    # 实时检查 buffer，发送缓存的文本
    while True:
        # 如果超出缓存限定时间没有任何变化
        if len(buffer) > 0 and time.time() - buffer_time > 0.6 and not is_pending and not is_waiting and estimated_duration == 0 and backup_time == None: 
            process_tts() 
        elif len(buffer) >= 40 and not is_waiting and estimated_duration == 0: # 40 字且不是在等待状态 
            process_tts() 
        elif is_pending and len(buffer) > 0 and time.time() - backup_time > 0.4: # pending 状态时限内没触发 process_tts()
            process_tts() 

        time.sleep(0.1) 

def text_to_speech_ws(segment):
    # 实时 WebSocket TTS 
    global request_payload, display_word

    with lock:
        try:
            request_payload["text"] = segment
            ws_global.send(json.dumps(request_payload))
            display_word = segment
            ws_global.send(json.dumps({"text": ""})) # 关闭当前 Websocket

        except Exception as e:
            update_status(f"Elevenlabs WebSocket 发送消息失败：{e}")

connect_ws()
# 确保每个线程只启动一次 
threading.Thread(target=flush_buffer, daemon=True).start()
threading.Thread(target=audio_player, daemon=True).start()
threading.Thread(target=check_playback_progress, daemon=True).start()
threading.Thread(target=keep_alive, daemon=True).start()