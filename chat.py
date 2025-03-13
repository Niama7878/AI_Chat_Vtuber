import json
import os
import requests
import websocket
import threading
import time
from dotenv import load_dotenv 
from status import update_status, processing
from vts import send_host_key
from tts import add_buffer
import regex
import memory

load_dotenv()  # 加载 .env 文件
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # OpenAI API 密钥
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY") # YouTube API 密钥

# Openai WebSocket URL & 头部信息
OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17"
HEADERS = [
    "Authorization: Bearer " + OPENAI_API_KEY,
    "OpenAI-Beta: realtime=v1"
]

live_chat_id = "" # Youtube 直播视频 ID
next_page_token = None # 下一页令牌
id_list = [] # 保存历史记录使用
global_id_list = [] # 不包括 "msg_001"，从 "msg_002" 开始生成 ID
received_text = "" # 存储接收到的全部字体

# 全局 WebSocket 连接 & 线程锁
ws_global = None
lock = threading.Lock()

emotion_event = {
    "type": "response.create",
    "response": {
        "modalities": ["text"], 
        "instructions": "请使用 tools 进行分析，不要生成额外文本",
        "tools": [
            {
                "type": "function",
                "name": "emotion_detection",
                "description": "分析对话情绪，仅返还任意一个情绪",
                "parameters": {
                "type": "object",
                "properties": {
                    "嘟嘴": {"type": "string"},
                    "星星眼": {"type": "string"},
                    "爱心眼": {"type": "string"},
                    "脸红": {"type": "string"},
                    "脸黑": {"type": "string"},
                    "无": {"type": "string"}
                },
                "required": []
                }
            }
        ],
        "conversation": None,
        "input": [] 
    }
}

def connect_ws():
    # 建立 WebSocket 连接 
    global ws_global

    try:
        ws_global = websocket.WebSocketApp(
            OPENAI_WS_URL,
            header=HEADERS,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error,
        )
        threading.Thread(target=ws_global.run_forever, daemon=True).start()

    except Exception as e:
        update_status(f"OpenAI WebSocket 连接失败：{e}")

def on_open(ws):
    # 连接成功时触发 
    with open("character_setup.txt", "r", encoding="utf-8") as f:
        content = f.read() 

    character_setup = [{ 
        "type": "conversation.item.create",
        "previous_item_id": None,
        "item": {
            "id": "msg_001",
            "type": "message",
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": content # 添加角色人设
                }
            ]
        }
    }]
    
    send_message(character_setup, False, False) # 只发送一次角色人设

def remove_emoji(text):
    # 去除 emoji 并去掉空格
    emoji_pattern = regex.compile(r'\p{Emoji}', flags=regex.UNICODE)
    return emoji_pattern.sub('', text).strip() 

def on_message(ws, message):
    # 处理从 OpenAI WebSocket 收到的数据
    global received_text, last_update_time, id_list, global_id_list, emotion_event

    data = json.loads(message)  # 解析收到的消息
    event_type = data.get("type") # 获取消息类型

    if event_type in ["response.text.delta", "response.function_call_arguments.delta"]:
        delta = data.get("delta", "")  # 获取文本
        if event_type == "response.text.delta":
            add_buffer(remove_emoji(delta))

        received_text += remove_emoji(delta)

    elif event_type == "response.text.done":
        emotion_event["response"]["input"].append({
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": received_text
            }]
        })
        
        for id in id_list:
            memory.update_chat_response(id, received_text) 
            id_list.clear() # 清空所有以保存纪录的 ID

        received_text = ""
        send_message([], False, True)

    elif event_type == "response.function_call_arguments.done":
        received_text = json.loads(received_text)
        send_host_key(next(iter(received_text))) # 触发表情

        ws_global.close() # 断开连接
        emotion_event["response"]["input"] = []
        received_text = ""  
        global_id_list.clear()
            
def on_close(ws, close_status_code, close_msg):
    # WebSocket 断开时触发 
    #update_status(f"OpenAI WebSocket 关闭信息：{close_status_code}, {close_msg}")
    connect_ws() # 尝试重新连接

def on_error(ws, error):
    # WebSocket 发生错误 
    update_status(f"OpenAI WebSocket 错误：{error}")

def get_live_chat_id():
    # 获取 Live Chat ID
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?id={live_chat_id}&part=liveStreamingDetails&key={YOUTUBE_API_KEY}"
        response = requests.get(url).json()
        return response.get("items", [{}])[0].get("liveStreamingDetails", {}).get("activeLiveChatId", None)
    
    except Exception as e:
        update_status(f"获取 Youtube Live Chat ID 失败：{e}")
        return None

def get_channel_info(channel_id):
    # 获取频道信息
    try:
        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id={channel_id}&key={YOUTUBE_API_KEY}"
        response = requests.get(url)

        if response.status_code != 200:
            print(f"获取 Youtube 频道信息失败：{response.json()}")
            return None

        data = response.json()
        items = data.get("items", [])

        return items[0]["snippet"]["title"]  # 返回频道的显示名称
    
    except Exception as e:
        update_status(f"获取 Youtube 频道信息失败: {e}")
        return None
    
def crawl_youtube_messages():
    # 爬取 YouTube 聊天消息
    global next_page_token
    live_chat_id = get_live_chat_id()

    if live_chat_id:
        while True:
            try:
                chat_url = f"https://www.googleapis.com/youtube/v3/liveChat/messages?liveChatId={live_chat_id}&part=snippet&key={YOUTUBE_API_KEY}"
                if next_page_token:
                    chat_url += f"&pageToken={next_page_token}" # 添加分页令牌

                response = requests.get(chat_url)
                if response.status_code != 200:
                    update_status(f"获取 Youtube 消息失败：{response.status_code}")
                    continue

                chat_messages = response.json()

                for message in chat_messages.get('items', []): # 遍历消息列表
                    display_message = message['snippet']['displayMessage'] # 获取显示消息
                    author_channel_id = message["snippet"].get("authorChannelId", "Unknown Author")  # Channel ID
                    display_name = get_channel_info(author_channel_id)  # 获取发言者的显示名称
                    memory.save_chat_record(display_name, "yt_message", display_message) # 添加消息记录
   
                next_page_token = chat_messages.get('nextPageToken') # 获取下一页的令牌

            except Exception as e:
                update_status(f"爬取 YouTube 消息失败：{e}")

            time.sleep(15)

def generate_id():
    # 从 "msg_002" 开始递增生成 ID
    new_id = f"msg_{len(global_id_list) + 2:03}"  
    global_id_list.append(new_id)  # 将新 ID 添加到 global_id_list
    return new_id

def process_pending_questions():
    # 处理和生成 OpenAI WebSocket 支持的聊天内容
    global id_list
    records_list, id_list = memory.get_records()
    messages = []
    
    if records_list:  # 如果有待处理记录
        previous_item_id = "msg_001"  # 第一个记录的 previous_item_id 始终是 msg_001
        for rec in reversed(records_list):
            user_id = generate_id()  # 为每个信息生成新 ID

            messages.append({
                "type": "conversation.item.create",
                "previous_item_id": previous_item_id,
                "item": {
                    "id": user_id,
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": f"{rec["user_id"]}：{rec["question"]}"
                    }]
                }
            })

            if rec.get("answered", False):
                assistant_id = generate_id()  # 为每个助手生成新 ID
                messages.append({
                    "type": "conversation.item.create",
                    "previous_item_id": user_id,
                    "item": {
                        "id": assistant_id,
                        "type": "message",
                        "role": "assistant",
                        "content": [{
                            "type": "text",
                            "text": rec["response"]
                        }]
                    }
                })

                previous_item_id = assistant_id  # 更新 previous_item_id 为刚刚生成的 assistant_id
        
        send_message(messages, True, False)
        processing(True) # 开启处理状态

def send_message(prompt_payload, generate_response, emotion_detect):
    # 通过 WebSocket 发送消息给 ChatGPT 
    global emotion_event
    with lock:
        try:
            for item in prompt_payload:
                ws_global.send(json.dumps(item)) 

                if item["item"]["id"] != "msg_001":
                    emotion_event["response"]["input"].append({
                        "type": "message",
                        "role": item["item"]["role"],
                        "content": item["item"]["content"]
                    })
                    content_text = item["item"]["content"][0]["text"]
                
                    if item["item"]["role"] == "assistant":
                        content_text = f"ChatGpt：{content_text}"

                    update_status(content_text)
                    
                time.sleep(0.2)  

            if generate_response: # 触发 AI 生成回复
                generate_event = {
                    "type": "response.create",
                    "response": {
                            "modalities": ["text"], 
                            "instructions": "根据上下文推理生成精简回复",
                            "temperature": 1.0,
                            "conversation": None
                        }
                    }
                ws_global.send(json.dumps(generate_event))
            
            if emotion_detect: # 对当前上下文进行情绪检测
                ws_global.send(json.dumps(emotion_event))
             
        except Exception as e:
            update_status(f"发送 OpenAI WebSocket 请求失败：{e}")

connect_ws()
threading.Thread(target=crawl_youtube_messages, daemon=True).start() 