# -*- coding: utf-8 -*-
"""
MessageWindows: a Windows automation backend that drives mouse and keyboard
input entirely through Win32 window messages (PostMessage/SendMessage)
instead of the real, global mouse/keyboard (SendInput / SetCursorPos /
scancode injection) used by airtest.core.win.win.Windows.

Why:
    The base `Windows` class moves the real system cursor and sends real
    (or scancode-simulated) keyboard input via pywinauto's `mouse`/
    `keyboard` modules and `ctypesinput.key_press/key_release`. That
    steals focus/cursor from whatever the user is doing and requires the
    target window to be foregrounded.

    `MessageWindows` instead posts WM_MOUSEMOVE / WM_LBUTTONDOWN / WM_KEYDOWN
    / WM_CHAR / etc. directly to the target window's message queue. The
    system cursor never moves and no other window is affected.

Caveats (inherent to message-based input, not specific to this code):
    - Only works against applications that actually process standard
      WM_MOUSE*/WM_KEY*/WM_CHAR messages. Many games / engines read
      raw input or DirectInput and will ignore posted messages entirely
      -- for those, use the normal `Windows` backend instead.
    - Requires a concrete target window handle (connect with `handle=`).
    - Mouse coordinates are window-client-relative, same as the base class.
"""

import time

import win32api
import win32con
import win32gui

from airtest.core.win.win import Windows
from airtest.utils.snippet import get_absolute_coordinate
from airtest.utils.logger import get_logger

LOGGING = get_logger(__name__)


# Mapping from the key names accepted by Windows.key_press()/keyevent()
# (see their docstrings) to Win32 virtual-key codes. Extend as needed.
VK_MAP = {
    "BACKSPACE": win32con.VK_BACK,
    "TAB": win32con.VK_TAB,
    "ENTER": win32con.VK_RETURN,
    "LSHIFT": win32con.VK_LSHIFT,
    "RSHIFT": win32con.VK_RSHIFT,
    "LCTRL": win32con.VK_LCONTROL,
    "RCTRL": win32con.VK_RCONTROL,
    "LALT": win32con.VK_LMENU,
    "RALT": win32con.VK_RMENU,
    "CAPS_LOCK": win32con.VK_CAPITAL,
    "ESCAPE": win32con.VK_ESCAPE,
    "SPACE": win32con.VK_SPACE,
    "PAGE_UP": win32con.VK_PRIOR,
    "PAGE_DOWN": win32con.VK_NEXT,
    "END": win32con.VK_END,
    "HOME": win32con.VK_HOME,
    "LEFT": win32con.VK_LEFT,
    "UP": win32con.VK_UP,
    "RIGHT": win32con.VK_RIGHT,
    "DOWN": win32con.VK_DOWN,
    "PRINT_SCREEN": win32con.VK_SNAPSHOT,
    "PAUSE": win32con.VK_PAUSE,
    "INSERT": win32con.VK_INSERT,
    "DELETE": win32con.VK_DELETE,
    "LWINDOWS": win32con.VK_LWIN,
    "RWINDOWS": win32con.VK_RWIN,
    "MENU": win32con.VK_APPS,
    "NUM_LOCK": win32con.VK_NUMLOCK,
    "SCROLL_LOCK": win32con.VK_SCROLL,
    "NUMPAD_0": win32con.VK_NUMPAD0,
    "NUMPAD_1": win32con.VK_NUMPAD1,
    "NUMPAD_2": win32con.VK_NUMPAD2,
    "NUMPAD_3": win32con.VK_NUMPAD3,
    "NUMPAD_4": win32con.VK_NUMPAD4,
    "NUMPAD_5": win32con.VK_NUMPAD5,
    "NUMPAD_6": win32con.VK_NUMPAD6,
    "NUMPAD_7": win32con.VK_NUMPAD7,
    "NUMPAD_8": win32con.VK_NUMPAD8,
    "NUMPAD_9": win32con.VK_NUMPAD9,
    "NUMPAD_.": win32con.VK_DECIMAL,
    "NUMPAD_+": win32con.VK_ADD,
    "NUMPAD_-": win32con.VK_SUBTRACT,
    "NUMPAD_*": win32con.VK_MULTIPLY,
    "NUMPAD_/": win32con.VK_DIVIDE,
    "NUMPAD_ENTER": win32con.VK_RETURN,
    "F1": win32con.VK_F1, "F2": win32con.VK_F2, "F3": win32con.VK_F3,
    "F4": win32con.VK_F4, "F5": win32con.VK_F5, "F6": win32con.VK_F6,
    "F7": win32con.VK_F7, "F8": win32con.VK_F8, "F9": win32con.VK_F9,
    "F10": win32con.VK_F10, "F11": win32con.VK_F11, "F12": win32con.VK_F12,
}

# mouse button name -> (WM_*DOWN, WM_*UP, MK_* wparam flag)
BUTTON_MSG = {
    "left": (win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON),
    "right": (win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP, win32con.MK_RBUTTON),
    "middle": (win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP, win32con.MK_MBUTTON),
}


class MessageWindows(Windows):
    """
    Windows client that drives all mouse and keyboard input via posted
    Win32 window messages sent directly to the target window, instead of
    the real/global input used by the base `Windows` class.

    Example:
        >>> dev = MessageWindows(handle=123456)
        >>> dev.touch((100, 100))
        >>> dev.text("hello")

    Note:
        A concrete window handle is required (either passed to __init__
        or resolved via connect()) since messages need a real target hwnd.
    """

    def __init__(self, handle=None, dpifactor=1, **kwargs):
        super(MessageWindows, self).__init__(handle=handle, dpifactor=dpifactor, **kwargs)
        # We never move the real system cursor, so we can't rely on
        # win32api.GetCursorPos() to know "current" mouse position --
        # track our own virtual cursor instead.
        self._virtual_cursor = (0, 0)

    # ------------------------------------------------------------------ #
    # low level helpers
    # ------------------------------------------------------------------ #

    def _target_hwnd(self):
        """Window handle that messages are posted to."""
        if self.handle:
            return self.handle
        if self._top_window:
            return self._top_window.handle
        raise RuntimeError(
            "MessageWindows requires a connected window handle to post messages to."
        )

    @staticmethod
    def _make_lparam(x, y):
        return win32api.MAKELONG(int(x), int(y))

    def _post(self, msg, wparam=0, lparam=0):
        win32gui.PostMessage(self._target_hwnd(), msg, wparam, lparam)

    def _send(self, msg, wparam=0, lparam=0):
        win32gui.SendMessage(self._target_hwnd(), msg, wparam, lparam)

    # ------------------------------------------------------------------ #
    # mouse
    # ------------------------------------------------------------------ #

    def _post_mouse_move(self, x, y, wparam=0):
        self._post(win32con.WM_MOUSEMOVE, wparam, self._make_lparam(x, y))
        self._virtual_cursor = (x, y)

    def _post_mouse_button(self, button, down, x, y):
        down_msg, up_msg, flag = BUTTON_MSG[button]
        msg = down_msg if down else up_msg
        wparam = flag if down else 0
        self._post(msg, wparam, self._make_lparam(x, y))

    def touch(self, pos, **kwargs):
        """
        Perform a mouse click via posted window messages (no real cursor
        movement). Same signature/behaviour as Windows.touch().
        """
        duration = kwargs.get("duration", 0.01)
        right_click = kwargs.get("right_click", False)
        button = "right" if right_click else "left"
        steps = kwargs.get("steps", 1)
        offset = kwargs.get("offset", 0)

        start = self._action_pos(self._virtual_cursor)
        ori_end = get_absolute_coordinate(pos, self)
        end = self._action_pos(ori_end)

        start_x, start_y = self._fix_op_pos(start)
        end_x, end_y = self._fix_op_pos(end)

        interval = float(duration) / steps
        time.sleep(interval)

        for i in range(1, steps):
            x = int(start_x + (end_x - start_x) * i / steps)
            y = int(start_y + (end_y - start_y) * i / steps)
            self._post_mouse_move(x, y)
            time.sleep(interval)

        self._post_mouse_move(end_x, end_y)

        for i in range(1, offset + 1):
            self._post_mouse_move(end_x + i, end_y + i)
            time.sleep(0.01)
        for i in range(offset):
            self._post_mouse_move(end_x + offset - i, end_y + offset - i)
            time.sleep(0.01)

        self._post_mouse_button(button, True, end_x, end_y)
        time.sleep(duration)
        self._post_mouse_button(button, False, end_x, end_y)
        return ori_end

    def double_click(self, pos):
        ori_pos = get_absolute_coordinate(pos, self)
        x, y = self._fix_op_pos(self._action_pos(ori_pos))
        self._post_mouse_move(x, y)
        self._post(win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, self._make_lparam(x, y))
        self._post(win32con.WM_LBUTTONUP, 0, self._make_lparam(x, y))
        self._post(win32con.WM_LBUTTONDBLCLK, win32con.MK_LBUTTON, self._make_lparam(x, y))
        self._post(win32con.WM_LBUTTONUP, 0, self._make_lparam(x, y))
        return ori_pos

    def swipe(self, p1, p2, duration=0.8, steps=5, button="left"):
        ori_from = get_absolute_coordinate(p1, self)
        ori_to = get_absolute_coordinate(p2, self)
        from_x, from_y = self._fix_op_pos(self._action_pos(ori_from))
        to_x, to_y = self._fix_op_pos(self._action_pos(ori_to))

        interval = float(duration) / (steps + 1)
        self._post_mouse_move(from_x, from_y)
        self._post_mouse_button(button, True, from_x, from_y)
        time.sleep(interval)

        for i in range(1, steps):
            x = int(from_x + (to_x - from_x) * i / steps)
            y = int(from_y + (to_y - from_y) * i / steps)
            self._post_mouse_move(x, y)
            time.sleep(interval)

        for i in range(10):
            self._post_mouse_move(to_x, to_y)
            time.sleep(interval)

        self._post_mouse_button(button, False, to_x, to_y)
        return ori_from, ori_to

    def mouse_move(self, pos):
        if not isinstance(pos, tuple) or len(pos) != 2:
            raise ValueError('invalid literal for mouse_move: {}'.format(pos))
        try:
            x, y = self._action_pos(pos)
        except ValueError:
            raise ValueError('invalid literal for mouse_move: {}'.format(pos))
        self._post_mouse_move(x, y)

    def mouse_down(self, button='left'):
        buttons = {'left', 'middle', 'right'}
        if not isinstance(button, str) or button not in buttons:
            raise ValueError('invalid literal for mouse_down(): {}'.format(button))
        x, y = self._action_pos(self._virtual_cursor)
        self._post_mouse_button(button, True, x, y)

    def mouse_up(self, button='left'):
        buttons = {'left', 'middle', 'right'}
        if not isinstance(button, str) or button not in buttons:
            raise ValueError('invalid literal for mouse_up(): {}'.format(button))
        x, y = self._action_pos(self._virtual_cursor)
        self._post_mouse_button(button, False, x, y)

    # ------------------------------------------------------------------ #
    # keyboard
    # ------------------------------------------------------------------ #

    def _vk_and_scan(self, key):
        """Resolve a single key name/character to (vk_code, scan_code)."""
        key = key.strip()
        if key.upper() in VK_MAP:
            vk = VK_MAP[key.upper()]
        elif len(key) == 1:
            res = win32api.VkKeyScan(key)
            if res == -1:
                raise ValueError("Unsupported key: {}".format(key))
            vk = res & 0xFF
        else:
            raise ValueError("Unsupported key: {}".format(key))
        scan = win32api.MapVirtualKey(vk, 0)
        return vk, scan

    def key_press(self, key):
        """
        Post a WM_KEYDOWN for `key` to the target window.
        Overrides Windows.key_press(), which sends a real scancode via
        SendInput -- this instead only affects the target window.
        """
        vk, scan = self._vk_and_scan(key)
        lparam = 1 | (scan << 16)
        self._post(win32con.WM_KEYDOWN, vk, lparam)

    def key_release(self, key):
        """Post a WM_KEYUP for `key` to the target window."""
        vk, scan = self._vk_and_scan(key)
        lparam = 1 | (scan << 16) | (1 << 30) | (1 << 31)
        self._post(win32con.WM_KEYUP, vk, lparam)

    def keyevent(self, keyname, **kwargs):
        """
        Press+release one or more space-separated keys via posted
        WM_KEYDOWN/WM_KEYUP messages, e.g. keyevent("ENTER") or
        keyevent("LCTRL A").
        """
        interval = kwargs.get("interval", 0.01)
        for key in keyname.split():
            self.key_press(key)
            time.sleep(interval)
            self.key_release(key)
            time.sleep(interval)

    def text(self, text, **kwargs):
        """
        Input text via posted WM_CHAR messages -- works for normal unicode
        text entry into standard controls/edit boxes.
        """
        interval = kwargs.get("interval", 0.01)
        hwnd = self._target_hwnd()
        for ch in text:
            win32gui.PostMessage(hwnd, win32con.WM_CHAR, ord(ch), 0)
            time.sleep(interval)

    def paste(self):
        """Perform Ctrl+V via posted key messages."""
        self._post(win32con.WM_KEYDOWN, win32con.VK_CONTROL, 0)
        self._post(win32con.WM_KEYDOWN, ord('V'), 0)
        self._post(win32con.WM_KEYUP, ord('V'), 0)
        self._post(win32con.WM_KEYUP, win32con.VK_CONTROL, 0)

    def app_is_running(self):
        return True
