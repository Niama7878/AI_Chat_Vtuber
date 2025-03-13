import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame
import threading
import time
import OpenGL.GL as gl
import freetype
import ctypes

class TextRenderer:
    def __init__(self, screen, font_path="ShanHaiNiuNaiBoBoW-2.ttf", font_size=60):
        self.screen = screen
        self.width, self.height = self.screen.get_size()
        self.font_path = font_path
        self.font_size = font_size
        self.face = freetype.Face(font_path)
        self.face.set_char_size(font_size * 64)

        self.text_queue = ""
        self.display_text = ""
        self.lines = []
        self.lock = threading.Lock()
        self.char_index = 0
        self.typing_speed = 0.15
        self.last_char_time = time.time()
        self.full_text_rendered_time = None

        self.texture_id = gl.glGenTextures(1)

    def update_text(self, text):
        # 外部调用接口，更新文本
        with self.lock:
            self.text_queue += "\n" + text if self.text_queue else text
            self.full_text_rendered_time = None

    def render_text(self):
        # 模拟打字效果，逐个字符显示
        with self.lock:
            if self.char_index < len(self.text_queue) and time.time() - self.last_char_time > self.typing_speed:
                self.char_index += 1
                self.display_text = self.text_queue[:self.char_index]
                self.lines = self.wrap_text(self.display_text)
                self.last_char_time = time.time()

                # 当文本完全渲染完毕时，记录完成时间
                if self.char_index == len(self.text_queue):
                    self.full_text_rendered_time = time.time()

            # 删除超出屏幕显示范围的旧文本
            max_lines = self.height // self.font_size
            while len(self.lines) > max_lines:
                self.lines.pop(0)
                self.display_text = "".join(self.lines)

            # 如果全部文本渲染完成后，2秒内没有新文本输入，则清空所有文本
            if self.full_text_rendered_time and time.time() - self.full_text_rendered_time > 2:
                self.text_queue = ""
                self.display_text = ""
                self.lines = []
                self.char_index = 0
                self.full_text_rendered_time = None

        # 清空背景颜色为绿色 (保持背景绿色)
        gl.glClearColor(0.0, 1.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        y_offset = 0
        for line in self.lines:
            # 计算行宽度
            line_width = 0
            for char in line:
                self.face.load_char(char, freetype.FT_LOAD_RENDER)
                line_width += self.face.glyph.linearHoriAdvance / 65536.0
            
            x_start_offset = (self.width - line_width) / 2 # 计算居中所需的 x 轴偏移量

            x_offset = x_start_offset # 使用计算出的起始 x 偏移量
            for char in line:
                self.render_char(char, x_offset, y_offset)
                self.face.load_char(char, freetype.FT_LOAD_RENDER)
                x_offset += self.face.glyph.linearHoriAdvance / 65536.0

            y_offset += self.font_size

    def render_char(self, char, x, y):
        self.face.load_char(char, freetype.FT_LOAD_RENDER)
        glyph = self.face.glyph
        bitmap = glyph.bitmap
        width, height = bitmap.width, bitmap.rows

        if width == 0 or height == 0:
            return

        # 创建 RGBA 纹理数据
        rgba_buffer = bytearray()
        for value in bitmap.buffer:
            alpha = value  # 将灰度值直接作为 Alpha 通道值
            if alpha > 0:  # 文字区域
                rgba_buffer.extend([int(255*1.0), int(255*0.75), int(255*0.8), alpha]) # 粉色 + Alpha
            else:       # 文字区域外，设置为透明黑色
                rgba_buffer.extend([0, 0, 0, 0]) # 透明黑色

        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        
        # 使用 GL_RGBA 格式上传 RGBA 数据
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, bytes(rgba_buffer))
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        gl.glColor4f(1.0, 0.75, 0.8, 1.0)  # 粉色字体 (颜色设置保持不变，因为颜色信息现在在纹理数据中)

        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0, 0)
        gl.glVertex2f(x, y)
        gl.glTexCoord2f(1, 0)
        gl.glVertex2f(x + width, y)
        gl.glTexCoord2f(1, 1)
        gl.glVertex2f(x + width, y + height)
        gl.glTexCoord2f(0, 1)
        gl.glVertex2f(x, y + height)
        gl.glEnd()
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glDisable(gl.GL_BLEND)

    def wrap_text(self, text):
        # 自动换行功能
        lines = []
        current_line = ""
        for char in text:
            test_line = current_line + char
            width = 0
            for c in test_line:
                self.face.load_char(c, freetype.FT_LOAD_RENDER)
                width += self.face.glyph.linearHoriAdvance / 65536.0

            if width > self.width - 100:
                lines.append(current_line)
                current_line = char
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
        return lines

renderer = None
running = True

def add_text(message):
    # 外部接口：用于添加文本
    global renderer
    if renderer:
        renderer.update_text(message)

def move_window(hwnd):
    # 允许拖动无边框窗口
    ctypes.windll.user32.ReleaseCapture()
    ctypes.windll.user32.SendMessageW(hwnd, 0xA1, 2, 0)

def start_pygame():
    global renderer, running
    pygame.init()
    screen = pygame.display.set_mode((1400, 240), pygame.OPENGL | pygame.DOUBLEBUF | pygame.NOFRAME)
    pygame.display.set_caption("聊天信息显示框")

    hwnd = pygame.display.get_wm_info()["window"] # 获取窗口句柄 (Windows only)

    gl.glViewport(0, 0, 1400, 240)
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glLoadIdentity()
    gl.glOrtho(0, 1400, 240, 0, -1, 1)

    renderer = TextRenderer(screen)
    clock = pygame.time.Clock()

    gl.glClearColor(0.0, 1.0, 0.0, 1.0) # 初始清屏颜色设置为绿色

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # 左键按下
                move_window(hwnd)

        renderer.render_text()
        pygame.display.flip()
        
        clock.tick(30)

    pygame.quit()

threading.Thread(target=start_pygame, daemon=True).start()