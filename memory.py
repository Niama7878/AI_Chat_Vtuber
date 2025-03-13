import sqlite3
from rapidfuzz import fuzz
import random
import os

def init_db():
    # 初始化数据库
    conn = sqlite3.connect("chat_memory.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        event_type TEXT,
                        question TEXT,
                        response TEXT,
                        answered BOOLEAN
                    )''')
    conn.commit()
    conn.close()

if not os.path.exists("chat_memory.db"): # 没有 chat_memory.db 就创建
    init_db()

def save_chat_record(user_id, event_type, question):
    # 保存用户问题
    conn = sqlite3.connect("chat_memory.db")
    cursor = conn.cursor()

    if event_type == "tts_message": # 直接存入数据库
        cursor.execute('''INSERT INTO chat_records (user_id, event_type, question, answered)
                          VALUES (?, ?, ?, ?)''', (user_id, event_type, question, False))
        conn.commit()
        conn.close()
        return
    
    # 查询现有记录，检查是否有相似的问题
    cursor.execute("SELECT id, question FROM chat_records WHERE event_type = ? AND user_id = ?", (event_type, user_id))
    records = cursor.fetchall()

    for rec in records:  # 检查是否已有相似记录（相似度 >= 60%）
        if fuzz.ratio(question, rec[1]) >= 60:
            conn.close()
            return  

    # 没有相似问题，则存入数据库
    cursor.execute('''INSERT INTO chat_records (user_id, event_type, question, answered)
                      VALUES (?, ?, ?, ?)''', (user_id, event_type, question, False))
    conn.commit()
    conn.close()

def update_chat_response(record_id, response):
    # 更新问题回复
    conn = sqlite3.connect("chat_memory.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_records SET response = ?, answered = ? WHERE id = ?", (response, True, record_id))
    conn.commit()
    conn.close()

def get_records():
    # 获取过滤过的纪录
    conn = sqlite3.connect("chat_memory.db")
    cursor = conn.cursor()
    
    # 读取所有记录
    cursor.execute("SELECT id, user_id, event_type, question, response, answered FROM chat_records")
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        return None, None  # 如果没有记录，直接返回 None
    
    # 处理数据格式
    formatted_records = [
        {
            "id": rec[0],
            "user_id": rec[1],
            "event_type": rec[2],
            "question": rec[3],
            "response": rec[4],
            "answered": bool(rec[5]),
        }
        for rec in records
    ]
    
    records_list = []
    id_list = []
    
    for record in formatted_records: # 遍历所有记录，查找未回答的问题
        if not record.get("answered", False):
            if record["event_type"] == "tts_message": # 处理 TTS 类型
                similar_records = [
                    rec for rec in formatted_records
                    if not rec.get("answered", False)
                    and rec["id"] != record["id"]
                    and rec["event_type"] == "tts_message"
                    and fuzz.ratio(record.get("question", ""), rec.get("question", "")) >= 60
                ]
            else: # 处理 YouTube 类型
                similar_records = [
                    rec for rec in formatted_records
                    if not rec.get("answered", False)
                    and rec["id"] != record["id"]
                    and rec["event_type"] == "yt_message"
                    and fuzz.ratio(record.get("question", ""), rec.get("question", "")) >= 60
                ]

            similar_records.append(record) # 加入目前的纪录

            for rec in similar_records:
                id_list.append(rec["id"])  # 将 ID 添加到列表中

            chosen_record = random.choice(similar_records) # 随机选择一个相似的问题
            records_list.append(chosen_record)
            break  # 处理完一个未回答的问题后跳出循环

    if not records_list:
        return None, None # 如果没有待处理问题，返回 None
    
    # 仅和相同类型的已回答记录比较
    similar_records = [
        rec for rec in formatted_records
        if rec.get("answered", False)
        and rec.get("event_type") == records_list[0]["event_type"]
        and fuzz.ratio(records_list[0]["question"], rec.get("question", "")) >= 60
    ]
        
    if similar_records:
        records_list.append(random.choice(similar_records))  # 随机选择一个已回答的相似问题
    
    return records_list, id_list