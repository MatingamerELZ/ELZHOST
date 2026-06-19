"""
=============================================================
  ELZ Assistant - Command Controller
  File: control.py
  Purpose: Parse voice/text commands and execute device actions
           Contacts, apps, files, calls, SMS, system controls
=============================================================
"""

import os
import json
import re
import time
import threading
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Android bridge
try:
    from jnius import autoclass                                    # type: ignore
    from android.permissions import request_permissions, Permission # type: ignore
    IS_ANDROID = True
except ImportError:
    IS_ANDROID = False

# ----------------------------------------------------------------
BASE_DIR  = Path(__file__).resolve().parent.parent
JSON_DIR  = BASE_DIR / "json"
SETTINGS  = JSON_DIR / "settings.json"
MEMORY    = JSON_DIR / "memory.json"
CMD_LOG   = JSON_DIR / "command_log.json"
LICENSE   = JSON_DIR / "license.json"


def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _is_pro() -> bool:
    s = _load_json(SETTINGS)
    return s.get("is_pro", False)


# ================================================================
#  Android helpers
# ================================================================

class AndroidBridge:
    """Thin wrapper over Android Java APIs via pyjnius."""

    @staticmethod
    def get_activity():
        if not IS_ANDROID:
            return None
        try:
            return autoclass("org.kivy.android.PythonActivity").mActivity
        except Exception:
            return None

    @staticmethod
    def open_app(package_name: str) -> bool:
        if not IS_ANDROID:
            print(f"[Android] open_app({package_name}) – simulation")
            return True
        try:
            ctx     = AndroidBridge.get_activity()
            Intent  = autoclass("android.content.Intent")
            pkg_mgr = ctx.getPackageManager()
            intent  = pkg_mgr.getLaunchIntentForPackage(package_name)
            if intent:
                ctx.startActivity(intent)
                return True
            return False
        except Exception as e:
            print(f"[Android] open_app error: {e}")
            return False

    @staticmethod
    def make_call(number: str) -> bool:
        if not IS_ANDROID:
            print(f"[Android] make_call({number}) – simulation")
            return True
        try:
            ctx    = AndroidBridge.get_activity()
            Intent = autoclass("android.content.Intent")
            Uri    = autoclass("android.net.Uri")
            intent = Intent(Intent.ACTION_CALL, Uri.parse(f"tel:{number}"))
            ctx.startActivity(intent)
            return True
        except Exception as e:
            print(f"[Android] make_call error: {e}")
            return False

    @staticmethod
    def send_sms(number: str, message: str) -> bool:
        if not IS_ANDROID:
            print(f"[Android] send_sms({number}, '{message}') – simulation")
            return True
        try:
            SmsManager = autoclass("android.telephony.SmsManager")
            mgr = SmsManager.getDefault()
            mgr.sendTextMessage(number, None, message, None, None)
            return True
        except Exception as e:
            print(f"[Android] send_sms error: {e}")
            return False

    @staticmethod
    def set_brightness(value: int) -> bool:
        """value 0–255"""
        if not IS_ANDROID:
            print(f"[Android] set_brightness({value}) – simulation")
            return True
        try:
            ctx      = AndroidBridge.get_activity()
            Settings = autoclass("android.provider.Settings")
            Settings.System.putInt(
                ctx.getContentResolver(),
                Settings.System.SCREEN_BRIGHTNESS,
                max(0, min(255, value))
            )
            return True
        except Exception as e:
            print(f"[Android] brightness error: {e}")
            return False

    @staticmethod
    def set_volume(stream: int, level: int) -> bool:
        if not IS_ANDROID:
            print(f"[Android] set_volume(stream={stream}, level={level}) – simulation")
            return True
        try:
            ctx    = AndroidBridge.get_activity()
            Audio  = autoclass("android.media.AudioManager")
            am     = ctx.getSystemService(ctx.AUDIO_SERVICE)
            max_v  = am.getStreamMaxVolume(stream)
            target = int(level / 100 * max_v)
            am.setStreamVolume(stream, target, 0)
            return True
        except Exception as e:
            print(f"[Android] volume error: {e}")
            return False

    @staticmethod
    def list_contacts() -> list:
        if not IS_ANDROID:
            return [{"name": "Test Contact", "phone": "09123456789"}]
        try:
            ctx          = AndroidBridge.get_activity()
            Contacts_URI = autoclass("android.provider.ContactsContract$Contacts")
            Phone_URI    = autoclass("android.provider.ContactsContract$CommonDataKinds$Phone")
            cr           = ctx.getContentResolver()
            cursor       = cr.query(Contacts_URI.CONTENT_URI, None, None, None, None)
            contacts     = []
            if cursor:
                while cursor.moveToNext():
                    name = cursor.getString(
                        cursor.getColumnIndex(Contacts_URI.DISPLAY_NAME))
                    cid  = cursor.getString(
                        cursor.getColumnIndex(Contacts_URI._ID))
                    p_cursor = cr.query(
                        Phone_URI.CONTENT_URI, None,
                        f"{Phone_URI.CONTACT_ID} = ?", [cid], None)
                    if p_cursor:
                        while p_cursor.moveToNext():
                            phone = p_cursor.getString(
                                p_cursor.getColumnIndex(Phone_URI.NUMBER))
                            contacts.append({"name": name, "phone": phone})
                        p_cursor.close()
                cursor.close()
            return contacts
        except Exception as e:
            print(f"[Android] list_contacts error: {e}")
            return []

    @staticmethod
    def get_battery_level() -> int:
        if not IS_ANDROID:
            return 85
        try:
            ctx = AndroidBridge.get_activity()
            Intent = autoclass("android.content.Intent")
            Filter = autoclass("android.content.IntentFilter")
            BM     = autoclass("android.os.BatteryManager")
            ifilter = Filter(Intent.ACTION_BATTERY_CHANGED)
            status  = ctx.registerReceiver(None, ifilter)
            level   = status.getIntExtra(BM.EXTRA_LEVEL, -1)
            scale   = status.getIntExtra(BM.EXTRA_SCALE, -1)
            return int(level / scale * 100) if scale > 0 else -1
        except Exception as e:
            print(f"[Android] battery error: {e}")
            return -1


# ================================================================
#  Alarm helper
# ================================================================

class AlarmManager:
    def __init__(self, speak_fn):
        self._speak    = speak_fn
        self._alarms   = []
        self._thread   = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def add(self, hour: int, minute: int, label: str = "آلارم") -> None:
        now    = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        self._alarms.append({"time": target, "label": label, "fired": False})
        data = _load_json(MEMORY)
        data.setdefault("alarms", []).append({
            "hour": hour, "minute": minute, "label": label,
            "created": now.isoformat()})
        _save_json(MEMORY, data)

    def _loop(self):
        while True:
            now = datetime.now()
            for alarm in self._alarms:
                if not alarm["fired"] and now >= alarm["time"]:
                    alarm["fired"] = True
                    self._speak(f"{alarm['label']}! وقتشه!")
            time.sleep(10)


# ================================================================
#  Command Parser
# ================================================================

class CommandParser:
    """
    Matches a text command (Farsi or English) to an action.
    Returns (action_name, params_dict) or ("unknown", {}).
    """

    # ---- rule table -------------------------------------------
    # Each rule: (regex_pattern, action_name, param_extractor_fn)
    _RULES_FA = [
        # Apps
        (r"باز\s*کن\s+(.*)",       "open_app",   lambda m: {"target": m.group(1).strip()}),
        (r"(تلگرام|واتساپ|اینستاگرام|یوتیوب|دوربین|مخاطبین|تماس|پیام)", "open_app",
         lambda m: {"target": m.group(1).strip()}),
        # Calls
        (r"زنگ\s*بزن\s+(.*)",      "call",       lambda m: {"target": m.group(1).strip()}),
        (r"تماس\s*(با|به)\s+(.*)", "call",       lambda m: {"target": m.group(2).strip()}),
        # SMS
        (r"پیام\s*بده\s+(.*)",     "sms",        lambda m: {"target": m.group(1).strip()}),
        # Volume
        (r"صدا\s*(رو|را)?\s*ببر\s*(بالا|زیاد)",  "volume_up",   lambda m: {}),
        (r"صدا\s*(رو|را)?\s*ببر\s*(پایین|کم)",   "volume_down", lambda m: {}),
        (r"صدا\s*(رو|را)?\s*قطع\s*کن",           "mute",        lambda m: {}),
        # Brightness
        (r"(روشنایی|نور)\s*(رو|را)?\s*زیاد\s*کن",  "brightness_up",   lambda m: {}),
        (r"(روشنایی|نور)\s*(رو|را)?\s*کم\s*کن",    "brightness_down", lambda m: {}),
        # Battery
        (r"(باتری|شارژ)",          "battery",    lambda m: {}),
        # Alarm
        (r"آلارم\s*(بذار|بزار|تنظیم\s*کن)\s*(\d{1,2})\s*[:،]\s*(\d{2})",
         "set_alarm", lambda m: {"hour": int(m.group(2)), "minute": int(m.group(3))}),
        # Notes
        (r"یادداشت\s*بنویس\s+(.*)", "add_note",  lambda m: {"text": m.group(1).strip()}),
        # Time / Date
        (r"(ساعت|وقت)\s*چنده",    "get_time",   lambda m: {}),
        (r"(امروز\s*چندمه|تاریخ)", "get_date",   lambda m: {}),
        # Weather
        (r"(آب\s*و\s*هوا|هوا)",   "weather",    lambda m: {}),
        # Contacts
        (r"(مخاطبین|لیست\s*تماس)", "contacts",  lambda m: {}),
        # Settings
        (r"(تنظیمات|settings)",   "open_settings", lambda m: {}),
        # Pro activation
        (r"کد\s*(فعال\s*سازی|پرو|پریمیوم)?\s*(.+)", "activate_pro",
         lambda m: {"code": m.group(2).strip()}),
        # Help
        (r"(کمک|راهنما|help)",    "help",       lambda m: {}),
    ]

    _RULES_EN = [
        (r"open\s+(.*)",           "open_app",   lambda m: {"target": m.group(1).strip()}),
        (r"call\s+(.*)",           "call",       lambda m: {"target": m.group(1).strip()}),
        (r"(send|message)\s+(.*)", "sms",        lambda m: {"target": m.group(2).strip()}),
        (r"volume\s*up",           "volume_up",  lambda m: {}),
        (r"volume\s*down",         "volume_down",lambda m: {}),
        (r"mute",                  "mute",       lambda m: {}),
        (r"battery",               "battery",    lambda m: {}),
        (r"(time|clock)",          "get_time",   lambda m: {}),
        (r"date",                  "get_date",   lambda m: {}),
        (r"weather",               "weather",    lambda m: {}),
        (r"contacts",              "contacts",   lambda m: {}),
        (r"settings",              "open_settings", lambda m: {}),
        (r"note\s+(.*)",           "add_note",   lambda m: {"text": m.group(1).strip()}),
        (r"set\s*alarm\s*(\d{1,2}):?(\d{2})?",
         "set_alarm", lambda m: {"hour": int(m.group(1)), "minute": int(m.group(2) or "0")}),
        (r"activate\s+(.*)",       "activate_pro", lambda m: {"code": m.group(1).strip()}),
        (r"(help)",                "help",       lambda m: {}),
    ]

    def parse(self, text: str) -> tuple[str, dict]:
        t = text.strip().lower()
        for pattern, action, extractor in (self._RULES_FA + self._RULES_EN):
            m = re.search(pattern, t)
            if m:
                try:
                    params = extractor(m)
                except Exception:
                    params = {}
                return action, params
        return "unknown", {"raw": text}


# ================================================================
#  Main Controller
# ================================================================

class Controller:
    """
    Receives parsed commands and dispatches them to device APIs.
    Calls speak_fn to give voice feedback.
    """

    # App name → package
    _APP_MAP = {
        "تلگرام":       "org.telegram.messenger",
        "واتساپ":       "com.whatsapp",
        "اینستاگرام":  "com.instagram.android",
        "یوتیوب":       "com.google.android.youtube",
        "دوربین":       "com.android.camera2",
        "مخاطبین":     "com.android.contacts",
        "تماس":         "com.android.dialer",
        "پیام":         "com.android.mms",
        "تنظیمات":     "com.android.settings",
        "telegram":     "org.telegram.messenger",
        "whatsapp":     "com.whatsapp",
        "instagram":    "com.instagram.android",
        "youtube":      "com.google.android.youtube",
        "camera":       "com.android.camera2",
        "contacts":     "com.android.contacts",
        "settings":     "com.android.settings",
        "chrome":       "com.android.chrome",
        "maps":         "com.google.android.apps.maps",
        "spotify":      "com.spotify.music",
    }

    def __init__(self, speak_fn):
        self._speak   = speak_fn
        self._parser  = CommandParser()
        self._bridge  = AndroidBridge()
        self._alarms  = AlarmManager(speak_fn)

    # ---- public entry point ------------------------------------
    def handle(self, text: str) -> str:
        action, params = self._parser.parse(text)
        handler = getattr(self, f"_do_{action}", self._do_unknown)
        result  = handler(params)
        self._log(text, action, result)
        return result

    # ---- action handlers ----------------------------------------
    def _do_open_app(self, params: dict) -> str:
        target = params.get("target", "").lower()
        pkg    = self._APP_MAP.get(target, target)
        ok     = AndroidBridge.open_app(pkg)
        if ok:
            msg = f"{target} رو باز کردم."
        else:
            msg = f"نتونستم {target} رو باز کنم."
        self._speak(msg)
        return msg

    def _do_call(self, params: dict) -> str:
        if not _is_pro():
            msg = "برای تماس گرفتن به نسخه پرو نیاز داری."
            self._speak(msg); return msg
        target = params.get("target", "")
        # Try to resolve name → number from contacts
        contacts = AndroidBridge.list_contacts()
        number   = target
        for c in contacts:
            if target in c.get("name", "").lower():
                number = c["phone"]; break
        ok  = AndroidBridge.make_call(number)
        msg = f"در حال تماس با {target} …" if ok else f"تماس با {target} ممکن نشد."
        self._speak(msg)
        return msg

    def _do_sms(self, params: dict) -> str:
        if not _is_pro():
            msg = "ارسال پیام نیاز به نسخه پرو داره."
            self._speak(msg); return msg
        target = params.get("target", "")
        self._speak(f"متن پیام برای {target} رو بگو.")
        # In real app, voice.py listen_for_command() is called here via callback
        msg = f"پیام به {target} ارسال می‌شه."
        self._speak(msg)
        return msg

    def _do_volume_up(self, params: dict) -> str:
        AndroidBridge.set_volume(3, 80)   # STREAM_MUSIC
        msg = "صدا رو بردم بالا."
        self._speak(msg); return msg

    def _do_volume_down(self, params: dict) -> str:
        AndroidBridge.set_volume(3, 30)
        msg = "صدا رو بردم پایین."
        self._speak(msg); return msg

    def _do_mute(self, params: dict) -> str:
        AndroidBridge.set_volume(3, 0)
        msg = "صدا رو قطع کردم."
        self._speak(msg); return msg

    def _do_brightness_up(self, params: dict) -> str:
        AndroidBridge.set_brightness(220)
        msg = "روشنایی رو زیاد کردم."
        self._speak(msg); return msg

    def _do_brightness_down(self, params: dict) -> str:
        AndroidBridge.set_brightness(60)
        msg = "روشنایی رو کم کردم."
        self._speak(msg); return msg

    def _do_battery(self, params: dict) -> str:
        level = AndroidBridge.get_battery_level()
        msg   = f"باتری الان {level} درصد هست." if level >= 0 else "نتونستم باتری رو بخونم."
        self._speak(msg); return msg

    def _do_get_time(self, params: dict) -> str:
        now = datetime.now()
        msg = f"ساعت الان {now.strftime('%H:%M')} هست."
        self._speak(msg); return msg

    def _do_get_date(self, params: dict) -> str:
        now = datetime.now()
        msg = f"امروز {now.strftime('%Y/%m/%d')} هست."
        self._speak(msg); return msg

    def _do_weather(self, params: dict) -> str:
        msg = "برای آب‌وهوا به اینترنت نیاز دارم. لطفاً مطمئن شو متصلی."
        self._speak(msg); return msg

    def _do_contacts(self, params: dict) -> str:
        if not _is_pro():
            msg = "دسترسی به مخاطبین نیاز به نسخه پرو داره."
            self._speak(msg); return msg
        contacts = AndroidBridge.list_contacts()
        count = len(contacts)
        msg   = f"{count} مخاطب پیدا کردم."
        self._speak(msg)
        return msg

    def _do_add_note(self, params: dict) -> str:
        text = params.get("text", "")
        data = _load_json(MEMORY)
        data.setdefault("notes", []).append({
            "text": text, "time": datetime.now().isoformat()})
        _save_json(MEMORY, data)
        msg = f"یادداشتت رو ذخیره کردم: {text}"
        self._speak(msg); return msg

    def _do_set_alarm(self, params: dict) -> str:
        hour   = params.get("hour", 7)
        minute = params.get("minute", 0)
        self._alarms.add(hour, minute)
        msg = f"آلارم برای {hour}:{minute:02d} تنظیم شد."
        self._speak(msg); return msg

    def _do_open_settings(self, params: dict) -> str:
        # Signal to UI layer via a known return value
        msg = "تنظیمات رو باز می‌کنم."
        self._speak(msg)
        return "ACTION:OPEN_SETTINGS"

    def _do_activate_pro(self, params: dict) -> str:
        code     = params.get("code", "").strip()
        lic_data = _load_json(LICENSE)
        if code in lic_data.get("pro_codes", []):
            s = _load_json(SETTINGS)
            s["is_pro"] = True
            _save_json(SETTINGS, s)
            msg = "🎉 نسخه پرو فعال شد! به همه امکانات دسترسی داری."
        else:
            msg = "کد نامعتبر بود. دوباره امتحان کن."
        self._speak(msg); return msg

    def _do_help(self, params: dict) -> str:
        msg = (
            "می‌تونم برنامه باز کنم، زنگ بزنم، پیام بفرستم، "
            "آلارم تنظیم کنم، صدا و روشنایی رو تغییر بدم، "
            "یادداشت بنویسم و اطلاعات سیستم رو بگم."
        )
        self._speak(msg); return msg

    def _do_unknown(self, params: dict) -> str:
        raw = params.get("raw", "")
        msg = f"متوجه نشدم: '{raw}'. لطفاً دوباره بگو."
        self._speak(msg); return msg

    # ---- logging -----------------------------------------------
    def _log(self, text: str, action: str, result: str) -> None:
        data = _load_json(CMD_LOG)
        data.setdefault("logs", []).append({
            "timestamp": datetime.now().isoformat(),
            "input":     text,
            "action":    action,
            "result":    result,
        })
        _save_json(CMD_LOG, data)


# ================================================================
if __name__ == "__main__":
    def fake_speak(t): print(f"[SPEAK] {t}")

    ctrl = Controller(fake_speak)
    tests = [
        "باز کن تلگرام",
        "ساعت چنده",
        "باتری",
        "صدا رو ببر بالا",
        "یادداشت بنویس خرید نان و شیر",
        "activate M.ELZHOTS",
        "open youtube",
    ]
    for cmd in tests:
        print(f"\n>> '{cmd}'")
        ctrl.handle(cmd)
