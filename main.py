from chat import process_pending_questions
import time
from status import processing
import stt

def main():
    time.sleep(4) # 等待所有连接完成

    while True: 
        if not processing(): # 确保不在处理状态中
            process_pending_questions() 
            time.sleep(1)
            
        time.sleep(0.1)
        
if __name__ == "__main__":
    main() # 运行主程序