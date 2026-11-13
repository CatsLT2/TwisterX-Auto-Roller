"""
TwisterX Auto Roller — joiner, OCR reader, requirement checker and Discord notifier.
Version: 1.3.2

What's new in 1.3.2:
  - Only one copy can run; opening it again brings the running window to the front.
  - Fixed: closing during the tour made the window reopen. The close button now asks once
    (Quit / keep in tray), and Quit really exits.

What's new in 1.3.1:
  - Renamed to TwisterX Auto Roller (TwisterX_Auto_Roller.py / "TwisterX Auto Roller.exe" / "Start TwisterX Auto Roller.bat").

What's new in 1.3.0:
  - Rebranded to TwisterX (TwisterX.py / TwisterX.exe / Start TwisterX.bat).
  - EXE carries proper version information and can be code-signed by build.bat.

What's new in 1.2.0:
  - Built-in guided tour on first launch: dims the window, circles / rings each feature
    with a pulsing highlight and an arrow, and explains it page by page (Back / Next /
    Skip, arrow keys work). Shown once; replay it from Settings → "Replay tutorial".

What's new in 1.1.1 (bug fixes):
  - Mouse-to-corner failsafe really works now, and Stop / Esc interrupt clicks mid-sequence.
  - Interval is now the delay between rerolls in auto mode (was a fixed 2 s).
  - OCR errors no longer reroll forever when auto mode and auto-reroll are both off.
  - "Read OCR now" is a test read: it never sends webhooks.
  - Webhook Test doesn't ping the role and tells you if the URL isn't saved yet.
  - Screenshots cover all monitors, so regions on a second screen work.
  - New roblox.com/share?code=...&type=Server links are accepted.
  - Preview / test reads use the current slider values; no 5 s wait when Spawn isn't set;
    warning when the Forecast position is only a guess; Esc doesn't stop while typing;
    bad Load wait / Interval values are reported in the log.

What's new in 1.1.0 (from 1.0.0):
  - Brand-new modern UI built with customtkinter: left sidebar navigation
    (Run / Calibration / Requirements / Records / Settings), rounded cards, stat tiles,
    switches and segmented buttons, a colour-coded log and a coloured pass/fail badge.
  - Restyled "Requirements met" popup and region preview.
  - New Settings page (stored under "settings" in config.json): appearance mode, accent colour,
    UI scaling, close-button behaviour (tray / quit), always on top, desktop notifications,
    sound on pass, Discord role ping on/off + editable role ID, data.txt history limit,
    log line limit, "Open data folder" and "Reset settings to defaults".
  - New dependency: customtkinter (pip install customtkinter).

What's new in 1.0.0 (from 0.0.12):
  - New tabbed dark UI (Run / Calibration / Requirements / Records) with a live log panel
    and a status bar, instead of one giant scrolling page.
  - Thread-safe: the worker thread never touches Tk widgets directly (fixes random freezes
    and "main thread is not in main loop" crashes).
  - "Read OCR now" runs in the background, so the window no longer freezes while reading.
  - Stop really stops: pressing Stop cancels pending rerolls and the auto-rejoin loop.
  - Config is cached in memory and written atomically (no more corrupted config.json if the
    app is killed mid-save, and far fewer disk writes).
  - config.json / data.txt live next to the script or EXE, no matter where it's launched from.
  - Tesseract is found automatically in the default install folders even when not on PATH.
  - DPI-aware, so click positions and screenshot regions line up on scaled displays.
  - Bug fix: Risk record conditions (e.g. Risk >= ENH) now work — they were never matching.
  - Session counters: scans, passes, record hits, and elapsed time.
  - Tray icon (optional, pip install pystray) — closing hides to tray.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tkinter import messagebox
from urllib.parse import parse_qs, urlparse

# DPI awareness must be set before any window / screen query.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# When double-clicked with python.exe, hide the black console window.
if not getattr(sys, "frozen", False):
    try:
        _con = ctypes.windll.kernel32.GetConsoleWindow()
        if _con and os.path.basename(sys.executable).lower() in ("python.exe", "py.exe") \
                and "--console" not in sys.argv:
            ctypes.windll.user32.ShowWindow(_con, 0)
    except Exception:
        pass

try:
    import mss
    import pyautogui
    import pytesseract
    import customtkinter as ctk
    import requests
    from PIL import Image, ImageDraw, ImageEnhance, ImageOps
except ImportError as _e:  # friendly message instead of a console that flashes and closes
    _r = tk.Tk()
    _r.withdraw()
    messagebox.showerror(
        "TwisterX Auto Roller - missing package",
        f"A required Python package is missing: {_e.name}\n\n"
        "Open a terminal and run:\n\n"
        "pip install customtkinter pyautogui pillow pytesseract mss requests pystray\n\n"
        "Then double-click the app again.")
    sys.exit(1)

try:
    import pystray
    HAVE_TRAY = True
except ImportError:
    HAVE_TRAY = False

# ═══════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════
VERSION = "1.3.2"
APP_NAME = "TwisterX Auto Roller"
ROLE_ID = ""  # default: none; set your own role ID in Settings

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CFG_FILE = APP_DIR / "config.json"
DATA_FILE = APP_DIR / "data.txt"
HISTORY_LIMIT = 1000  # default; editable in Settings

pyautogui.FAILSAFE = True

BASE_W, BASE_H = 2560, 1440
FORECAST_REL_X = 1260 / BASE_W
FORECAST_REL_Y = 125 / BASE_H

RISK_ORDER = ["NONE", "TSTM", "MRGL", "SLGT", "ENH", "MDT", "HIGH"]
OPS = [">=", "<="]
NUMERIC_FIELDS = ["Temperature", "Dew point", "PWAT", "SRH", "CAPE", "Lapse Rates", "Humidity", "Storm Motion"]
FILTER_FIELDS = ["Risk"] + NUMERIC_FIELDS
DISPLAY_FIELDS = FILTER_FIELDS

# Palette
C = {
    "bg": "#121417", "panel": "#1a1d22", "panel2": "#21252b", "border": "#2c313a",
    "fg": "#d7dae0", "muted": "#8b929e", "accent": "#4ea6dc", "accent_hi": "#6cbcf0",
    "ok": "#5fd38d", "ok_bg": "#17281e", "warn": "#e5c07b", "err": "#e06c75",
    "entry": "#0f1114", "select": "#264f78",
}
FONT = "Segoe UI"
MONO = "Consolas"


# ═══════════════════════════════════════════════════════
#  TESSERACT DISCOVERY
# ═══════════════════════════════════════════════════════
def find_tesseract() -> str | None:
    # 1) Bundled copy (inside the EXE, or a "tesseract" folder next to the script).
    for base in (getattr(sys, "_MEIPASS", None), APP_DIR):
        if base:
            exe = Path(base) / "tesseract" / "tesseract.exe"
            if exe.is_file():
                os.environ["TESSDATA_PREFIX"] = str(exe.parent / "tessdata")
                return str(exe)
    # 2) Installed copy.
    found = shutil.which("tesseract")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        cand = Path(base) / "Tesseract-OCR" / "tesseract.exe"
        if cand.is_file():
            return str(cand)
    return None


TESSERACT_PATH = find_tesseract()
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# ═══════════════════════════════════════════════════════
#  CONFIG (cached, thread-safe, atomic writes)
# ═══════════════════════════════════════════════════════
def default_filter() -> dict:
    f = {"Risk": {"enabled": False, "op": ">=", "value": "SLGT", "independent": False}}
    for k in NUMERIC_FIELDS:
        f[k] = {"enabled": False, "op": ">=", "value": 0.0, "independent": False}
    return f


def default_settings() -> dict:
    return {
        "appearance": "Dark", "theme": "blue", "scaling": 100,
        "close_action": "tray", "always_on_top": False,
        "notifications": True, "sound_on_pass": True,
        "ping_role": False, "role_id": ROLE_ID,
        "history_limit": HISTORY_LIMIT, "log_limit": 1500,
    }


def default_cfg() -> dict:
    return {
        "app": {"version": VERSION},
        "saved_link": "", "webhook_url": "",
        "panel": {"tl": None, "br": None}, "thermos": {"tl": None, "br": None},
        "ocr": {"threshold": 165, "contrast": 2.2},
        "filters": default_filter(), "filters_enabled": True,
        "records": [],
        "tutorial": {"done": False},
        "close_asked": False,
        "click": {"pause_ms": 50, "settle_ms": 120, "attempts": 3},
        "click_spots": {"spawn": None, "forecast": None},
        "auto_reroll": {"enabled": False},
        "pass_dialog": {"enabled": True},
        "run": {"load_wait": 25, "interval": 2, "click_sequence": True},
        "settings": default_settings(),
    }


def deep_merge(cfg, defs: dict) -> dict:
    if not isinstance(cfg, dict):
        cfg = {}
    for k, v in defs.items():
        if k not in cfg:
            cfg[k] = json.loads(json.dumps(v))
        elif isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k] = deep_merge(cfg[k], v)
    return cfg


def atomic_write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


class Config:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self._data = self._load()
        self.save()

    def _load(self) -> dict:
        c = {}
        if self.path.is_file():
            try:
                c = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                try:
                    shutil.copy(self.path, self.path.with_suffix(".json.bad"))
                except Exception:
                    pass
                c = {}
        c = deep_merge(c, default_cfg())
        c["app"]["version"] = VERSION
        return c

    def get(self, *keys, default=None):
        with self._lock:
            node = self._data
            for k in keys:
                if not isinstance(node, dict) or k not in node:
                    return default
                node = node[k]
            return json.loads(json.dumps(node))  # copy

    def set(self, *keys_and_value):
        *keys, value = keys_and_value
        with self._lock:
            node = self._data
            for k in keys[:-1]:
                node = node.setdefault(k, {})
            node[keys[-1]] = value
            self.save()

    def save(self):
        with self._lock:
            atomic_write_json(self.path, self._data)


CFG: Config  # set in main()


# ═══════════════════════════════════════════════════════
#  DATA LOG
# ═══════════════════════════════════════════════════════
_data_lock = threading.Lock()


def _empty_data():
    return {"last": {}, "history": []}


def load_data() -> dict:
    if not DATA_FILE.is_file():
        return _empty_data()
    try:
        txt = DATA_FILE.read_text(encoding="utf-8").strip()
        return json.loads(txt) if txt else _empty_data()
    except Exception:
        try:
            os.replace(DATA_FILE, DATA_FILE.with_suffix(".txt.bak"))
        except Exception:
            pass
        return _empty_data()


def log_result(vals: dict, passed: bool, reasons: list) -> bool:
    with _data_lock:
        d = load_data()
        last = d.get("last") or {}
        diff = {k: {"from": last.get(k, ""), "to": v} for k, v in vals.items() if last.get(k) != v}
        d["last"] = vals
        hist = d.setdefault("history", [])
        hist.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "values": vals, "changed": bool(diff), "diff": diff,
            "passed": passed, "reasons": reasons, "ver": VERSION,
        })
        try:
            limit = max(10, int(CFG.get("settings", "history_limit", default=HISTORY_LIMIT)))
        except (TypeError, ValueError):
            limit = HISTORY_LIMIT
        d["history"] = hist[-limit:]
        atomic_write_json(DATA_FILE, d)
        return bool(diff)


# ═══════════════════════════════════════════════════════
#  WIN32 RAW INPUT
# ═══════════════════════════════════════════════════════
_user32 = ctypes.windll.user32

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 0x4C, 0x4D
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 0x4E, 0x4F
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]


class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_short), ("wParamH", ctypes.c_ushort)]


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]


class InputI(ctypes.Union):
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", InputI)]


_DESKTOP = _user32.GetDesktopWindow()
_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


def _send(input_type: int, union: InputI):
    _user32.SendInput(1, ctypes.byref(Input(input_type, union)), ctypes.sizeof(Input))


def _key(scan: int, up: bool):
    ii = InputI()
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    ii.ki = KeyBdInput(0, scan, flags, 0, ctypes.pointer(ctypes.c_ulong(0)))
    _send(INPUT_KEYBOARD, ii)


def _mouse(dx: int, dy: int, flags: int):
    ii = InputI()
    ii.mi = MouseInput(dx, dy, 0, flags, 0, ctypes.pointer(ctypes.c_ulong(0)))
    _send(INPUT_MOUSE, ii)


def _get_class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def find_roblox_hwnd():
    result = []

    def _cb(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        n = _user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            _user32.GetWindowTextW(hwnd, buf, n + 1)
            if "Roblox" in buf.value:
                # Prefer the actual game client over e.g. a browser tab titled "Roblox".
                if _get_class_name(hwnd) == "WINDOWSCLIENT":
                    result.insert(0, hwnd)
                else:
                    result.append(hwnd)
        return True

    _user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    return result[0] if result else None


def _focus_window(hwnd):
    ALT = 0x38
    _key(ALT, up=False)
    try:
        _user32.SetForegroundWindow(hwnd)
    finally:
        _key(ALT, up=True)


ABORT = threading.Event()  # set by Stop / failsafe; checked between every click step


class Aborted(Exception):
    """Raised when Stop is pressed or the mouse is pushed into a screen corner."""


def mouse_in_corner(margin: int = 3) -> bool:
    pt = ctypes.wintypes.POINT()
    if not _user32.GetCursorPos(ctypes.byref(pt)):
        return False
    xo = _user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    yo = _user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    xe = xo + _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) - 1
    ye = yo + _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) - 1
    pw, ph = _user32.GetSystemMetrics(0) - 1, _user32.GetSystemMetrics(1) - 1  # primary monitor
    corners = {(xo, yo), (xe, yo), (xo, ye), (xe, ye), (0, 0), (pw, 0), (0, ph), (pw, ph)}
    return any(abs(pt.x - cx) <= margin and abs(pt.y - cy) <= margin for cx, cy in corners)


def check_abort():
    if ABORT.is_set():
        raise Aborted("Stopped.")
    if mouse_in_corner():
        ABORT.set()
        raise Aborted("Mouse moved to a screen corner.")


def _wait(secs: float):
    """Sleep that reacts to Stop / the corner failsafe within 50 ms."""
    end = time.time() + secs
    while True:
        check_abort()
        left = end - time.time()
        if left <= 0:
            return
        time.sleep(min(0.05, left))


def _move_to(x: int, y: int):
    xo = _user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    yo = _user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = max(1, _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) - 1)
    vh = max(1, _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) - 1)
    nx = round((x - xo) * 65535 / vw)
    ny = round((y - yo) * 65535 / vh)
    _mouse(nx, ny, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK)


def _left_click():
    _mouse(0, 0, MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.02)
    _mouse(0, 0, MOUSEEVENTF_LEFTUP)


def _click_in_window(hwnd, x, y, settle_ms, pause_ms, log):
    check_abort()
    _focus_window(hwnd)
    is_roblox = _get_class_name(hwnd) == "WINDOWSCLIENT"
    if is_roblox:
        _wait(settle_ms / 1000)
        _move_to(x + 1, y)
        log("  [click] waking DirectInput")
        _wait(0.1)
        _focus_window(_DESKTOP)
        _wait(0.1)
    _move_to(x, y)
    _wait(pause_ms / 1000)
    if is_roblox:
        _left_click()
        _wait(0.05)
    check_abort()
    _left_click()


def click_xy(x: int, y: int, log=print) -> bool:
    c = CFG.get("click")
    settle_ms, pause_ms, attempts = int(c["settle_ms"]), int(c["pause_ms"]), max(1, int(c["attempts"]))
    hwnd = find_roblox_hwnd()
    if not hwnd:
        log("  [click] Roblox window not found — clicking blind")
    for attempt in range(1, attempts + 1):
        try:
            if attempt > 1:
                log(f"  [click] retry {attempt}/{attempts}")
            check_abort()
            if hwnd:
                _click_in_window(hwnd, x, y, settle_ms, pause_ms, log)
            else:
                _move_to(x, y)
                _wait(pause_ms / 1000)
                check_abort()
                _left_click()
            return True
        except Aborted:
            raise
        except Exception as e:
            log(f"  [click] attempt {attempt} error: {e}")
            _wait(0.3 * attempt)
    log(f"  [click] all attempts failed for ({x},{y})")
    return False


def click_spawn(log=print):
    spot = CFG.get("click_spots", "spawn")
    if not spot:
        log("Spawn click not set — skipping")
        return
    log("Clicking spawn button")
    click_xy(spot[0], spot[1], log)
    _wait(0.4)


def click_forecast(log=print):
    spot = CFG.get("click_spots", "forecast")
    if spot:
        x, y = spot
    else:
        w, h = pyautogui.size()
        x, y = int(FORECAST_REL_X * w), int(FORECAST_REL_Y * h)
        log(f"  Forecast position not set — guessing ({x}, {y}). Set it on the Calibration page!")
    log("Clicking Forecast button")
    click_xy(x, y, log)
    _wait(0.5)


# ═══════════════════════════════════════════════════════
#  LINK / PROTOCOL
# ═══════════════════════════════════════════════════════
def parse_url(url: str) -> tuple[str, str]:
    url = (url or "").strip()
    if not url:
        raise ValueError("Link is empty.")
    p = urlparse(url)
    host = (p.netloc or "").lower()
    if not (host == "roblox.com" or host.endswith(".roblox.com")):
        raise ValueError("Not a roblox.com link.")
    parts = [x for x in p.path.split("/") if x]
    q = parse_qs(p.query)
    if parts[:1] == ["share"]:  # new style: roblox.com/share?code=...&type=Server
        code = (q.get("code") or [""])[0]
        if not code:
            raise ValueError("Share link is missing its code.")
        if (q.get("type") or ["Server"])[0].lower() != "server":
            raise ValueError("That share link isn't a private server link.")
        return "share", code
    if len(parts) < 2 or parts[0] != "games":
        raise ValueError("Path must be /games/<id>/...")
    pid = parts[1]
    if not pid.isdigit():
        raise ValueError("Could not read place ID from URL.")
    codes = parse_qs(p.query).get("privateServerLinkCode", [])
    if not codes:
        raise ValueError("Missing privateServerLinkCode in URL.")
    return pid, codes[0]


def build_proto(pid: str, lc: str) -> str:
    if pid == "share":
        return f"roblox://navigation/share_links?code={lc}&type=Server"
    return f"roblox://placeId={pid}&linkCode={lc}"


# ═══════════════════════════════════════════════════════
#  OCR
# ═══════════════════════════════════════════════════════
def screenshot() -> Image.Image:
    with mss.mss() as s:
        mon = s.monitors[0]  # the whole virtual desktop, so any monitor works
        shot = s.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        img.info["origin"] = (mon["left"], mon["top"])
        return img


def png_bytes(img: Image.Image) -> bytes:
    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def crop(img: Image.Image, tl, br) -> Image.Image:
    W, H = img.size
    ox, oy = img.info.get("origin", (0, 0))  # screen coords -> image coords
    tl, br = (tl[0] - ox, tl[1] - oy), (br[0] - ox, br[1] - oy)
    l, r = sorted((max(0, min(tl[0], W)), max(0, min(br[0], W))))
    t, b = sorted((max(0, min(tl[1], H)), max(0, min(br[1], H))))
    if r - l < 2 or b - t < 2:
        raise ValueError("Region is too small — recalibrate it.")
    return img.crop((l, t, r, b))


def region(name: str):
    r = CFG.get(name)
    if not r or not r.get("tl") or not r.get("br"):
        raise ValueError(f"{name.capitalize()} region not set (Calibration tab).")
    return r["tl"], r["br"]


def preprocess(img: Image.Image) -> Image.Image:
    o = CFG.get("ocr")
    thr, con = int(o["threshold"]), float(o["contrast"])
    g = ImageEnhance.Contrast(ImageOps.autocontrast(img.convert("L"))).enhance(con)
    bw = ImageOps.invert(g).point(lambda p: 255 if p > thr else 0)
    return bw.resize((bw.width * 2, bw.height * 2), Image.Resampling.NEAREST)


def ocr_text(img: Image.Image) -> str:
    raw = pytesseract.image_to_string(preprocess(img), config="--oem 3 --psm 6")
    lines = (re.sub(r"\s+", " ", ln).strip() for ln in raw.replace("\r", "\n").split("\n"))
    return "\n".join(ln for ln in lines if ln)


_WANTED = FILTER_FIELDS + ["Day"]
_LBL_RX = re.compile(r"^(?P<lbl>" + "|".join(re.escape(x) for x in _WANTED) + r")\s*[:;]\s*(?P<val>.+)$", re.I)
_LBL_MAP = {w.lower(): w for w in _WANTED}


def parse_vals(text: str) -> dict:
    out = {}
    for line in text.split("\n"):
        m = _LBL_RX.match(line.strip())
        if m:
            out[_LBL_MAP[m.group("lbl").lower()]] = m.group("val").strip()
    return out


def read_panel(img: Image.Image | None = None) -> tuple[dict, str, Image.Image]:
    tl, br = region("panel")
    img = img or screenshot()
    txt = ocr_text(crop(img, tl, br))
    return parse_vals(txt), txt, img


# ═══════════════════════════════════════════════════════
#  FILTERING
# ═══════════════════════════════════════════════════════
def norm_risk(s) -> str:
    if not s:
        return ""
    s = str(s).strip().upper()
    for bad, good in [("SLOT", "SLGT"), ("SLG T", "SLGT"), ("SLG1", "SLGT"),
                      ("MARG", "MRGL"), ("MRG", "MRGL"), ("MRGLL", "MRGL"), ("ENHANCED", "ENH")]:
        s = s.replace(bad, good)
    for r in RISK_ORDER:  # tolerate trailing junk, e.g. "SLGT." or "ENH 1"
        if s.startswith(r):
            return r
    return s


def extract_num(s):
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(s).replace(",", ""))
    return float(m.group(0)) if m else None


def cmp(op: str, a, b) -> bool:
    return a >= b if op == ">=" else a <= b


def risk_cmp(op: str, actual, target) -> bool:
    a, t = norm_risk(actual), norm_risk(target)
    if a not in RISK_ORDER or t not in RISK_ORDER:
        return False
    return cmp(op, RISK_ORDER.index(a), RISK_ORDER.index(t))


def apply_filters(values: dict, filters: dict) -> tuple[bool, list[str]]:
    solo, combined_fail, any_combined = [], [], False
    for key in FILTER_FIELDS:
        f = filters.get(key, {})
        if not f.get("enabled"):
            continue
        op = str(f.get("op", ">=")).strip()
        if key == "Risk":
            tgt, act = str(f.get("value", "SLGT")).upper(), values.get("Risk", "")
            ok = risk_cmp(op, act, tgt)
            why = f"Risk: '{act}' {op} '{tgt}' — no match"
        else:
            try:
                tgt = float(f.get("value", 0.0))
            except (TypeError, ValueError):
                ok, why = False, f"{key}: invalid target"
            else:
                act = values.get(key, "")
                num = extract_num(act)
                if num is None:
                    ok, why = False, f"{key}: could not read '{act}'"
                else:
                    ok, why = cmp(op, num, tgt), f"{key}: {num:g} {op} {tgt:g} — no match"
        if f.get("independent"):
            solo.append((key, ok, why))
        else:
            any_combined = True
            if not ok:
                combined_fail.append(why)

    if not solo:
        return (any_combined and not combined_fail), combined_fail
    reasons = [f"[solo] {k}: {'pass' if ok else r}" for k, ok, r in solo] + combined_fail
    passed = any(ok for _, ok, _ in solo) or (any_combined and not combined_fail)
    return passed, reasons


def check_records(values: dict, records: list) -> list[str]:
    hits = []
    for rec in records:
        if not rec.get("enabled"):
            continue
        field, op, name = rec.get("field", ""), rec.get("op", ">="), rec.get("name") or rec.get("field", "?")
        if field == "Risk":
            if risk_cmp(op, values.get("Risk", ""), rec.get("value", "")):
                hits.append(name)
            continue
        try:
            tgt = float(rec.get("value", 0.0))
        except (TypeError, ValueError):
            continue
        num = extract_num(values.get(field, ""))
        if num is not None and cmp(op, num, tgt):
            hits.append(name)
    return hits


# ═══════════════════════════════════════════════════════
#  WEBHOOK
# ═══════════════════════════════════════════════════════
_http = requests.Session()
_http.headers["User-Agent"] = f"TwisterXAutoRoller/{VERSION}"


def send_webhook(url: str, title: str, vals: dict, image: bytes | None,
                 server_link: str = "", color: int = 0x00B0F4, filename: str = "thermos.png",
                 ping: bool = True):
    if not url.strip():
        raise ValueError("Webhook URL is empty.")
    embed = {
        "title": title, "color": color,
        "fields": [{"name": k, "value": str(vals[k]), "inline": True} for k in DISPLAY_FIELDS if k in vals],
        "footer": {"text": f"TwisterX Auto Roller v{VERSION}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if server_link:
        embed["description"] = f"[Join Server]({server_link})"
    if image:
        embed["image"] = {"url": f"attachment://{filename}"}
    st = CFG.get("settings", default={}) or {}
    role_id = str(st.get("role_id") or ROLE_ID).strip()
    if ping and st.get("ping_role", True) and role_id.isdigit():
        payload = {"content": f"<@&{role_id}>", "embeds": [embed],
                   "allowed_mentions": {"roles": [role_id]}}
    else:
        payload = {"embeds": [embed], "allowed_mentions": {"parse": []}}

    for attempt in range(3):  # retry on Discord rate limit / transient errors
        if image:
            r = _http.post(url, data={"payload_json": json.dumps(payload)},
                           files={"file": (filename, image, "image/png")}, timeout=30)
        else:
            r = _http.post(url, json=payload, timeout=20)
        if r.status_code == 429:
            try:
                wait = float(r.json().get("retry_after", 1.0))
            except Exception:
                wait = 1.0
            time.sleep(min(wait, 10))
            continue
        if r.status_code >= 500 and attempt < 2:
            time.sleep(1 + attempt)
            continue
        r.raise_for_status()
        return
    r.raise_for_status()


# ═══════════════════════════════════════════════════════
#  SYSTEM TRAY
# ═══════════════════════════════════════════════════════
def make_icon_image(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 64
    d.ellipse([2 * s, 2 * s, 62 * s, 62 * s], fill=C["bg"], outline=C["accent"], width=max(1, int(3 * s)))
    # tornado: stacked swirl bands that narrow and drift toward the bottom
    bands = 7
    for i in range(bands):
        t = i / (bands - 1)
        half_w = (21 - 16 * t) * s
        cx = (32 + 5 * t * t) * s
        cy = (14 + 34 * t) * s
        h = max(2.0, (4.2 - 1.6 * t) * s)
        d.ellipse([cx - half_w, cy - h, cx + half_w, cy + h],
                  outline=C["accent_hi"] if i % 2 == 0 else C["accent"], width=max(1, int(2.6 * s)))
    return img


class Tray:
    def __init__(self, app: "App"):
        self.app = app
        self.icon = None
        if not HAVE_TRAY:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Show window", lambda *_: app.call(app.show_window), default=True),
            pystray.MenuItem("Stop loop", lambda *_: app.call(app.stop_all)),
            pystray.MenuItem("Quit", lambda *_: app.call(app.quit_app)),
        )
        self.icon = pystray.Icon("twisterx", make_icon_image(), APP_NAME, menu)
        self.icon.run_detached()

    def notify(self, msg: str):
        if self.icon:
            try:
                self.icon.notify(msg, APP_NAME)
            except Exception:
                pass

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════
#  STYLE (customtkinter)
# ═══════════════════════════════════════════════════════
# (light, dark) colour pairs — customtkinter picks one based on the appearance mode.
BG = ("#eef0f3", "#111316")
SIDEBAR = ("#e3e6ea", "#17191d")
CARD = ("#ffffff", "#1c1f24")
TILE = ("#f3f4f6", "#24282e")
ENTRY_BG = ("#f7f8fa", "#15171b")
BORDER = ("#d9dce1", "#2b2f36")
TEXT = ("#1d2128", "#e1e4e8")
MUTED = ("#6b7280", "#8b929e")
OK = ("#16824a", "#4cd387")
ERR = ("#c0392b", "#ff6b6b")
WARN = ("#a86b0c", "#e5c07b")
OK_BG = ("#e6f6ec", "#14271c")
NAV_SEL = ("#d0d5dc", "#262a31")

THEMES = ["blue", "green", "dark-blue"]
APPEARANCES = ["Dark", "Light", "System"]
SCALE_MIN, SCALE_MAX = 80, 150


def accent():
    """Accent (button) colour pair of the active colour theme."""
    try:
        return tuple(ctk.ThemeManager.theme["CTkButton"]["fg_color"])
    except Exception:
        return ("#3a7ebf", "#1f538d")


def accent_hover():
    try:
        return tuple(ctk.ThemeManager.theme["CTkButton"]["hover_color"])
    except Exception:
        return ("#325882", "#14375e")


def pick(pair):
    """Resolve a (light, dark) pair for plain-Tk widgets / text tags."""
    return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]


def setting(key):
    s = CFG.get("settings", default={}) or {}
    return s.get(key, default_settings()[key])


def play_pass_sound():
    if not setting("sound_on_pass"):
        return
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


def F(size=13, weight="normal", mono=False):
    return ctk.CTkFont(family=MONO if mono else FONT, size=size, weight=weight)


# ═══════════════════════════════════════════════════════
#  DIALOGS
# ═══════════════════════════════════════════════════════
class PassDialog(ctk.CTkToplevel):
    """Modal shown when requirements pass. result=True → keep rerolling."""

    def __init__(self, parent, vals: dict):
        super().__init__(parent)
        self.result = False
        self.title("Requirements met")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.attributes("-topmost", True)
        self.transient(parent)

        card = ctk.CTkFrame(self, fg_color=OK_BG, corner_radius=14, border_width=1, border_color=OK)
        card.pack(padx=20, pady=20, fill="both")
        ctk.CTkLabel(card, text="✔  Requirements met", font=F(20, "bold"), text_color=OK) \
            .pack(pady=(20, 2), padx=34)
        ctk.CTkLabel(card, text="All enabled conditions passed. What next?", font=F(12),
                     text_color=MUTED).pack(pady=(0, 12))

        box = ctk.CTkFrame(card, fg_color=CARD, corner_radius=10)
        box.pack(padx=22, fill="x")
        for i, k in enumerate(k for k in DISPLAY_FIELDS if k in vals):
            ctk.CTkLabel(box, text=k, font=F(12), text_color=MUTED, anchor="w") \
                .grid(row=i, column=0, sticky="w", padx=(14, 18), pady=1)
            ctk.CTkLabel(box, text=str(vals[k]), font=F(12, "bold", mono=True), text_color=OK, anchor="w") \
                .grid(row=i, column=1, sticky="w", padx=(0, 14), pady=1)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(pady=18)
        ctk.CTkButton(row, text="Continue rerolling", fg_color=TILE, text_color=TEXT, hover_color=BORDER,
                      command=self._continue).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Stop here", fg_color=OK, hover_color=("#11673a", "#3cb672"),
                      text_color=("#ffffff", "#0b1f13"), command=self._stop).pack(side="left", padx=6)
        self.bind("<Escape>", lambda e: self._stop())
        self.bind("<Return>", lambda e: self._stop())
        self.protocol("WM_DELETE_WINDOW", self._stop)

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{(self.winfo_screenwidth() - w) // 2}+{(self.winfo_screenheight() - h) // 2}")
        if setting("sound_on_pass"):
            self.bell()
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass

    def _continue(self):
        self.result = True
        self.destroy()

    def _stop(self):
        self.result = False
        self.destroy()


class ClickCapture:
    """Full-screen translucent overlay; reports the clicked screen position."""

    def __init__(self, root, label: str, on_pick, on_cancel):
        ov = tk.Toplevel(root)
        ov.overrideredirect(True)
        vx, vy = _user32.GetSystemMetrics(SM_XVIRTUALSCREEN), _user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw, vh = _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN), _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        ov.geometry(f"{vw}x{vh}+{vx}+{vy}")
        ov.attributes("-alpha", 0.35, "-topmost", True)
        ov.configure(bg="black", cursor="crosshair")
        tk.Label(ov, text=f"{label}\n\nClick to set the position  •  Esc to cancel",
                 font=(FONT, 20, "bold"), bg="#111111", fg=C["warn"], padx=36, pady=24,
                 justify="center").place(relx=.5, rely=.5, anchor="center")

        def on_click(e):
            ov.destroy()
            on_pick(e.x_root, e.y_root)

        def cancel(_=None):
            ov.destroy()
            on_cancel()

        ov.bind("<Button-1>", on_click)
        ov.bind("<Escape>", cancel)
        ov.bind("<Button-3>", cancel)
        ov.focus_force()



# ═══════════════════════════════════════════════════════
#  GUIDED TOUR (first launch)
# ═══════════════════════════════════════════════════════
# (page, target key in App.T or None, title, text)
TOUR_STEPS = [
    ("run", None, "Welcome to TwisterX Auto Roller 👋",
     "This quick tour walks you through the app step by step. Each step highlights the part "
     "of the window you need.\n\nUse Next / Back (or the arrow keys). Skip ends the tour. "
     "You can replay it any time from Settings."),
    ("run", "sidebar", "Navigation",
     "These are the five pages. Set things up from top to bottom: Run → Calibration → "
     "Requirements → Records. Settings is for preferences."),
    ("run", "connection", "Step 1 — Connect",
     "Paste your Roblox private server link (either the …privateServerLinkCode=… link or a "
     "roblox.com/share?code=… link) and press Save.\n\nOptional: paste a Discord webhook URL, "
     "press Save, then Test to check it works."),
    ("run", "timing", "Load wait & Interval",
     "Load wait: how long the game needs to load before clicking (raise it on a slow PC).\n"
     "Interval: the pause before each reroll / next run (minimum 2 s)."),
    ("run", "buttons", "Run controls",
     "▶ Join now does one run.  ⟳ Start auto keeps going.  ■ Stop (or Esc) stops everything.\n"
     "Read OCR now is a test read: no joining, no clicks, no webhooks.\n\n"
     "Emergency stop: push the mouse into any screen corner."),
    ("run", "switches", "Run options",
     "Click in-game buttons: click Spawn and Forecast after loading.\n"
     "Auto-reroll on fail: rejoin automatically when requirements fail.\n"
     "Popup on pass: pause and ask you what to do. Turn it off for record hunting."),
    ("run", "tiles", "Session stats",
     "Live counters for this session: scans, passes, record hits and uptime."),
    ("run", "lastscan", "Last scan",
     "The values read from the screen, with a green PASSED or red Not passed badge."),
    ("run", "log", "Log",
     "Everything the app does shows up here. If something goes wrong, read the last few "
     "lines first. The buttons open the data folder, config.json and data.txt."),
    ("calib", "nav_calib", "Step 2 — Calibration",
     "Next, tell the app where to click and what to read. Join your game once by hand "
     "first so the buttons and the forecast panel are on screen."),
    ("calib", "spots", "Click positions",
     "Press Set, then click the in-game button on your screen. Forecast is required; "
     "Spawn only if your game shows a menu first. Test clicks it once to check."),
    ("calib", "region_panel", "OCR text panel",
     "Set the top-left and bottom-right corners around the forecast text "
     "(Risk, CAPE, …). Preview shows exactly what the text reader sees."),
    ("calib", "region_thermos", "Thermos screenshot",
     "The area that gets attached as an image to the Discord message when you pass."),
    ("calib", "ocrimg", "OCR image tuning",
     "If Preview looks messy, move Threshold and Contrast until the text is crisp black on "
     "white, then Save. Test OCR now checks the result."),
    ("calib", "clicktiming", "Click timing",
     "Only touch these if clicks don't register: raise Settle and Pause a little."),
    ("req", "nav_req", "Step 3 — Requirements",
     "Now decide what counts as a good server."),
    ("req", "conditions", "Conditions",
     "Switch a row on, choose >= or <= and type a value.\n"
     "Normal rows must ALL pass. Tick Solo on a row to make it pass on its own."),
    ("req", "req_save", "Save requirements",
     "Always press Save requirements after editing. Revert undoes unsaved changes."),
    ("records", "records", "Step 4 — Record hunt (optional)",
     "Values you're trying to beat. A hit sends a full screenshot to Discord and never "
     "stops the loop. Add a record, fill it in, then Save records."),
    ("settings", "appearance", "Settings",
     "Light/dark mode, accent colour and size. Below: tray behaviour, sounds, "
     "Discord role ping and data limits."),
    ("settings", "replay", "Replay this tour",
     "Need a refresher? This button starts the tour again."),
    ("run", "buttons", "You're ready! 🎉",
     "Save your link, calibrate, set requirements, then press ▶ Join now for a test run "
     "or ⟳ Start auto to let it roll. Good luck!"),
]

_KEY = "#010203"  # colour made fully transparent in the overlay windows


class Tour:
    """Spotlight walkthrough: dims the window, rings the target widget and explains it."""

    PAD = 8

    def __init__(self, app: "App", on_finish):
        self.app, self.root, self.on_finish = app, app.root, on_finish
        self.i = 0
        self._pulse = 0
        self._after = None
        self._cfg_after = None

        # Layer 1: dim with a transparent hole (clicks pass through the hole).
        self.dim = tk.Toplevel(self.root)
        self.dim.overrideredirect(True)
        self.dim.attributes("-alpha", 0.6, "-transparentcolor", _KEY)
        self.dim_cv = tk.Canvas(self.dim, bg="black", highlightthickness=0, bd=0)
        self.dim_cv.pack(fill="both", expand=True)

        # Layer 2: ring, arrow and the step card.
        self.top = tk.Toplevel(self.root)
        self.top.overrideredirect(True)
        self.top.attributes("-transparentcolor", _KEY)
        self.cv = tk.Canvas(self.top, bg=_KEY, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)

        self.card = ctk.CTkFrame(self.cv, fg_color=CARD, corner_radius=14, border_width=2,
                                 border_color=accent(), bg_color=_KEY, width=380)
        head = ctk.CTkFrame(self.card, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(14, 0))
        self.step_lbl = ctk.CTkLabel(head, text="", font=F(11, "bold"), text_color=accent(), anchor="w")
        self.step_lbl.pack(side="left")
        ctk.CTkButton(head, text="Skip tour", width=70, height=24, font=F(11), fg_color="transparent",
                      hover_color=TILE, text_color=MUTED, command=self.finish).pack(side="right")
        self.title_lbl = ctk.CTkLabel(self.card, text="", font=F(17, "bold"), text_color=TEXT,
                                      anchor="w", justify="left", wraplength=340)
        self.title_lbl.pack(fill="x", padx=18, pady=(4, 2))
        self.body_lbl = ctk.CTkLabel(self.card, text="", font=F(12), text_color=TEXT, anchor="w",
                                     justify="left", wraplength=340)
        self.body_lbl.pack(fill="x", padx=18)
        self.dots = ctk.CTkLabel(self.card, text="", font=F(9), text_color=MUTED)
        self.dots.pack(fill="x", padx=18, pady=(10, 0))
        btns = ctk.CTkFrame(self.card, fg_color="transparent")
        btns.pack(fill="x", padx=18, pady=(8, 16))
        self.back_btn = ctk.CTkButton(btns, text="← Back", width=90, height=32, font=F(12),
                                      fg_color=TILE, hover_color=BORDER, text_color=TEXT, command=self.back)
        self.back_btn.pack(side="left")
        self.next_btn = ctk.CTkButton(btns, text="Next →", width=110, height=32, font=F(12, "bold"),
                                      command=self.next)
        self.next_btn.pack(side="right")
        self.card_win = self.cv.create_window(0, 0, window=self.card, anchor="nw")

        for w in (self.top, self.dim):
            w.bind("<Right>", lambda e: self.next())
            w.bind("<Return>", lambda e: self.next())
            w.bind("<Left>", lambda e: self.back())
            w.bind("<Escape>", lambda e: self.finish())
        self._root_bind = self.root.bind("<Configure>", self._on_root_configure, add="+")
        self.show()
        self._animate()

    # ── navigation ─────────────────────────────────────
    def next(self):
        if self.i >= len(TOUR_STEPS) - 1:
            self.finish()
        else:
            self.i += 1
            self.show()

    def back(self):
        if self.i > 0:
            self.i -= 1
            self.show()

    def finish(self):
        for a in (self._after, self._cfg_after):
            if a:
                try:
                    self.root.after_cancel(a)
                except Exception:
                    pass
        try:
            self.root.unbind("<Configure>", self._root_bind)
        except Exception:
            pass
        for w in (self.top, self.dim):
            try:
                w.destroy()
            except Exception:
                pass
        self.app.show_page("run")
        self.on_finish()

    # ── drawing ────────────────────────────────────────
    def _on_root_configure(self, e):
        if e.widget is not self.root or self.root.state() not in ("normal", "zoomed"):
            return
        if self._cfg_after:
            self.root.after_cancel(self._cfg_after)
        self._cfg_after = self.root.after(120, self.show)

    def _scroll_into_view(self, page, w):
        canvas = getattr(page, "_parent_canvas", None)
        if canvas is None:
            return
        page.update_idletasks()
        total = max(1, page.winfo_height())
        y = w.winfo_rooty() - page.winfo_rooty()
        canvas.yview_moveto(max(0.0, (y - 40) / total))
        self.root.update_idletasks()

    def show(self):
        self._cfg_after = None
        if not self.top.winfo_exists():
            return
        page, key, title, body = TOUR_STEPS[self.i]
        if self.root.state() not in ("normal", "zoomed"):
            for w in (self.dim, self.top):  # window hidden/minimized: hide the overlay too
                w.withdraw()
            return
        for w in (self.dim, self.top):
            if w.state() == "withdrawn":
                w.deiconify()
        self.app.show_page(page)
        self.root.update_idletasks()
        target = self.app.T.get(key) if key else None
        if target is not None:
            self._scroll_into_view(self.app.pages[page], target)

        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        geo = f"{rw}x{rh}+{rx}+{ry}"
        for w in (self.dim, self.top):
            w.geometry(geo)
            w.update_idletasks()
            if (w.winfo_rootx(), w.winfo_rooty()) != (rx, ry):
                w.wm_geometry(geo)  # overrideredirect windows sometimes ignore the first move
                w.update()
            w.lift()
        self.top.focus_force()

        n = len(TOUR_STEPS)
        self.step_lbl.configure(text=f"STEP {self.i + 1} OF {n}")
        self.title_lbl.configure(text=title)
        self.body_lbl.configure(text=body)
        self.dots.configure(text="  ".join("●" if j == self.i else "○" for j in range(n)))
        self.back_btn.configure(state="normal" if self.i else "disabled")
        self.next_btn.configure(text="Finish ✓" if self.i == n - 1 else "Next →")

        self.dim_cv.delete("all")
        self.cv.delete("ring", "arrow")
        self.top.update_idletasks()
        cw, ch = self.card.winfo_reqwidth(), self.card.winfo_reqheight()

        if target is None:
            self.hole = None
            self.cv.coords(self.card_win, (rw - cw) // 2, (rh - ch) // 2)
            return

        P = self.PAD
        x1 = target.winfo_rootx() - rx - P
        y1 = target.winfo_rooty() - ry - P
        x2 = x1 + target.winfo_width() + 2 * P
        y2 = y1 + target.winfo_height() + 2 * P
        # keep the highlight inside the window
        x1, y1 = max(4, x1), max(4, y1)
        x2, y2 = min(rw - 4, x2), min(rh - 4, y2)
        small = (x2 - x1) < 260 and (y2 - y1) < 120
        self.hole = (x1, y1, x2, y2, small)

        if small:  # circle small things
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            rx_, ry_ = (x2 - x1) / 2 * 1.35, (y2 - y1) / 2 * 1.6
            self.dim_cv.create_oval(cx - rx_, cy - ry_, cx + rx_, cy + ry_, fill=_KEY, outline=_KEY)
        else:
            self._round_rect(self.dim_cv, x1, y1, x2, y2, 14, fill=_KEY, outline=_KEY)
        self._draw_ring()

        # place the card next to the target: right, below, above, left — whichever fits
        gap = 28
        options = [
            (x2 + gap, max(12, min((y1 + y2) // 2 - ch // 2, rh - ch - 12))),
            (max(12, min((x1 + x2) // 2 - cw // 2, rw - cw - 12)), y2 + gap),
            (max(12, min((x1 + x2) // 2 - cw // 2, rw - cw - 12)), y1 - gap - ch),
            (x1 - gap - cw, max(12, min((y1 + y2) // 2 - ch // 2, rh - ch - 12))),
        ]
        cx_, cy_ = next(((x, y) for x, y in options
                         if x >= 8 and y >= 8 and x + cw <= rw - 8 and y + ch <= rh - 8),
                        (rw - cw - 16, rh - ch - 16))
        self.cv.coords(self.card_win, cx_, cy_)

        # arrow from the card to the highlight
        ax = min(max(cx_ + cw / 2, x1), x2)
        ay = min(max(cy_ + ch / 2, y1), y2)
        sx = min(max(ax, cx_), cx_ + cw)
        sy = min(max(ay, cy_), cy_ + ch)
        if abs(sx - ax) + abs(sy - ay) > 30:
            self.cv.create_line(sx, sy, ax, ay, fill=accent()[0], width=3, arrow="last",
                                arrowshape=(14, 16, 6), smooth=True, tags="arrow")

    def _draw_ring(self):
        self.cv.delete("ring")
        if not getattr(self, "hole", None):
            return
        x1, y1, x2, y2, small = self.hole
        col = accent()[0]
        width = 3 + (self._pulse % 6 if self._pulse % 12 < 6 else 6 - self._pulse % 6) * 0.6
        if small:
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            rx_, ry_ = (x2 - x1) / 2 * 1.35, (y2 - y1) / 2 * 1.6
            for k, wd in ((6, 1), (0, width)):
                self.cv.create_oval(cx - rx_ - k, cy - ry_ - k, cx + rx_ + k, cy + ry_ + k,
                                    outline=col, width=wd, tags="ring")
        else:
            for k, wd in ((6, 1), (0, width)):
                self._round_rect(self.cv, x1 - k, y1 - k, x2 + k, y2 + k, 14 + k,
                                 outline=col, width=wd, fill="", tags="ring")
        self.cv.tag_lower("ring")

    def _animate(self):
        if not self.top.winfo_exists():
            return
        self._pulse += 1
        self._draw_ring()
        self._after = self.root.after(90, self._animate)

    @staticmethod
    def _round_rect(cv, x1, y1, x2, y2, r, **kw):
        r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(pts, smooth=True, **kw)

# ═══════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════
PAGES = [("run", "▶   Run"), ("calib", "⌖   Calibration"), ("req", "✓   Requirements"),
         ("records", "★   Records"), ("settings", "⚙   Settings")]


class App:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self._q: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.next_join_at: float | None = None
        self.reroll_after_id = None
        self.stats = {"scans": 0, "passes": 0, "records": 0}
        self.started_at = time.time()
        self.page = None

        root.title(f"{APP_NAME}  v{VERSION}")
        root.geometry("1200x820")
        root.minsize(1000, 660)
        root.configure(fg_color=BG)
        try:
            self._icon_img = tk.PhotoImage(data=png_bytes(make_icon_image(32)))
            root.iconphoto(True, self._icon_img)
        except Exception:
            pass
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.sv_status = tk.StringVar(value="Ready.")
        self.sv_auto = tk.StringVar(value="Auto: off")
        self.sv_result = tk.StringVar(value="No scan yet")

        self._build()
        self.apply_always_on_top()
        self.tray = Tray(self)
        self._pump()
        self._tick()

        self.log(f"{APP_NAME} v{VERSION} started. Files: {APP_DIR}")
        if not TESSERACT_PATH:
            self.log("Tesseract not found! Install it from https://github.com/UB-Mannheim/tesseract/wiki", "err")
        if not HAVE_TRAY:
            self.log("Tip: pip install pystray to enable the system tray icon.", "muted")
        self.tour = None
        if not CFG.get("tutorial", "done"):
            self.root.after(900, self.start_tour)

    # ── guided tour ─────────────────────────────────────
    def start_tour(self):
        if self.tour is not None:
            return
        self.root.deiconify()
        self.root.update_idletasks()

        def done():
            self.tour = None
            if not CFG.get("tutorial", "done"):
                CFG.set("tutorial", "done", True)
                self.log("Tutorial finished. Replay it any time from Settings.", "muted")
        self.tour = Tour(self, done)

    # ── thread-safe UI plumbing ─────────────────────────
    def call(self, fn, *args):
        """Run fn(*args) on the Tk thread. Safe from any thread."""
        self._q.put((fn, args))

    def _pump(self):
        try:
            while True:
                fn, args = self._q.get_nowait()
                try:
                    fn(*args)
                except Exception as e:
                    self._log_now(f"UI error: {e}", "err")
        except queue.Empty:
            pass
        self.root.after(40, self._pump)

    def log(self, msg: str, tag: str = ""):
        self.call(self._log_now, msg, tag)

    def _log_now(self, msg: str, tag: str = ""):
        ts = datetime.now().strftime("%H:%M:%S")
        t = self.log_text
        t.configure(state="normal")
        t.insert("end", f"{ts}  ", "ts")
        t.insert("end", msg + "\n", tag or ())
        limit = max(100, int(setting("log_limit")))
        lines = int(t.index("end-1c").split(".")[0])
        if lines > limit:
            t.delete("1.0", f"{lines - limit}.0")
        t.configure(state="disabled")
        t.see("end")
        if not msg.startswith("  "):
            self.sv_status.set(msg)

    def status(self, msg: str):
        self.log(msg)

    def notify(self, msg: str):
        if setting("notifications"):
            self.tray.notify(msg)

    def ask_pass(self, vals: dict) -> bool:
        """Block the worker until the user answers the pass dialog."""
        holder, done = [False], threading.Event()

        def show():
            dlg = PassDialog(self.root, vals)
            self.root.wait_window(dlg)
            holder[0] = dlg.result
            done.set()

        self.call(show)
        while not done.wait(0.2):
            if self.stop_event.is_set():
                break
        return holder[0]

    # ── widget helpers ──────────────────────────────────
    def _card(self, parent, title: str | None = None, subtitle: str | None = None):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
        body = ctk.CTkFrame(card, fg_color="transparent")
        if title:
            ctk.CTkLabel(card, text=title, font=F(15, "bold"), text_color=TEXT, anchor="w") \
                .pack(fill="x", padx=18, pady=(14, 0 if subtitle else 8))
        if subtitle:
            ctk.CTkLabel(card, text=subtitle, font=F(12), text_color=MUTED, anchor="w", justify="left",
                         wraplength=820).pack(fill="x", padx=18, pady=(0, 8))
        body.pack(fill="both", expand=True, padx=18, pady=(0 if title else 14, 16))
        return card, body

    @staticmethod
    def _entry(parent, var, width=140, mono=False, **kw):
        return ctk.CTkEntry(parent, textvariable=var, width=width, height=32, corner_radius=8,
                            fg_color=ENTRY_BG, border_color=BORDER, font=F(12, mono=mono), **kw)

    @staticmethod
    def _btn(parent, text, command, kind="normal", width=None, **kw):
        style = {
            "normal": dict(fg_color=TILE, hover_color=BORDER, text_color=TEXT, border_width=1, border_color=BORDER),
            "accent": dict(font=F(13, "bold")),
            "danger": dict(fg_color=("#fde8e8", "#3a1f23"), hover_color=("#f9d0d0", "#4a272c"),
                           text_color=ERR, font=F(13, "bold")),
            "ghost": dict(fg_color="transparent", hover_color=TILE, text_color=MUTED),
        }[kind]
        if "font" not in style:
            style["font"] = F(12)
        style.setdefault("height", 34)
        style.update(kw)
        if width:
            style["width"] = width
        return ctk.CTkButton(parent, text=text, command=command, corner_radius=8, **style)

    @staticmethod
    def _muted(parent, text, wrap=0, size=12):
        return ctk.CTkLabel(parent, text=text, font=F(size), text_color=MUTED, anchor="w", justify="left",
                            wraplength=wrap)

    @staticmethod
    def _label(parent, text, size=13, **kw):
        return ctk.CTkLabel(parent, text=text, font=F(size), text_color=TEXT, anchor="w", **kw)

    @staticmethod
    def _switch(parent, text, var, command):
        return ctk.CTkSwitch(parent, text=text, variable=var, command=command, font=F(12), text_color=TEXT,
                             onvalue=True, offvalue=False)

    @staticmethod
    def _commit(entry, fn):
        entry.bind("<Return>", lambda e: fn())
        entry.bind("<FocusOut>", lambda e: fn())

    def _scroll_page(self, name) -> ctk.CTkScrollableFrame:
        page = ctk.CTkScrollableFrame(self.main, fg_color="transparent", corner_radius=0)
        self.pages[name] = page
        return page

    def _page_header(self, parent, title, subtitle):
        h = ctk.CTkFrame(parent, fg_color="transparent")
        h.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(h, text=title, font=F(24, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
        self._muted(h, subtitle).pack(fill="x")

    # ── build ───────────────────────────────────────────
    def _build(self):
        root = self.root
        self.T = {}  # widgets the guided tour can point at
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        # Sidebar
        sb = ctk.CTkFrame(root, width=210, corner_radius=0, fg_color=SIDEBAR)
        sb.grid(row=0, column=0, rowspan=2, sticky="nsw")
        sb.grid_propagate(False)
        sb.pack_propagate(False)
        self.T["sidebar"] = sb
        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.pack(fill="x", padx=18, pady=(22, 18))
        ctk.CTkLabel(logo, text="🌪  TwisterX", font=F(18, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
        self._muted(logo, f"Auto Roller  •  v{VERSION}", size=11).pack(fill="x")

        self.nav_btns = {}
        for key, label in PAGES:
            b = ctk.CTkButton(sb, text=label, anchor="w", height=40, corner_radius=10, font=F(13),
                              fg_color="transparent", hover_color=NAV_SEL, text_color=TEXT,
                              command=lambda k=key: self.show_page(k))
            b.pack(fill="x", padx=12, pady=2)
            self.nav_btns[key] = b
            self.T[f"nav_{key}"] = b

        foot = ctk.CTkFrame(sb, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=14, pady=16)
        self.auto_badge = ctk.CTkLabel(foot, textvariable=self.sv_auto, font=F(12, "bold"), corner_radius=8,
                                       fg_color=TILE, text_color=MUTED, height=30)
        self.auto_badge.pack(fill="x")
        self._muted(foot, "Esc = Stop   •   Enter = Join", size=11).pack(fill="x", pady=(8, 0))

        # Main area
        self.main = ctk.CTkFrame(root, fg_color="transparent", corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        bar = ctk.CTkFrame(root, fg_color=SIDEBAR, corner_radius=0, height=30)
        bar.grid(row=1, column=1, sticky="ew")
        ctk.CTkLabel(bar, textvariable=self.sv_status, font=F(12), text_color=TEXT, anchor="w") \
            .pack(side="left", fill="x", expand=True, padx=16)
        self._muted(bar, "Esc or mouse into a screen corner = stop", size=11).pack(side="right", padx=16)

        self.pages = {}
        self._build_run_page()
        self._build_calib_page()
        self._build_req_page()
        self._build_records_page()
        self._build_settings_page()
        self.show_page("run")

        root.bind("<Return>", lambda e: None if isinstance(e.widget, (tk.Entry, tk.Text)) else self.join_now())
        root.bind("<Escape>", lambda e: None if isinstance(e.widget, (tk.Entry, tk.Text)) else self.stop_all())

    def show_page(self, name):
        if self.page == name:
            return
        for k, p in self.pages.items():
            p.grid_forget()
        self.pages[name].grid(row=0, column=0, sticky="nsew", padx=22, pady=(18, 10))
        for k, b in self.nav_btns.items():
            sel = k == name
            b.configure(fg_color=NAV_SEL if sel else "transparent", text_color=accent() if sel else TEXT,
                        font=F(13, "bold" if sel else "normal"))
        self.page = name

    # ── Run page ────────────────────────────────────────
    def _build_run_page(self):
        page = ctk.CTkFrame(self.main, fg_color="transparent")
        self.pages["run"] = page
        page.grid_columnconfigure(0, weight=3, uniform="c")
        page.grid_columnconfigure(1, weight=2, uniform="c")
        page.grid_rowconfigure(2, weight=1)

        # Stat tiles
        tiles = ctk.CTkFrame(page, fg_color="transparent")
        tiles.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.T["tiles"] = tiles
        self.stat_vars = {}
        for i, (key, cap) in enumerate([("scans", "Scans"), ("passes", "Passes"),
                                        ("records", "Record hits"), ("uptime", "Uptime")]):
            tiles.grid_columnconfigure(i, weight=1, uniform="s")
            cell = ctk.CTkFrame(tiles, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
            cell.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            v = tk.StringVar(value="0")
            self.stat_vars[key] = v
            ctk.CTkLabel(cell, text=cap.upper(), font=F(11, "bold"), text_color=MUTED, anchor="w") \
                .pack(fill="x", padx=16, pady=(12, 0))
            ctk.CTkLabel(cell, textvariable=v, font=F(24, "bold"),
                         text_color=accent() if key != "uptime" else TEXT, anchor="w") \
                .pack(fill="x", padx=16, pady=(0, 12))

        left = ctk.CTkFrame(page, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        right = ctk.CTkFrame(page, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew")

        # Connection
        card, con = self._card(left, "Connection")
        card.pack(fill="x", pady=(0, 12))
        self.T["connection"] = card
        con.grid_columnconfigure(1, weight=1)
        self.sv_link = tk.StringVar(value=CFG.get("saved_link", default=""))
        self.sv_wh = tk.StringVar(value=CFG.get("webhook_url", default=""))
        self._label(con, "Server link", 12).grid(row=0, column=0, sticky="w", pady=4)
        self._entry(con, self.sv_link, mono=True, placeholder_text="https://www.roblox.com/games/…") \
            .grid(row=0, column=1, sticky="ew", padx=10)
        self._btn(con, "Save", self.save_link, width=64).grid(row=0, column=2, columnspan=2, sticky="w")
        self._label(con, "Webhook", 12).grid(row=1, column=0, sticky="w", pady=4)
        wh = self._entry(con, self.sv_wh, mono=True, show="•")
        wh.grid(row=1, column=1, sticky="ew", padx=10)
        self._btn(con, "Save", self.save_wh, width=64).grid(row=1, column=2)
        self._btn(con, "Test", self.test_webhook, width=64).grid(row=1, column=3, padx=(6, 0))
        wh.bind("<FocusIn>", lambda e: wh.configure(show=""))
        wh.bind("<FocusOut>", lambda e: wh.configure(show="•"))

        # Controls
        card, ctl = self._card(left, "Run")
        card.pack(fill="x")
        run = CFG.get("run")
        self.sv_lwait = tk.StringVar(value=str(run["load_wait"]))
        self.sv_interval = tk.StringVar(value=str(run["interval"]))
        self.sv_doseq = tk.BooleanVar(value=bool(run["click_sequence"]))
        r1 = ctk.CTkFrame(ctl, fg_color="transparent")
        r1.pack(fill="x")
        self.T["timing"] = r1
        self._label(r1, "Load wait", 12).pack(side="left")
        e = self._entry(r1, self.sv_lwait, width=60)
        e.pack(side="left", padx=(8, 4))
        self._commit(e, self._save_run)
        self._muted(r1, "s").pack(side="left", padx=(0, 18))
        self._label(r1, "Interval", 12).pack(side="left")
        e = self._entry(r1, self.sv_interval, width=60)
        e.pack(side="left", padx=(8, 4))
        self._commit(e, self._save_run)
        self._muted(r1, "s").pack(side="left")

        r2 = ctk.CTkFrame(ctl, fg_color="transparent")
        r2.pack(fill="x", pady=(14, 0))
        self.T["buttons"] = r2
        self._btn(r2, "▶  Join now", self.join_now, "accent", width=120).pack(side="left")
        self._btn(r2, "⟳  Start auto", self.start_auto, width=120).pack(side="left", padx=8)
        self._btn(r2, "■  Stop", self.stop_all, "danger", width=90).pack(side="left")
        self._btn(r2, "Read OCR now", self.read_now).pack(side="right")

        r3 = ctk.CTkFrame(ctl, fg_color="transparent")
        r3.pack(fill="x", pady=(16, 0))
        self.T["switches"] = r3
        self.sv_rr_en = tk.BooleanVar(value=bool(CFG.get("auto_reroll", "enabled")))
        self.sv_pass_dlg = tk.BooleanVar(value=bool(CFG.get("pass_dialog", "enabled")))
        for i, (txt, var, cmd) in enumerate([
                ("Click in-game buttons", self.sv_doseq, self._save_run),
                ("Auto-reroll on fail", self.sv_rr_en,
                 lambda: self._save_bool("auto_reroll", "enabled", self.sv_rr_en)),
                ("Popup on pass", self.sv_pass_dlg,
                 lambda: self._save_bool("pass_dialog", "enabled", self.sv_pass_dlg))]):
            self._switch(r3, txt, var, cmd).grid(row=0, column=i, sticky="w", padx=(0, 18))
        self._muted(ctl, "Turn the popup off when record hunting so the loop never stops on its own.") \
            .pack(fill="x", pady=(8, 0))

        # Last values
        card, vals = self._card(right, "Last scan")
        card.pack(fill="both", expand=True)
        self.T["lastscan"] = card
        self.result_lbl = ctk.CTkLabel(vals, textvariable=self.sv_result, font=F(14, "bold"), corner_radius=8,
                                       fg_color=TILE, text_color=MUTED, height=36)
        self.result_lbl.pack(fill="x", pady=(0, 10))
        grid = ctk.CTkFrame(vals, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure(1, weight=1)
        self.val_vars = {}
        for i, k in enumerate(DISPLAY_FIELDS + ["Day"]):
            self._muted(grid, k).grid(row=i, column=0, sticky="w", pady=0)
            v = tk.StringVar(value="—")
            self.val_vars[k] = v
            ctk.CTkLabel(grid, textvariable=v, font=F(12, "bold", mono=True), text_color=TEXT, anchor="e",
                         height=22).grid(row=i, column=1, sticky="e")

        # Log
        logc = ctk.CTkFrame(page, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
        logc.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        self.T["log"] = logc
        lh = ctk.CTkFrame(logc, fg_color="transparent")
        lh.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(lh, text="Log", font=F(15, "bold"), text_color=TEXT).pack(side="left")
        for txt, cmd in [("Open folder", self.open_folder), ("config.json", lambda: os.startfile(CFG_FILE)),
                         ("data.txt", self.open_data), ("Clear", self._clear_log)]:
            self._btn(lh, txt, cmd, "ghost", height=28).pack(side="right", padx=2)
        self.log_text = ctk.CTkTextbox(logc, height=140, corner_radius=10, fg_color=ENTRY_BG, text_color=TEXT,
                                       font=F(12, mono=True), wrap="word", border_width=0)
        self.log_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log_text.configure(state="disabled")
        self._apply_log_tags()

    def _apply_log_tags(self):
        for tag, col in [("ts", MUTED), ("ok", OK), ("err", ERR), ("warn", WARN), ("muted", MUTED)]:
            self.log_text.tag_config(tag, foreground=pick(col))

    # ── Calibration page ────────────────────────────────
    def _build_calib_page(self):
        page = self._scroll_page("calib")
        self._page_header(page, "Calibration", "Where to click and which screen areas to read.")
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x")
        for i in range(3):
            top.grid_columnconfigure(i, weight=1, uniform="cal")

        self.spot_vars = {}
        card, spots = self._card(top, "Click positions")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.T["spots"] = card
        for key, label in [("spawn", "Spawn / menu (1st)"), ("forecast", "Forecast (2nd)")]:
            self._label(spots, label, 12).pack(fill="x")
            v = tk.StringVar(value=self._fmt_pt(CFG.get("click_spots", key)))
            self.spot_vars[key] = v
            row = ctk.CTkFrame(spots, fg_color="transparent")
            row.pack(fill="x", pady=(2, 12))
            ctk.CTkLabel(row, textvariable=v, font=F(12, mono=True), text_color=accent(), width=96,
                         anchor="w").pack(side="left")
            self._btn(row, "Test", lambda k=key: self._run_bg(
                click_spawn if k == "spawn" else click_forecast, self.status), width=56).pack(side="right")
            self._btn(row, "Set", lambda k=key: self._calibrate(("click_spots", k)), width=56) \
                .pack(side="right", padx=6)
        self._muted(spots, "If spawn isn't set, only Forecast is clicked.", wrap=240).pack(fill="x")

        self.region_vars = {}
        for col, (sec, title) in enumerate([("panel", "OCR text panel"), ("thermos", "Thermos screenshot")], 1):
            card, lf = self._card(top, title)
            card.grid(row=0, column=col, sticky="nsew", padx=(0, 10) if col == 1 else 0)
            self.T[f"region_{sec}"] = card
            for cor, lbl in [("tl", "Top-left"), ("br", "Bottom-right")]:
                v = tk.StringVar(value=self._fmt_pt(CFG.get(sec, cor)))
                self.region_vars[(sec, cor)] = v
                row = ctk.CTkFrame(lf, fg_color="transparent")
                row.pack(fill="x", pady=4)
                self._label(row, lbl, 12, width=90).pack(side="left")
                ctk.CTkLabel(row, textvariable=v, font=F(12, mono=True), text_color=accent()).pack(side="left")
                self._btn(row, "Set", lambda s=sec, c=cor: self._calibrate((s, c)), width=56).pack(side="right")
            self._btn(lf, "Preview region", lambda s=sec: self.preview_region(s)).pack(anchor="w", pady=(10, 0))

        bottom = ctk.CTkFrame(page, fg_color="transparent")
        bottom.pack(fill="x", pady=(12, 0))
        bottom.grid_columnconfigure(0, weight=1, uniform="b")
        bottom.grid_columnconfigure(1, weight=1, uniform="b")

        card, ocr = self._card(bottom, "OCR image", "Tune until Preview shows crisp black text on white.")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.T["ocrimg"] = card
        o = CFG.get("ocr")
        self.sv_thresh = tk.IntVar(value=int(o["threshold"]))
        self.sv_contrast = tk.DoubleVar(value=float(o["contrast"]))
        for lbl, var, lo, hi, steps, fmt in [("Threshold", self.sv_thresh, 0, 255, 255, "{:.0f}"),
                                             ("Contrast", self.sv_contrast, 0.5, 6.0, 55, "{:.1f}")]:
            row = ctk.CTkFrame(ocr, fg_color="transparent")
            row.pack(fill="x", pady=4)
            self._label(row, lbl, 12, width=80).pack(side="left")
            shown = tk.StringVar(value=fmt.format(var.get()))
            ctk.CTkSlider(row, from_=lo, to=hi, number_of_steps=steps, variable=var,
                          command=lambda val, s=shown, f=fmt, v=var: (
                              v.set(round(float(val)) if isinstance(v, tk.IntVar) else round(float(val), 1)),
                              s.set(f.format(float(val))))).pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkLabel(row, textvariable=shown, width=40, font=F(12, mono=True), text_color=accent()) \
                .pack(side="left")
        orow = ctk.CTkFrame(ocr, fg_color="transparent")
        orow.pack(anchor="w", pady=(10, 0))
        self._btn(orow, "Save", self.save_ocr, "accent", width=80).pack(side="left")
        self._btn(orow, "Test OCR now", self.read_now).pack(side="left", padx=8)

        card, clk = self._card(bottom, "Click timing")
        card.grid(row=0, column=1, sticky="nsew")
        self.T["clicktiming"] = card
        cc = CFG.get("click")
        self.sv_settle = tk.StringVar(value=str(cc["settle_ms"]))
        self.sv_pause = tk.StringVar(value=str(cc["pause_ms"]))
        self.sv_attempts = tk.StringVar(value=str(cc["attempts"]))
        for lbl, var, unit in [("Settle after focus", self.sv_settle, "ms"),
                               ("Pause before click", self.sv_pause, "ms"),
                               ("Max attempts", self.sv_attempts, "")]:
            row = ctk.CTkFrame(clk, fg_color="transparent")
            row.pack(fill="x", pady=3)
            self._label(row, lbl, 12, width=150).pack(side="left")
            self._entry(row, var, width=70).pack(side="left")
            self._muted(row, unit).pack(side="left", padx=6)
        crow = ctk.CTkFrame(clk, fg_color="transparent")
        crow.pack(anchor="w", pady=(10, 0))
        self._btn(crow, "Save", self.save_click, "accent", width=80).pack(side="left")
        self._btn(crow, "Mouse position (3s)", self.mouse_pos).pack(side="left", padx=8)

    # ── Requirements page ───────────────────────────────
    def _build_req_page(self):
        page = self._scroll_page("req")
        self._page_header(page, "Requirements", "Normal rows: all must pass.  Solo rows: any one is enough.")
        self.sv_req_en = tk.BooleanVar(value=bool(CFG.get("filters_enabled")))
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.pack(fill="x", pady=(0, 10))
        self._switch(head, "Check requirements", self.sv_req_en,
                     lambda: (CFG.set("filters_enabled", bool(self.sv_req_en.get())),
                              self.log(f"Requirements {'on' if self.sv_req_en.get() else 'off'}."))) \
            .pack(side="left")
        self._muted(head, "When off, nothing is sent and no popup appears.").pack(side="left", padx=14)

        card, lf = self._card(page, "Conditions")
        card.pack(fill="x")
        self.T["conditions"] = card
        for col, (txt, w) in enumerate([("On", 50), ("Field", 130), ("Op", 100), ("Value", 140), ("Solo", 60)]):
            ctk.CTkLabel(lf, text=txt.upper(), font=F(11, "bold"), text_color=MUTED, width=w, anchor="w") \
                .grid(row=0, column=col, sticky="w", padx=6, pady=(0, 6))

        self.filter_vars = {}
        fcfg = CFG.get("filters")
        for i, key in enumerate(FILTER_FIELDS, 1):
            fd = fcfg.get(key, {})
            en = tk.BooleanVar(value=bool(fd.get("enabled")))
            op = tk.StringVar(value=str(fd.get("op", ">=")))
            ind = tk.BooleanVar(value=bool(fd.get("independent")))
            val = tk.StringVar(value=str(fd.get("value", "SLGT" if key == "Risk" else 0.0)))
            ctk.CTkSwitch(lf, text="", variable=en, onvalue=True, offvalue=False, width=44) \
                .grid(row=i, column=0, padx=6, pady=4, sticky="w")
            self._label(lf, key, 12).grid(row=i, column=1, padx=6, sticky="w")
            ctk.CTkSegmentedButton(lf, values=OPS, variable=op, font=F(12, mono=True), width=90) \
                .grid(row=i, column=2, padx=6, sticky="w")
            if key == "Risk":
                val.set(norm_risk(val.get()) or "SLGT")
                ctk.CTkOptionMenu(lf, values=RISK_ORDER, variable=val, width=130, font=F(12)) \
                    .grid(row=i, column=3, padx=6, sticky="w")
            else:
                self._entry(lf, val, width=130).grid(row=i, column=3, padx=6, sticky="w")
            ctk.CTkCheckBox(lf, text="", variable=ind, onvalue=True, offvalue=False, width=24,
                            corner_radius=6).grid(row=i, column=4, padx=6, sticky="w")
            self.filter_vars[key] = {"enabled": en, "op": op, "value": val, "independent": ind}

        btns = ctk.CTkFrame(page, fg_color="transparent")
        btns.pack(fill="x", pady=12)
        self._btn(btns, "Save requirements", self.save_filters, "accent").pack(side="left")
        self.T["req_save"] = btns
        self._btn(btns, "Revert", self.reload_filters).pack(side="left", padx=8)

    # ── Records page ────────────────────────────────────
    def _build_records_page(self):
        page = self._scroll_page("records")
        self._page_header(page, "Record hunt", "Values you're trying to beat. A hit sends a full screenshot "
                                               "to Discord and never stops the loop.")
        card, lf = self._card(page, "Records")
        card.pack(fill="x")
        self.T["records"] = card
        hdr = ctk.CTkFrame(lf, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 6))
        for txt, w in [("On", 50), ("Name", 200), ("Field", 140), ("Op", 96), ("Value", 110)]:
            ctk.CTkLabel(hdr, text=txt.upper(), font=F(11, "bold"), text_color=MUTED, width=w, anchor="w") \
                .pack(side="left", padx=4)
        self.rh_frame = ctk.CTkFrame(lf, fg_color="transparent")
        self.rh_frame.pack(fill="x")
        self.record_rows = []
        for r in CFG.get("records", default=[]):
            self._add_record(r.get("name", ""), r.get("enabled", True), r.get("field", "CAPE"),
                             r.get("op", ">="), str(r.get("value", 0.0)))
        btns = ctk.CTkFrame(page, fg_color="transparent")
        btns.pack(fill="x", pady=12)
        self._btn(btns, "+ Add record", self._add_record).pack(side="left")
        self._btn(btns, "Save records", self.save_records, "accent").pack(side="left", padx=8)

    def _add_record(self, name="", enabled=True, field="CAPE", op=">=", value="0"):
        row = ctk.CTkFrame(self.rh_frame, fg_color="transparent")
        row.pack(fill="x", pady=3)
        r = {"frame": row, "enabled": tk.BooleanVar(value=enabled), "name": tk.StringVar(value=name),
             "field": tk.StringVar(value=field), "op": tk.StringVar(value=op), "value": tk.StringVar(value=value)}
        ctk.CTkSwitch(row, text="", variable=r["enabled"], onvalue=True, offvalue=False, width=50) \
            .pack(side="left", padx=4)
        self._entry(row, r["name"], width=200, placeholder_text="Name").pack(side="left", padx=4)
        ctk.CTkOptionMenu(row, values=DISPLAY_FIELDS, variable=r["field"], width=140, font=F(12)) \
            .pack(side="left", padx=4)
        ctk.CTkSegmentedButton(row, values=OPS, variable=r["op"], width=96, font=F(12, mono=True)) \
            .pack(side="left", padx=4)
        self._entry(row, r["value"], width=110).pack(side="left", padx=4)
        self._btn(row, "✕", lambda: self._del_record(row), "ghost", width=34).pack(side="left", padx=6)
        self.record_rows.append(r)

    def _del_record(self, frame):
        self.record_rows = [r for r in self.record_rows if r["frame"] is not frame]
        frame.destroy()

    # ── Settings page ───────────────────────────────────
    def _build_settings_page(self):
        page = self._scroll_page("settings")
        self._page_header(page, "Settings", "Saved to config.json. Most changes apply immediately.")
        s = CFG.get("settings")
        self.set_vars = {
            "appearance": tk.StringVar(value=s["appearance"]),
            "theme": tk.StringVar(value=s["theme"]),
            "scaling": tk.IntVar(value=int(s["scaling"])),
            "close_action": tk.StringVar(value="Minimize to tray" if s["close_action"] == "tray" else "Quit"),
            "always_on_top": tk.BooleanVar(value=bool(s["always_on_top"])),
            "notifications": tk.BooleanVar(value=bool(s["notifications"])),
            "sound_on_pass": tk.BooleanVar(value=bool(s["sound_on_pass"])),
            "ping_role": tk.BooleanVar(value=bool(s["ping_role"])),
            "role_id": tk.StringVar(value=str(s["role_id"])),
            "history_limit": tk.StringVar(value=str(s["history_limit"])),
            "log_limit": tk.StringVar(value=str(s["log_limit"])),
        }
        v = self.set_vars

        def row(parent, title, helper=None):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", pady=6)
            txt = ctk.CTkFrame(r, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True)
            self._label(txt, title, 13).pack(fill="x")
            if helper:
                self._muted(txt, helper, size=11).pack(fill="x")
            return r

        # Appearance
        card, b = self._card(page, "Appearance")
        card.pack(fill="x", pady=(0, 12))
        self.T["appearance"] = card
        ctk.CTkSegmentedButton(row(b, "Mode"), values=APPEARANCES, variable=v["appearance"],
                               command=lambda _: self._set("appearance", v["appearance"].get())) \
            .pack(side="right")
        ctk.CTkSegmentedButton(row(b, "Accent colour", "Applies after restart."), values=THEMES,
                               variable=v["theme"],
                               command=lambda _: self._set("theme", v["theme"].get())).pack(side="right")
        r = row(b, "UI scaling", "80–150%. Applied when you release the slider.")
        self.scale_lbl = ctk.CTkLabel(r, text=f"{v['scaling'].get()}%", width=50, font=F(12, mono=True),
                                      text_color=accent())
        self.scale_lbl.pack(side="right")
        sl = ctk.CTkSlider(r, from_=SCALE_MIN, to=SCALE_MAX, number_of_steps=(SCALE_MAX - SCALE_MIN) // 5,
                           variable=v["scaling"], width=220,
                           command=lambda val: self.scale_lbl.configure(text=f"{int(round(val))}%"))
        sl.pack(side="right", padx=8)
        sl.bind("<ButtonRelease-1>", lambda e: self._set("scaling", int(v["scaling"].get())))

        # Window
        card, b = self._card(page, "Window & alerts")
        card.pack(fill="x", pady=(0, 12))
        ctk.CTkSegmentedButton(row(b, "Close button", None if HAVE_TRAY else
                                   "pystray not installed: 'tray' minimizes to the taskbar."),
                               values=["Minimize to tray", "Quit"], variable=v["close_action"],
                               command=lambda val: self._set("close_action", "tray" if val != "Quit" else "quit")) \
            .pack(side="right")
        for key, title, helper in [
                ("always_on_top", "Always on top", None),
                ("notifications", "Desktop notifications", "Tray balloon on pass / when hidden."),
                ("sound_on_pass", "Sound on pass", None)]:
            ctk.CTkSwitch(row(b, title, helper), text="", variable=v[key], onvalue=True, offvalue=False,
                          command=lambda k=key: self._set(k, bool(v[k].get()))).pack(side="right")

        # Discord
        card, b = self._card(page, "Discord")
        card.pack(fill="x", pady=(0, 12))
        ctk.CTkSwitch(row(b, "Ping role", "Mention the role in webhook messages."), text="",
                      variable=v["ping_role"], onvalue=True, offvalue=False,
                      command=lambda: self._set("ping_role", bool(v["ping_role"].get()))).pack(side="right")
        e = self._entry(row(b, "Role ID"), v["role_id"], width=220, mono=True)
        e.pack(side="right")
        self._commit(e, self._commit_role)

        # Data
        card, b = self._card(page, "Data & log")
        card.pack(fill="x", pady=(0, 12))
        for key, title, helper, lo in [("history_limit", "History limit", "Scans kept in data.txt.", 10),
                                       ("log_limit", "Log lines", "Lines kept in the log panel.", 100)]:
            e = self._entry(row(b, title, helper), v[key], width=100)
            e.pack(side="right")
            self._commit(e, lambda k=key, t=title, m=lo: self._commit_int(k, t, m))
        r = ctk.CTkFrame(b, fg_color="transparent")
        r.pack(fill="x", pady=(10, 0))
        self._btn(r, "Open data folder", self.open_folder).pack(side="left")
        rb = self._btn(r, "▶  Replay tutorial", self.start_tour, "accent")
        rb.pack(side="left", padx=8)
        self.T["replay"] = rb
        self._btn(r, "Reset settings to defaults", self.reset_settings, "danger").pack(side="right")

    def _set(self, key, value, quiet=False):
        CFG.set("settings", key, value)
        if key == "appearance":
            ctk.set_appearance_mode(value)
            self.root.after(50, self._apply_log_tags)
        elif key == "theme":
            ctk.set_default_color_theme(value)
        elif key == "scaling":
            ctk.set_widget_scaling(max(SCALE_MIN, min(SCALE_MAX, int(value))) / 100)
            self.scale_lbl.configure(text=f"{int(value)}%")
        elif key == "always_on_top":
            self.apply_always_on_top()
        if not quiet:
            shown = {True: "on", False: "off"}.get(value, value) if isinstance(value, bool) else value
            self.log(f"Setting: {key.replace('_', ' ')} = {shown}" +
                     ("  (restart to apply)" if key == "theme" else ""), "muted")

    def _commit_int(self, key, title, minv):
        try:
            n = self._int(self.set_vars[key], title, minv)
        except ValueError as e:
            self.log(str(e), "err")
            self.set_vars[key].set(str(setting(key)))
            return
        if n != setting(key):
            self._set(key, n)

    def _commit_role(self):
        rid = self.set_vars["role_id"].get().strip()
        if rid and not rid.isdigit():
            self.log("Role ID must be digits only (or empty).", "err")
            self.set_vars["role_id"].set(str(setting("role_id")))
            return
        if rid != setting("role_id"):
            self._set("role_id", rid)

    def apply_always_on_top(self):
        try:
            self.root.attributes("-topmost", bool(setting("always_on_top")))
        except Exception:
            pass

    def reset_settings(self):
        if not messagebox.askyesno("Reset settings", "Reset all Settings to their defaults?\n"
                                   "(Links, regions, requirements and records are kept.)", parent=self.root):
            return
        d = default_settings()
        CFG.set("settings", d)
        for k, var in self.set_vars.items():
            if k == "close_action":
                var.set("Minimize to tray" if d[k] == "tray" else "Quit")
            else:
                var.set(d[k] if not isinstance(var, tk.StringVar) else str(d[k]))
        for k in ("appearance", "scaling", "always_on_top"):
            self._set(k, d[k], quiet=True)
        ctk.set_default_color_theme(d["theme"])
        self.log("Settings reset to defaults.", "ok")

    # ── settings actions ────────────────────────────────
    @staticmethod
    def _fmt_pt(pt):
        return f"({pt[0]}, {pt[1]})" if pt else "not set"

    def _save_bool(self, sec, key, var):
        CFG.set(sec, key, bool(var.get()))
        self.log(f"{sec.replace('_', ' ').capitalize()}: {'on' if var.get() else 'off'}")

    def _save_run(self):
        try:
            CFG.set("run", {"load_wait": self._int(self.sv_lwait, "Load wait", 0),
                            "interval": self._int(self.sv_interval, "Interval", 2),
                            "click_sequence": bool(self.sv_doseq.get())})
        except ValueError as e:
            self.log(f"Run settings not saved: {e}", "err")

    @staticmethod
    def _int(var, name, minv):
        try:
            n = int(float(str(var.get()).strip()))
        except ValueError:
            raise ValueError(f"{name} must be a whole number.")
        if n < minv:
            raise ValueError(f"{name} must be at least {minv}.")
        return n

    def save_link(self):
        link = self.sv_link.get().strip()
        try:
            parse_url(link)
        except ValueError as e:
            messagebox.showerror("Bad link", str(e), parent=self.root)
            return
        CFG.set("saved_link", link)
        self.log("Server link saved.", "ok")

    def save_wh(self):
        url = self.sv_wh.get().strip()
        if url and not re.match(r"^https://(?:\w+\.)?discord(?:app)?\.com/api/webhooks/", url):
            if not messagebox.askyesno("Webhook", "That doesn't look like a Discord webhook URL. Save anyway?",
                                       parent=self.root):
                return
        CFG.set("webhook_url", url)
        self.log("Webhook saved.", "ok")

    def test_webhook(self):
        url = self.sv_wh.get().strip()

        def job():
            try:
                send_webhook(url, "Test message", {"Risk": "TEST"}, None, ping=False)
                saved = (CFG.get("webhook_url") or "").strip()
                note = "" if url == saved else " (the URL in the box is not saved yet - press Save)"
                self.log("Webhook test sent." + note, "ok")
            except Exception as e:
                self.log(f"Webhook test failed: {e}", "err")
        self._run_bg(job)

    def save_ocr(self, quiet: bool = False):
        new = {"threshold": int(self.sv_thresh.get()), "contrast": round(float(self.sv_contrast.get()), 2)}
        if new != CFG.get("ocr"):
            CFG.set("ocr", new)
            quiet = False
        if not quiet:
            self.log("OCR settings saved.", "ok")

    def save_click(self):
        try:
            CFG.set("click", {"settle_ms": self._int(self.sv_settle, "Settle ms", 0),
                              "pause_ms": self._int(self.sv_pause, "Pause ms", 0),
                              "attempts": self._int(self.sv_attempts, "Attempts", 1)})
            self.log("Click timing saved.", "ok")
        except ValueError as e:
            messagebox.showerror("Click timing", str(e), parent=self.root)

    def save_filters(self):
        out = {}
        try:
            for key, fv in self.filter_vars.items():
                if key == "Risk":
                    value = fv["value"].get().upper().strip()
                else:
                    try:
                        value = float(fv["value"].get().strip())
                    except ValueError:
                        raise ValueError(f"Value for {key} must be a number.")
                out[key] = {"enabled": bool(fv["enabled"].get()), "op": fv["op"].get(),
                            "value": value, "independent": bool(fv["independent"].get())}
        except ValueError as e:
            messagebox.showerror("Requirements", str(e), parent=self.root)
            return
        CFG.set("filters", out)
        CFG.set("filters_enabled", bool(self.sv_req_en.get()))
        n = sum(1 for f in out.values() if f["enabled"])
        self.log(f"Requirements saved ({n} active).", "ok")

    def reload_filters(self):
        fcfg = CFG.get("filters")
        for key, fv in self.filter_vars.items():
            fd = fcfg.get(key, {})
            fv["enabled"].set(bool(fd.get("enabled")))
            fv["op"].set(fd.get("op", ">="))
            fv["independent"].set(bool(fd.get("independent")))
            fv["value"].set(str(fd.get("value", "SLGT" if key == "Risk" else 0.0)))
        self.log("Requirements reverted to saved values.")

    def save_records(self):
        recs, bad = [], []
        for r in self.record_rows:
            field, raw = r["field"].get(), r["value"].get().strip()
            if field == "Risk":
                value = norm_risk(raw)
                if value not in RISK_ORDER:
                    bad.append(r["name"].get() or field)
                    continue
            else:
                try:
                    value = float(raw)
                except ValueError:
                    bad.append(r["name"].get() or field)
                    continue
            recs.append({"name": r["name"].get().strip(), "enabled": bool(r["enabled"].get()),
                         "field": field, "op": r["op"].get(), "value": value})
        if bad:
            messagebox.showerror("Records", "Invalid value for: " + ", ".join(bad) +
                                 f"\n(Risk records need one of: {', '.join(RISK_ORDER)})", parent=self.root)
            return
        CFG.set("records", recs)
        self.log(f"{len(recs)} record(s) saved.", "ok")

    # ── calibration ─────────────────────────────────────
    _CALIB_LABELS = {
        ("panel", "tl"): "OCR panel — TOP-LEFT corner", ("panel", "br"): "OCR panel — BOTTOM-RIGHT corner",
        ("thermos", "tl"): "Thermos region — TOP-LEFT corner", ("thermos", "br"): "Thermos region — BOTTOM-RIGHT corner",
        ("click_spots", "spawn"): "Spawn / menu button", ("click_spots", "forecast"): "Forecast button",
    }

    def _calibrate(self, target):
        self.root.iconify()
        self.root.after(350, lambda: ClickCapture(self.root, self._CALIB_LABELS[target],
                                                  lambda x, y: self._calib_done(target, x, y),
                                                  self._calib_cancel))

    def _calib_done(self, target, x, y):
        self.root.deiconify()
        sec, key = target
        CFG.set(sec, key, [x, y])
        var = self.spot_vars[key] if sec == "click_spots" else self.region_vars[target]
        var.set(self._fmt_pt([x, y]))
        self.log(f"{self._CALIB_LABELS[target]} set to ({x}, {y})", "ok")

    def _calib_cancel(self):
        self.root.deiconify()
        self.log("Calibration cancelled.", "muted")

    def preview_region(self, sec):
        self.save_ocr(quiet=True)
        try:
            tl, br = region(sec)
            img = crop(screenshot(), tl, br)
        except Exception as e:
            self.log(f"Preview failed: {e}", "err")
            return
        if sec == "panel":
            img = preprocess(img)
        img = img.convert("RGB")
        img.thumbnail((900, 700))
        win = ctk.CTkToplevel(self.root)
        win.title(f"Preview — {sec}" + ("  (as Tesseract sees it)" if sec == "panel" else ""))
        win.configure(fg_color=BG)
        cimg = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        frame = ctk.CTkFrame(win, fg_color=CARD, corner_radius=12)
        frame.pack(padx=14, pady=14)
        lbl = ctk.CTkLabel(frame, image=cimg, text="")
        lbl.image = cimg
        lbl.pack(padx=10, pady=10)
        win.bind("<Escape>", lambda e: win.destroy())
        win.after(100, win.lift)

    def mouse_pos(self):
        def job():
            for i in (3, 2, 1):
                self.log(f"  Reading mouse position in {i}…")
                time.sleep(1)
            p = pyautogui.position()
            self.log(f"Mouse position: ({p.x}, {p.y})", "ok")
        self._run_bg(job)

    # ── run loop ────────────────────────────────────────
    def _run_bg(self, fn, *args):
        def wrap():
            try:
                fn(*args)
            except (Aborted, pyautogui.FailSafeException) as e:
                self.log(f"Aborted: {e}", "warn")
            except Exception as e:
                self.log(f"Error: {e}", "err")
        ABORT.clear()
        threading.Thread(target=wrap, daemon=True).start()

    @property
    def busy(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    def get_proto(self) -> str:
        link = self.sv_link.get().strip() or CFG.get("saved_link", default="")
        if not link:
            raise ValueError("No server link saved.")
        return build_proto(*parse_url(link))

    def join_now(self):
        if self.busy:
            self.log("Already running…", "muted")
            return
        try:
            proto = self.get_proto()
            lw = self._int(self.sv_lwait, "Load wait", 0)
        except ValueError as e:
            self.log(f"Cannot join: {e}", "err")
            return
        self._save_run()
        self.stop_event.clear()
        ABORT.clear()
        self.worker = threading.Thread(target=self._job, args=(proto, lw, bool(self.sv_doseq.get())), daemon=True)
        self.worker.start()

    def _sleep(self, secs: float) -> bool:
        """Interruptible sleep. Returns False if Stop was pressed or the mouse hit a corner."""
        end = time.time() + secs
        while time.time() < end:
            if self.stop_event.wait(min(0.1, max(0.0, end - time.time()))):
                return False
            if mouse_in_corner():
                self.log("Stopped (mouse moved to a screen corner).", "warn")
                self.call(self.stop_all)
                return False
        return not self.stop_event.is_set()

    def _job(self, proto, lw, do_seq):
        try:
            self.log("Launching Roblox…")
            os.startfile(proto)
            self.log(f"Waiting {lw}s for the game to load…")
            if not self._sleep(lw):
                return
            if do_seq:
                if CFG.get("click_spots", "spawn"):
                    click_spawn(self.status)
                    self.log("  Waiting 5s before clicking Forecast…")
                    if not self._sleep(5):
                        return
                click_forecast(self.status)
                if not self._sleep(3):
                    return
            self.log("Reading OCR…")
            try:
                vals, raw, img = read_panel()
            except Exception as e:
                self.log(f"OCR failed: {e}", "err")
                self._maybe_reroll()
                return
            if self.stop_event.is_set():
                self.log("Stopped - scan result ignored.", "muted")
                return
            self._process(vals, raw, img, act=True)
        except (Aborted, pyautogui.FailSafeException) as e:
            self.log(f"Stopped: {e}", "warn")
            self.call(self.stop_all)
        except Exception as e:
            self.log(f"Error: {e}", "err")
            self._maybe_reroll()

    def read_now(self):
        if self.busy:
            self.log("Busy — wait for the current run to finish.", "muted")
            return

        self.save_ocr(quiet=True)

        def job():
            self.log("Reading OCR… (test read - no webhooks are sent)")
            vals, raw, img = read_panel()
            self._process(vals, raw, img, act=False)
        self.worker = threading.Thread(target=lambda: self._safe(job), daemon=True)
        self.worker.start()

    def _safe(self, fn):
        try:
            fn()
        except Exception as e:
            self.log(f"Error: {e}", "err")

    def _process(self, vals: dict, raw: str, img: Image.Image, act: bool):
        """Evaluate a scan. act=True → this came from a join run (popup/reroll allowed)."""
        filters_on = bool(CFG.get("filters_enabled"))
        passed, reasons = apply_filters(vals, CFG.get("filters")) if filters_on else (False, [])
        self.stats["scans"] += 1
        self.call(self._show_vals, vals, passed, filters_on)

        if not vals:
            self.log("No values read — check the panel region / OCR settings.", "warn")
            self.log("  raw: " + (raw.replace("\n", " | ") or "(empty)"), "muted")
        else:
            self.log("  " + "  ".join(f"{k}={vals[k]}" for k in DISPLAY_FIELDS if k in vals), "muted")
        for r in reasons:
            self.log(f"  - {r}", "muted")
        try:
            log_result(vals, passed, reasons)
        except Exception as e:
            self.log(f"Could not write data.txt: {e}", "err")

        wh_url = (CFG.get("webhook_url") or "").strip()
        server_link = (CFG.get("saved_link") or "").strip()

        if filters_on and passed:
            self.stats["passes"] += 1
            self.log("✔ Requirements met!", "ok")
            self.notify("Requirements met!")
            if not (act and CFG.get("pass_dialog", "enabled")):
                play_pass_sound()
            if wh_url and act:
                try:
                    thermo = None
                    try:
                        tl, br = region("thermos")
                        thermo = png_bytes(crop(img, tl, br))
                    except Exception:
                        pass
                    send_webhook(wh_url, "Requirements passed", vals, thermo, server_link)
                    self.log("  Webhook sent.", "ok")
                except Exception as e:
                    self.log(f"Webhook error: {e}", "err")
        elif filters_on:
            self.log("✘ Requirements not met.", "warn")
        else:
            self.log("Requirements checking is off.", "muted")

        hits = check_records(vals, CFG.get("records", default=[]))
        if hits:
            self.stats["records"] += 1
            self.log(f"★ Record hit: {', '.join(hits)}", "ok")
            if wh_url and act:
                try:
                    send_webhook(wh_url, f"Record hit: {', '.join(hits)}", vals, png_bytes(img),
                                 server_link, color=0xFFD700, filename="screenshot.png")
                    self.log("  Record webhook sent.", "ok")
                except Exception as e:
                    self.log(f"Record webhook error: {e}", "err")

        if not act:
            return
        if filters_on and passed and CFG.get("pass_dialog", "enabled"):
            self.log("Waiting for your choice…")
            if not self.ask_pass(vals):
                self.call(self.stop_all)
                self.log("Stopped at your request.")
                return
            self._maybe_reroll(force=True)
            return
        if filters_on and not passed:
            self._maybe_reroll()
        elif self.next_join_at is not None:
            iv = self._int(self.sv_interval, "Interval", 2)
            self.next_join_at = time.time() + iv

    def _maybe_reroll(self, force: bool = False):
        if self.stop_event.is_set():
            return
        if force or CFG.get("auto_reroll", "enabled") or self.next_join_at is not None:
            try:
                delay = self._int(self.sv_interval, "Interval", 2)
            except ValueError:
                delay = 2
            self.log(f"  Rerolling in {delay}s…")
            self.call(self._schedule_reroll, delay)

    def _schedule_reroll(self, delay: int = 2):
        if self.stop_event.is_set():
            return
        if self.reroll_after_id:
            self.root.after_cancel(self.reroll_after_id)
        self.reroll_after_id = self.root.after(int(delay * 1000), self._do_reroll)

    def _do_reroll(self):
        self.reroll_after_id = None
        if not self.stop_event.is_set():
            self.join_now()

    def _show_vals(self, vals, passed, filters_on):
        for k, v in self.val_vars.items():
            v.set(vals.get(k, "—"))
        if not filters_on:
            self.sv_result.set("Requirements off")
            self.result_lbl.configure(text_color=MUTED, fg_color=TILE)
        elif passed:
            self.sv_result.set("✔  PASSED")
            self.result_lbl.configure(text_color=OK, fg_color=OK_BG)
        else:
            self.sv_result.set("✘  Not passed")
            self.result_lbl.configure(text_color=ERR, fg_color=("#fdecec", "#2c1719"))

    def start_auto(self):
        try:
            self.get_proto()
            iv = self._int(self.sv_interval, "Interval", 2)
        except ValueError as e:
            self.log(f"Auto rejoin: {e}", "err")
            return
        self._save_run()
        self.stop_event.clear()
        self.next_join_at = time.time() + iv
        self.log(f"Auto rejoin started (every {iv}s after each run).", "ok")

    def stop_all(self):
        self.stop_event.set()
        ABORT.set()
        self.next_join_at = None
        if self.reroll_after_id:
            self.root.after_cancel(self.reroll_after_id)
            self.reroll_after_id = None
        self.sv_auto.set("Auto: off")
        self.log("Stopped.", "warn")

    def _tick(self):
        if show_requested():
            self.show_window()
        if self.next_join_at is not None:
            rem = int(self.next_join_at - time.time())
            if self.busy:
                self.sv_auto.set("Auto: running…")
            elif rem <= 0:
                self.sv_auto.set("Auto: joining…")
                self.next_join_at = time.time() + 3600  # pushed back again once the run finishes
                self.join_now()
            else:
                self.sv_auto.set(f"Auto: next in {rem}s")
        elif self.busy:
            self.sv_auto.set("Running…")
        else:
            self.sv_auto.set("Auto: off")

        up = int(time.time() - self.started_at)
        self.stat_vars["uptime"].set(f"{up // 3600}:{up % 3600 // 60:02d}:{up % 60:02d}")
        for k in ("scans", "passes", "records"):
            self.stat_vars[k].set(str(self.stats[k]))
        self.root.after(1000, self._tick)

    # ── misc ────────────────────────────────────────────
    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def open_data(self):
        if not DATA_FILE.is_file():
            atomic_write_json(DATA_FILE, _empty_data())
        os.startfile(DATA_FILE)

    def open_folder(self):
        os.startfile(APP_DIR)

    def on_close(self):
        if self.tour is not None:
            self.tour.finish()  # closing counts as finishing, so the tour won't come back
        if not CFG.get("close_asked", default=False):
            ans = messagebox.askyesnocancel(
                APP_NAME,
                "Quit the app?\n\n"
                "Yes = quit completely\n"
                "No = keep running in the system tray\n\n"
                "You won't be asked again. Change it any time in Settings → Close button.",
                parent=self.root)
            if ans is None:
                return
            choice = "quit" if ans else "tray"
            CFG.set("close_asked", True)
            self._set("close_action", choice)
            try:
                self.set_vars["close_action"].set("Quit" if choice == "quit" else "Minimize to tray")
            except Exception:
                pass
        if setting("close_action") != "tray":
            self.quit_app()
        elif self.tray.icon:
            self.root.withdraw()
            self.notify("Still running in the tray. Right-click the tray icon → Quit to close it.")
        else:
            self.root.iconify()  # no pystray: minimize to the taskbar instead

    def show_window(self):
        self.root.deiconify()
        if self.root.state() == "iconic":
            self.root.state("normal")
        self.root.lift()
        self.root.attributes("-topmost", True)  # Windows won't let a background app steal focus otherwise
        self.root.after(200, self.apply_always_on_top)
        self.root.focus_force()

    def quit_app(self):
        self.stop_event.set()
        ABORT.set()
        if self.tour is not None:
            try:
                self.tour.finish()
            except Exception:
                pass
        self.tray.stop()
        try:
            self.root.destroy()
        finally:
            os._exit(0)  # make sure no background thread keeps the process alive


_INSTANCE_MUTEX = None
_SHOW_EVENT = None


def claim_single_instance() -> bool:
    """True if this is the only running copy. Otherwise asks the running copy to show itself."""
    global _INSTANCE_MUTEX, _SHOW_EVENT
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.wintypes.HANDLE
    k32.CreateEventW.restype = ctypes.wintypes.HANDLE
    k32.OpenEventW.restype = ctypes.wintypes.HANDLE
    ERROR_ALREADY_EXISTS = 183
    _INSTANCE_MUTEX = k32.CreateMutexW(None, False, "Local\\TwisterXAutoRoller.Instance")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        EVENT_MODIFY_STATE = 0x0002
        h = k32.OpenEventW(EVENT_MODIFY_STATE, False, "Local\\TwisterXAutoRoller.Show")
        if h:
            k32.SetEvent(h)
            k32.CloseHandle(h)
        return False
    _SHOW_EVENT = k32.CreateEventW(None, False, False, "Local\\TwisterXAutoRoller.Show")
    return True


def show_requested() -> bool:
    """Polled by the app: did a second copy ask us to come to the front?"""
    if not _SHOW_EVENT:
        return False
    return ctypes.windll.kernel32.WaitForSingleObject(_SHOW_EVENT, 0) == 0  # WAIT_OBJECT_0


def main():
    global CFG
    if not claim_single_instance():
        return  # already running: the existing window pops up instead
    CFG = Config(CFG_FILE)
    st = CFG.get("settings")
    ctk.set_appearance_mode(st["appearance"] if st.get("appearance") in APPEARANCES else "Dark")
    ctk.set_default_color_theme(st["theme"] if st.get("theme") in THEMES else "blue")
    try:
        ctk.set_widget_scaling(max(SCALE_MIN, min(SCALE_MAX, int(st["scaling"]))) / 100)
    except (TypeError, ValueError):
        pass
    root = ctk.CTk()  # customtkinter handles DPI scaling itself
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
