import websocket
import json
import pyaudio
import threading
import os
import time
from status import update_status, processing
from dotenv import load_dotenv
import keyboard
import memory
from play import AudioPlayer

# 加载环境变量
load_dotenv()
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_URL = "wss://api.deepgram.com/v1/listen?model=base&language=zh&encoding=linear16&sample_rate=16000"
HEADER = [
    "Authorization: Token " + DEEPGRAM_API_KEY
]

ws_global = None  # 全局 WebSocket 连接
lock = threading.Lock()  # 线程锁

RATE = 16000
CHUNK = 320  # 20ms（16000Hz 时）
CHANNELS = 1
p = pyaudio.PyAudio() # 初始化 pyaudio
stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
is_processing = False # 处理状态
player = AudioPlayer()

def on_close(ws, close_status_code, close_msg):
    # 连接关闭时触发
    #update_status(f"Deepgram WebSocket 连接关闭：{close_status_code}, {close_msg}")
    connect_ws()  # 重新连接 WebSocket

def on_error(ws, error):
    # 报错时打印错误信息
    #update_status(f"Deepgram WebSocket 错误：{error}")
    pass

def keep_alive():
    # 每隔一段时间发送 KeepAlive 以保持 WebSocket 连接 
    while True:
        try:
            time.sleep(10)
            ws_global.send(json.dumps({"type": "KeepAlive"}))
        except Exception as e:
            pass

def on_message(ws, message):
    # 处理收到的转录文本
    global is_processing
    response = json.loads(message)
    if 'channel' in response and 'alternatives' in response['channel'] and response['channel']['alternatives']:
        transcript = response['channel']['alternatives'][0].get('transcript', '')
        if transcript: 
            memory.save_chat_record("Niama78", "tts_message", transcript)

    is_processing = False
  
def on_open(ws):
    # 连接打开时触发
    try:       
        silence_duration = 2  # 发送 2 秒的静音
        silent_audio = b"\x00" * (RATE * silence_duration * 2)  # 16-bit PCM，每个样本2字节
        ws_global.send(silent_audio, opcode=websocket.ABNF.OPCODE_BINARY)

    except Exception as e:
        update_status(f"Deepgram WebSocket 初始化音频发送失败：{e}")

def speech_recorder():
    # 录制音频，进行 STT
    global is_processing

    while True:
        buffer = b""  # 录音数据缓存
        recording = False  # 录音状态

        while not keyboard.is_pressed('space'): # 等待按键按下
            time.sleep(0.01)  
            
        if not is_processing and not processing() and not player.is_playing: # 按下按键开始录音
            update_status("开始录音...")
            recording = True
            buffer = b""  # 清空 buffer

            while keyboard.is_pressed('space'):  # 持续录音直到松开
                try:
                    if processing() or player.is_playing: # 如果过程中播放或者处理状态变了，立即终止
                        update_status("检测到播放或处理中，取消当前录音！")
                        buffer = b""  # 丢弃数据
                        recording = False
                        break

                    audio_data = stream.read(CHUNK, exception_on_overflow=False)
                    buffer += audio_data
                    time.sleep(0.01)  

                except Exception as e:
                    update_status(f"音频处理错误：{e}")
                    break

        if recording:
            update_status("松开按键，发送录音数据...")
            if buffer:  # 只有非空数据才发送
                ws_global.send(buffer, opcode=websocket.ABNF.OPCODE_BINARY)
                ws_global.send(json.dumps({"type": "CloseStream"}))  # 关闭流
            is_processing = True  # 标记正在处理，防止短时间内重复触发

        time.sleep(0.1)  

def connect_ws():
    # 建立 WebSocket 连接 
    global ws_global
    
    try:
        ws_global = websocket.WebSocketApp(
            url=DEEPGRAM_URL,
            header=HEADER,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error
        )
        threading.Thread(target=ws_global.run_forever, daemon=True).start()

    except Exception as e:
        update_status(f"Deepgram WebSocket 连接失败：{e}")

connect_ws()
threading.Thread(target=keep_alive, daemon=True).start()
threading.Thread(target=speech_recorder, daemon=True).start()