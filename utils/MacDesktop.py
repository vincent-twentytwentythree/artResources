"""Airtest-compatible access to a macOS application window."""

import re
import time

import cv2
import numpy as np
import Quartz
from AppKit import NSRunningApplication, NSWorkspace, NSApplicationActivateIgnoringOtherApps


class MacDesktop:
    def __init__(self, uuid=None, title_re=None):
        self.uuid = uuid or title_re or "Hearthstone"
        self.title_re = re.compile(title_re or uuid or "Hearthstone")
        self._window = None
        self._image_size = None
        self._find_window()

    def _find_window(self):
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
        ) or []
        for window in windows:
            if window.get("kCGWindowLayer") != 0:
                continue
            title = window.get("kCGWindowName") or ""
            owner = window.get("kCGWindowOwnerName") or ""
            if self.title_re.search(title) or self.title_re.search(owner):
                self._window = window
                return window
        raise RuntimeError(f"No visible macOS window matches {self.title_re.pattern!r}")

    def snapshot(self, filename=None, quality=None, **kwargs):
        window = self._find_window()
        image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            window["kCGWindowNumber"],
            Quartz.kCGWindowImageBoundsIgnoreFraming,
        )
        if image is None:
            raise RuntimeError(
                "macOS Screen Recording permission is required to capture Hearthstone. "
                "Allow the terminal running Python in System Settings > Privacy & Security > Screen Recording."
            )
        width = Quartz.CGImageGetWidth(image)
        height = Quartz.CGImageGetHeight(image)
        stride = Quartz.CGImageGetBytesPerRow(image)
        raw = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(image))
        pixels = np.frombuffer(raw, dtype=np.uint8).reshape(height, stride)
        channels = Quartz.CGImageGetBitsPerPixel(image) // 8
        pixels = pixels[:, :width * channels].reshape(height, width, channels)
        frame = cv2.cvtColor(pixels, cv2.COLOR_BGRA2BGR)
        self._image_size = (width, height)
        if filename:
            cv2.imwrite(filename, frame)
        return frame

    def get_current_resolution(self):
        if self._image_size is None:
            # Resolve Retina image pixels before callers calculate their first click.
            window = self._find_window()
            image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectNull,
                Quartz.kCGWindowListOptionIncludingWindow,
                window["kCGWindowNumber"],
                Quartz.kCGWindowImageBoundsIgnoreFraming,
            )
            if image is not None:
                self._image_size = (
                    Quartz.CGImageGetWidth(image),
                    Quartz.CGImageGetHeight(image),
                )
        if self._image_size is not None:
            return self._image_size
        bounds = self._find_window()["kCGWindowBounds"]
        return int(bounds["Width"]), int(bounds["Height"])

    def screen_capture_available(self):
        return bool(Quartz.CGPreflightScreenCaptureAccess())

    def _screen_point(self, pos):
        window = self._find_window()
        bounds = window["kCGWindowBounds"]
        width, height = self.get_current_resolution()
        return (
            bounds["X"] + pos[0] * bounds["Width"] / width,
            bounds["Y"] + pos[1] * bounds["Height"] / height,
        )

    def touch(self, pos, right_click=False, duration=0.05, **kwargs):
        if not self.is_foreground():
            if not self.set_foreground():
                raise RuntimeError("Could not bring the target macOS window to the foreground")
            time.sleep(0.1)
        point = self._screen_point(pos)
        button = Quartz.kCGMouseButtonRight if right_click else Quartz.kCGMouseButtonLeft
        down = Quartz.kCGEventRightMouseDown if right_click else Quartz.kCGEventLeftMouseDown
        up = Quartz.kCGEventRightMouseUp if right_click else Quartz.kCGEventLeftMouseUp
        for event_type in (down, up):
            event = Quartz.CGEventCreateMouseEvent(None, event_type, point, button)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            if event_type == down:
                time.sleep(duration)

    def mouse_move(self, pos):
        point = self._screen_point(pos)
        event = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved, point, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def set_foreground(self):
        pid = self._find_window()["kCGWindowOwnerPID"]
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        return app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)

    def is_foreground(self):
        pid = self._find_window()["kCGWindowOwnerPID"]
        front = NSWorkspace.sharedWorkspace().frontmostApplication()
        return front is not None and front.processIdentifier() == pid
