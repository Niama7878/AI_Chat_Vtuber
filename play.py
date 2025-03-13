import queue
import threading
import subprocess
import shutil

class AudioPlayer:
    def __init__(self):
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.running = True  # 控制播放线程的开关
        self.thread = threading.Thread(target=self._play_loop, daemon=True)
        self.thread.start()

    def is_installed(self, lib_name: str) -> bool:
        return shutil.which(lib_name) is not None

    def add_audio(self, audio: bytes):
        # 把音频数据加入队列
        self.audio_queue.put(audio)

    @property
    def is_playing(self):
        return self._is_playing
    
    @is_playing.setter
    def is_playing(self, value):
        self._is_playing = value

    def _play_loop(self):
        # 播放队列中的音频 
        while self.running:
            try:
                audio = self.audio_queue.get(timeout=0.1) 
                if audio is None:  # 退出信号
                    break
                self.is_playing = True
                self._play_audio(audio)
                self.is_playing = False
            except queue.Empty:
                continue  # 没有新音频就继续等待

    def _play_audio(self, audio: bytes):
        # 使用 ffplay 播放音频
        if not self.is_installed("ffplay"):
            raise ValueError("需要安装 ffmpeg (ffplay) 才能播放音频！")
        
        args = ["ffplay", "-autoexit", "-nodisp", "-volume", "100", "-"]
        proc = subprocess.Popen(
            args=args,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.communicate(input=audio)
        proc.poll()