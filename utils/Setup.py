import os
import time
from typing import Optional, Tuple, Type, Callable, Union, List
import threading

from airtest.core.api import *
from airtest.core.cv import try_log_screen
from airtest.core.error import TargetNotFoundError
from airtest.core.helper import G, logwrap, delay_after_operation, set_logdir
from airtest.core.settings import Settings as ST
from airtest.utils.compat import script_log_dir
from pywinauto.findwindows import ElementNotFoundError

from zafkiel.device.cv import loop_find
from zafkiel.device.template import ImageTemplate as Template
from zafkiel.logger import logger
from zafkiel.exception import NotRunningError, ScriptError
from zafkiel.ocr.ocr import Ocr
from zafkiel.timer import Timer
from zafkiel.utils import random_rectangle_point

def init_device(platform="Android", uuid=None, **kwargs):
    """
    Initialize device if not yet, and set as current device.

    :param platform: Android, IOS or Windows
    :param uuid: uuid for target device, e.g. serialno for Android, handle for Windows, uuid for iOS
    :param kwargs: Optional platform specific keyword args, e.g. `cap_method=JAVACAP` for Android
    :return: device instance
    :Example:

        >>> init_device(platform="Android",uuid="SJE5T17B17", cap_method="JAVACAP")
        >>> init_device(platform="Windows",uuid="123456")
    """
    if platform == "messagewindows":
        from utils.MessageWindows import MessageWindows as cls
    else:
        cls = import_device_cls(platform)
    dev = cls(uuid, **kwargs)
    # Add device instance in G and set as current device.
    G.add_device(dev)
    return dev

@logwrap
def connect_device(uri):
    """
    Initialize device with uri, and set as current device.

    :param uri: an URI where to connect to device, e.g. `android://adbhost:adbport/serialno?param=value&param2=value2`
    :return: device instance
    :Example:

        >>> connect_device("Android:///")  # local adb device using default params
        >>> # local device with serial number SJE5T17B17 and custom params
        >>> connect_device("Android:///SJE5T17B17?cap_method=javacap&touch_method=adb")
        >>> # remote device using custom params Android://adbhost:adbport/serialno
        >>> connect_device("Android://127.0.0.1:5037/10.254.60.1:5555")
        >>> connect_device("Android://127.0.0.1:5037/10.234.60.1:5555?name=serialnumber")  # add serialno to params
        >>> connect_device("Windows:///")  # connect to the desktop
        >>> connect_device("Windows:///123456")  # Connect to the window with handle 123456
        >>> connect_device("windows:///?title_re='.*explorer.*'")  # Connect to the window that name include "explorer"
        >>> connect_device("Windows:///123456?foreground=False")  # Connect to the window without setting it foreground
        >>> connect_device("iOS:///127.0.0.1:8100")  # iOS device
        >>> connect_device("iOS:///http://localhost:8100/?mjpeg_port=9100")  # iOS with mjpeg port
        >>> connect_device("iOS:///http://localhost:8100/?mjpeg_port=9100&&udid=00008020-001270842E88002E")  # iOS with mjpeg port and udid
        >>> connect_device("iOS:///http://localhost:8100/?mjpeg_port=9100&&uuid=00008020-001270842E88002E")  # udid/uuid/serialno are all ok

    """
    platform, uuid, params = parse_device_uri(uri)
    dev = init_device(platform, uuid, **params)
    return dev

def _connect_device_with_timeout(dev: str, timeout: float = 5) -> bool:
    """
    Connect device with timeout to avoid blocking when window is not responding.

    Args:
        dev: Device URI string
        timeout: Timeout in seconds for each connection attempt

    Returns:
        True if connected successfully, False if timeout or ElementNotFoundError

    Raises:
        Other exceptions from connect_device
    """
    result = {"success": False, "error": None}

    def worker():
        try:
            connect_device(dev)
            result["success"] = True
        except ElementNotFoundError as e:
            result["error"] = e
        except Exception as e:
            result["error"] = e

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        # Thread is still running, connection timed out (likely SendMessage blocking)
        logger.warning(f"connect_device timed out after {timeout}s, window may not be responding")
        return False

    if result["success"]:
        return True

    if result["error"]:
        if isinstance(result["error"], ElementNotFoundError):
            return False
        raise result["error"]

    return False

def auto_setup(
        basedir: str = None,
        devices: Optional[List[str]] = None,
        firing_time: int = 30,
        logdir: Optional[Union[bool, str]] = None,
        project_root: str = None,
        compress: int = None
):
    """
    Auto setup running env and try to connect device if no device is connected.

    Args:
        basedir: basedir of script, __file__ is also acceptable.
        devices: connect_device uri in list.
        firing_time: Game starts taking time, this value should be set larger in old machine.
        logdir: log dir for script report, default is None for no log, set to ``True`` for ``<basedir>/log``.
        project_root: Project root dir for `using` api.
        compress: The compression rate of the screenshot image, integer in range [1, 99], default is 10

    Examples:
        auto_setup(__file__)
        auto_setup(__file__, devices=["Android://127.0.0.1:5037/SJE5T17B17"],
        ...        logdir=True, project_root=r"D:\\test\\logs", compress=90)
    """
    if basedir:
        if os.path.isfile(basedir):
            basedir = os.path.dirname(basedir)
        if basedir not in G.BASEDIR:
            G.BASEDIR.append(basedir)
    if devices:
        startup_time = Timer(firing_time).start()
        for dev in devices:
            connected = False
            while not startup_time.reached():
                if _connect_device_with_timeout(dev, timeout=5):
                    connected = True
                    break
                time.sleep(3)
            if not connected:
                raise NotRunningError(dev)
    if logdir:
        logdir = script_log_dir(basedir, logdir)
        set_logdir(logdir)
    if project_root:
        ST.PROJECT_ROOT = project_root
    if compress:
        ST.SNAPSHOT_QUALITY = compress
