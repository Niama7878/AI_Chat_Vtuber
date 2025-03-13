import websocket
import json
import os
from status import update_status
import threading
import noise
import random
import time

# 全局 WebSocket 连接 & 线程锁
ws_global = None
lock = threading.Lock()

token_global = None # 全局 Token 变量
current_angles = {"x": 0.0, "y": 0.0, "z": 0.0} # 全局变量存储当前角度
velocities = {"x": 0.0, "y": 0.0, "z": 0.0}  # 存储角速度
t = 0  # 时间参数
direction_x = 0 # 角度 x
direction_y = 0 # 角度 y
direction_z = 0 # 角度 z

# 热键字典
hostkeys_list = {  
    "嘟嘴": "e629914de8274d2bbb5a2fba351ac961",
    "星星眼": "56e08112c81c4ba9ad97ba6016e40865",
    "爱心眼": "9c11d9f795d84744a62cdb3726e87f59",
    "脸红": "b260bb4c8978462a85c5e7143c90bc0d",
    "脸黑": "218b32ebc8cf424eab1fe7e22cce953b",
}

def load_token(token_file):
    # 加载存储的令牌
    if os.path.exists(token_file):
        with open(token_file, "r") as file:
            return json.load(file).get("authenticationToken")
    else:
        update_status("找不到令牌文件，重新请求令牌...")
        return None

def save_token(token, token_file):
    # 保存令牌到文件
    with open(token_file, "w") as file:
        json.dump({"authenticationToken": token}, file)
        update_status("令牌已保存！")

def control_movement():
    # 控制 Live2D 随机移动
    global current_angles, velocities, t, direction_x, direction_y, direction_z
    t += 0.02  # 让运动更平滑

    # 让方向有一定概率改变，避免持续朝同一方向
    if random.random() < 0.5:  
        direction_x *= -1  
    if random.random() < 0.5:
        direction_y *= -1  
    if random.random() < 0.5:
        direction_z *= -1  

    # 计算目标角度，并限制最大幅度，避免大幅甩头
    target_x = max(min(direction_x * noise.pnoise1(t, repeat=1000) * 10 + random.uniform(-3, 3), 15), -15)
    target_y = max(min(direction_y * noise.pnoise1(t + 100, repeat=1000) * 20 + random.uniform(-5, 5), 20), -20)
    target_z = max(min(direction_z * noise.pnoise1(t + 200, repeat=1000) * 25 + random.uniform(-8, 8), 25), -25)

    # 细微的抖动
    micro_noise = lambda: noise.pnoise1(t * 8, repeat=1000) * 1.2
    target_x += micro_noise()
    target_y += micro_noise()
    target_z += micro_noise()

    # 调整惯性，让运动更快调整方向，避免持续向某一方向甩
    inertia = 0.75  
    velocities["x"] = velocities["x"] * inertia + (target_x - current_angles["x"]) * (1 - inertia)
    velocities["y"] = velocities["y"] * inertia + (target_y - current_angles["y"]) * (1 - inertia)
    velocities["z"] = velocities["z"] * inertia + (target_z - current_angles["z"]) * (1 - inertia)

    # 更新角度
    current_angles["x"] += velocities["x"]
    current_angles["y"] += velocities["y"]
    current_angles["z"] += velocities["z"]

    # 偶尔停顿一下
    if random.random() < 0.1:
        time.sleep(random.uniform(0.3, 1.0))

    return [
        {"id": "FaceAngleX", "value": current_angles["x"]},
        {"id": "FaceAngleY", "value": current_angles["y"]},
        {"id": "FaceAngleZ", "value": current_angles["z"]}
    ]

def change_parameters():
    # 发送参数修改请求
    while True:
        parameter = control_movement()
        send_request("InjectParameterDataRequest", "SomeID", {
            "pluginName": "AI_Chat_Vtuber",
            "pluginDeveloper": "Niama78",
            "authenticationToken": token_global,
            "faceFound": True,
            "mode": "set",
            "parameterValues": parameter
        })
        time.sleep(0.1)

def send_host_key(hostkey):
    # 发送热键触发请求
    if hostkey == "无":
        return
    
    send_request("HotkeyTriggerRequest", "SomeID", {
        "pluginName": "AI_Chat_Vtuber",
        "pluginDeveloper": "Niama78",
        "authenticationToken": token_global,
        "hotkeyID": hostkeys_list[hostkey]
    })

def send_request(message_type, request_id, data):
    # 发送请求到 WebSocket
    request_data = {
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "messageType": message_type,
        "requestID": request_id,
        "data": data
    }

    with lock:
        try:
            ws_global.send(json.dumps(request_data))  # 发送请求数据

        except Exception as e:
            update_status(f"发送请求失败：{e}")

def on_open(token_file):
    # WebSocket 连接打开时的回调
    global token_global
    token = load_token(token_file)  # 加载令牌
    
    if token:
        token_global = token
        authenticate() # 进行身份验证
    else:
        request_authentication_token()  # 请求身份验证令牌

def authenticate():
    # 进行身份验证
    send_request("AuthenticationRequest", "AuthRequestID", {
        "pluginName": "AI_Chat_Vtuber",
        "pluginDeveloper": "Niama78",
        "authenticationToken": token_global
    })

def request_authentication_token():
    # 请求身份验证令牌
    send_request("AuthenticationTokenRequest", "TokenRequestID", {
        "pluginName": "AI_Chat_Vtuber",
        "pluginDeveloper": "Niama78"
    })
    update_status("请求身份验证令牌...")

def on_message(ws, message):
    # 接收到消息时的回调
    global token_global
    response = json.loads(message)  # 解析消息
    message_type = response.get("messageType")  # 获取消息类型

    if message_type == "AuthenticationTokenResponse":
        if "authenticationToken" in response["data"]:
            update_status("令牌请求成功！")
            token = response["data"]["authenticationToken"] # 获取令牌
            save_token(token, "token.json")  # 保存令牌
            token_global = token # 更新全局令牌
            authenticate() # 进行验证触发后续事件
      
    elif message_type == "AuthenticationResponse":
        if response["data"].get("authenticated") is True:
            threading.Thread(target=change_parameters, daemon=True).start() # Vtuber 后台随机移动线程
            
        else:
            update_status("身份验证失败，重新请求令牌...") 
            request_authentication_token()  # 请求新的令牌

    elif message_type == "APIError":
        update_status(f"Vtuber Studio API 错误：{response['data']['errorMessage']}")

def on_close(ws, close_status_code, close_msg):
    # WebSocket 连接关闭时的回调
    update_status(f"Vtuber Studio 关闭信息：{close_status_code}, {close_msg}")
    connect_ws() # 尝试重新连接

def on_error(ws, error):
    # WebSocket 发生错误时的回调
    update_status(f"Vtuber Studio WebSocket 错误：{error}")

def connect_ws():
    # 连接 WebSocket
    global ws_global

    try:
        ws_global = websocket.WebSocketApp(
            "ws://localhost:8001",
            on_open=lambda ws: on_open("token.json"), 
            on_message=on_message,
            on_close=on_close,
            on_error=on_error,
        )

        threading.Thread(target=ws_global.run_forever, daemon=True).start()
        
    except Exception as e:
        update_status(f"连接 Vtuber Studio WebSocket 失败：{e}")

connect_ws()