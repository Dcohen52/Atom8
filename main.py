import os
import ctypes

ctypes.windll.user32.SetCursorPos(100, 20)
ctypes.windll.user32.mouse_event(2, 0, 0, 0,0) # left down
ctypes.windll.user32.mouse_event(4, 0, 0, 0,0) # left up
ctypes.windll.user32.SetCursorPos(100, 100)
ctypes.windll.user32.mouse_event(2, 0, 0, 0,0) # left down
ctypes.windll.user32.mouse_event(4, 0, 0, 0,0) # left up