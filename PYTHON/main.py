"""
=============================================================
  ELZ Assistant - Main Application (Kivy / Android)
  File: main.py
  Purpose: Full Iron Man themed UI with:
    - Splash / boot sequence
    - Login / Register screens
    - Main assistant screen with waveform
    - Settings screen
    - Pro activation
=============================================================
"""

import os
import json
import time
import threading
import hashlib
from datetime import datetime
from pathlib import Path

# ---- Kivy setup before imports --------------------------------
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.uix.slider import Slider
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.graphics import (Color, Rectangle, Ellipse, Line,
                            RoundedRectangle, Canvas)
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.properties import (NumericProperty, StringProperty,
                              BooleanProperty, ListProperty)
from kivy.lang import Builder

# Local modules
import sys
sys.path.insert(0, str(Path(__file__).parent))
from control import Controller
from voice import VoiceEngine

# ----------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = BASE_DIR / "json"
SETTINGS = JSON_DIR / "settings.json"
USERS_DB = JSON_DIR / "users.json"
LICENSE  = JSON_DIR / "license.json"

# ---- Iron Man palette -----------------------------------------
CLR_BG      = (0.04, 0.04, 0.04, 1)        # near-black
CLR_PRIMARY = (1.0,  0.42, 0.0,  1)        # Iron Man orange
CLR_GOLD    = (1.0,  0.84, 0.0,  1)        # gold accent
CLR_DARK    = (0.08, 0.08, 0.08, 1)
CLR_PANEL   = (0.1,  0.1,  0.12, 1)
CLR_RED     = (0.9,  0.1,  0.1,  1)
CLR_TEXT    = (1.0,  0.42, 0.0,  1)
CLR_WHITE   = (1,    1,    1,    1)
CLR_GREY    = (0.5,  0.5,  0.5,  1)

Window.clearcolor = CLR_BG[:3] + (1,)


# ================================================================
#  Helpers
# ================================================================

def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    try:
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def _is_pro() -> bool:
    return _load_json(SETTINGS).get("is_pro", False)


# ================================================================
#  KV String (styles)
# ================================================================

KV = """
<ElzButton@Button>:
    background_color: 0, 0, 0, 0
    background_normal: ''
    color: 1, 0.42, 0, 1
    font_size: sp(16)
    bold: True
    canvas.before:
        Color:
            rgba: 0.15, 0.15, 0.15, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]
        Color:
            rgba: 1, 0.42, 0, 0.9
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(8)]
            width: 1.2

<ElzLabel@Label>:
    color: 1, 0.42, 0, 1
    font_size: sp(14)

<ElzInput@TextInput>:
    background_color: 0.1, 0.1, 0.12, 1
    foreground_color: 1, 0.84, 0, 1
    cursor_color: 1, 0.42, 0, 1
    hint_text_color: 0.5, 0.5, 0.5, 1
    font_size: sp(15)
    padding: dp(12), dp(10)
    multiline: False
    canvas.before:
        Color:
            rgba: 1, 0.42, 0, 0.7
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(6)]
            width: 1
"""

Builder.load_string(KV)


# ================================================================
#  Waveform Widget
# ================================================================

class WaveformWidget(Widget):
    amplitude = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._bars   = 32
        self._values = [0.0] * self._bars
        Clock.schedule_interval(self._update, 1 / 30)

    def set_amplitude(self, v: float):
        self.amplitude = max(0.0, min(1.0, v))

    def _update(self, dt):
        # Shift left, add new value
        self._values.pop(0)
        import random
        if self.amplitude > 0.05:
            self._values.append(self.amplitude * (0.6 + random.random() * 0.4))
        else:
            self._values.append(max(0, self._values[-1] * 0.7 - 0.02))
        self.canvas.clear()
        with self.canvas:
            Color(*CLR_PRIMARY)
            bar_w = self.width / (self._bars * 1.5)
            gap   = bar_w * 0.5
            for i, val in enumerate(self._values):
                x = self.x + i * (bar_w + gap)
                h = max(dp(3), val * self.height * 0.9)
                y = self.y + (self.height - h) / 2
                RoundedRectangle(pos=(x, y), size=(bar_w, h), radius=[dp(3)])


# ================================================================
#  Boot / Splash Screen
# ================================================================

class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = FloatLayout()

        # Background
        with self.canvas.before:
            Color(*CLR_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Arc decoration
        with layout.canvas:
            Color(*CLR_PRIMARY[:3], 0.3)
            Line(circle=(Window.width/2, Window.height/2, dp(120)), width=dp(2))
            Line(circle=(Window.width/2, Window.height/2, dp(90)),  width=dp(1))

        # Logo label
        self.logo = Label(
            text="[b]ELZ[/b]",
            markup=True,
            font_size=sp(56),
            color=CLR_PRIMARY,
            pos_hint={"center_x": 0.5, "center_y": 0.58},
            size_hint=(1, None),
            height=dp(80),
        )
        layout.add_widget(self.logo)

        self.subtitle = Label(
            text="INTELLIGENT ASSISTANT",
            font_size=sp(13),
            color=CLR_GOLD,
            pos_hint={"center_x": 0.5, "center_y": 0.48},
            size_hint=(1, None),
            height=dp(30),
        )
        layout.add_widget(self.subtitle)

        self.status = Label(
            text="INITIALIZING SYSTEMS …",
            font_size=sp(11),
            color=CLR_GREY,
            pos_hint={"center_x": 0.5, "center_y": 0.35},
            size_hint=(1, None),
            height=dp(24),
        )
        layout.add_widget(self.status)

        self.add_widget(layout)
        Clock.schedule_once(self._boot_sequence, 0.5)

    def _update_bg(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def _boot_sequence(self, *_):
        steps = [
            (0.8,  "LOADING VOICE ENGINE …"),
            (1.6,  "SCANNING PERMISSIONS …"),
            (2.4,  "CONNECTING MODULES …"),
            (3.2,  "BOOT COMPLETE ✓"),
        ]
        for delay, msg in steps:
            Clock.schedule_once(lambda dt, m=msg: setattr(self.status, "text", m), delay)
        Clock.schedule_once(self._go_to_login, 4.0)

    def _go_to_login(self, *_):
        self.manager.current = "login"


# ================================================================
#  Login Screen
# ================================================================

class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(30), spacing=dp(16))

        with self.canvas.before:
            Color(*CLR_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        layout.add_widget(Label(size_hint_y=0.05))

        layout.add_widget(Label(
            text="[b]ELZ[/b] ASSISTANT",
            markup=True, font_size=sp(32),
            color=CLR_PRIMARY, size_hint_y=None, height=dp(60)))

        layout.add_widget(Label(
            text="ورود به سیستم",
            font_size=sp(16), color=CLR_GOLD,
            size_hint_y=None, height=dp(30)))

        self.username = TextInput(
            hint_text="نام کاربری",
            background_color=(0.1, 0.1, 0.12, 1),
            foreground_color=(1, 0.84, 0, 1),
            cursor_color=(1, 0.42, 0, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(15),
            padding=(dp(12), dp(10)),
            multiline=False,
            size_hint_y=None, height=dp(48))
        layout.add_widget(self.username)

        self.password = TextInput(
            hint_text="رمز عبور",
            password=True,
            background_color=(0.1, 0.1, 0.12, 1),
            foreground_color=(1, 0.84, 0, 1),
            cursor_color=(1, 0.42, 0, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(15),
            padding=(dp(12), dp(10)),
            multiline=False,
            size_hint_y=None, height=dp(48))
        layout.add_widget(self.password)

        btn_login = Button(
            text="ورود",
            background_color=(1, 0.42, 0, 1),
            color=(0, 0, 0, 1),
            bold=True,
            font_size=sp(16),
            size_hint_y=None, height=dp(50))
        btn_login.bind(on_press=self._login)
        layout.add_widget(btn_login)

        btn_reg = Button(
            text="ثبت‌نام",
            background_color=(0.1, 0.1, 0.12, 1),
            color=CLR_PRIMARY,
            font_size=sp(15),
            size_hint_y=None, height=dp(44))
        btn_reg.bind(on_press=lambda *_: setattr(self.manager, "current", "register"))
        layout.add_widget(btn_reg)

        self.msg_label = Label(
            text="", color=CLR_RED,
            font_size=sp(13), size_hint_y=None, height=dp(30))
        layout.add_widget(self.msg_label)

        layout.add_widget(Widget())
        self.add_widget(layout)

    def _login(self, *_):
        u = self.username.text.strip()
        p = self.password.text.strip()
        if not u or not p:
            self.msg_label.text = "لطفاً همه فیلدها رو پر کن."; return
        data = _load_json(USERS_DB)
        for user in data.get("users", []):
            if user["username"] == u and user["password"] == _hash_password(p):
                App.get_running_app().current_user = user
                self.manager.current = "main"
                self.msg_label.text = ""
                return
        self.msg_label.text = "نام کاربری یا رمز اشتباهه."


# ================================================================
#  Register Screen
# ================================================================

class RegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(30), spacing=dp(14))

        with self.canvas.before:
            Color(*CLR_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        layout.add_widget(Label(size_hint_y=0.04))
        layout.add_widget(Label(
            text="[b]ثبت‌نام[/b]", markup=True,
            font_size=sp(28), color=CLR_PRIMARY,
            size_hint_y=None, height=dp(55)))

        fields = [
            ("نام کاربری", "username", False),
            ("رمز عبور",   "password", True),
            ("تکرار رمز",  "password2", True),
            ("ایمیل (اختیاری)", "email", False),
        ]
        self._inputs = {}
        for hint, key, is_pwd in fields:
            ti = TextInput(
                hint_text=hint,
                password=is_pwd,
                background_color=(0.1, 0.1, 0.12, 1),
                foreground_color=(1, 0.84, 0, 1),
                cursor_color=(1, 0.42, 0, 1),
                hint_text_color=(0.5, 0.5, 0.5, 1),
                font_size=sp(15),
                padding=(dp(12), dp(10)),
                multiline=False,
                size_hint_y=None, height=dp(46))
            self._inputs[key] = ti
            layout.add_widget(ti)

        btn = Button(
            text="ثبت‌نام",
            background_color=(1, 0.42, 0, 1),
            color=(0, 0, 0, 1),
            bold=True,
            font_size=sp(16),
            size_hint_y=None, height=dp(50))
        btn.bind(on_press=self._register)
        layout.add_widget(btn)

        btn_back = Button(
            text="← بازگشت",
            background_color=(0, 0, 0, 0),
            color=CLR_PRIMARY,
            font_size=sp(14),
            size_hint_y=None, height=dp(40))
        btn_back.bind(on_press=lambda *_: setattr(self.manager, "current", "login"))
        layout.add_widget(btn_back)

        self.msg = Label(text="", color=CLR_RED, font_size=sp(13),
                         size_hint_y=None, height=dp(30))
        layout.add_widget(self.msg)
        layout.add_widget(Widget())
        self.add_widget(layout)

    def _register(self, *_):
        u  = self._inputs["username"].text.strip()
        p1 = self._inputs["password"].text.strip()
        p2 = self._inputs["password2"].text.strip()
        em = self._inputs["email"].text.strip()
        if not u or not p1:
            self.msg.text = "نام کاربری و رمز الزامیه."; return
        if p1 != p2:
            self.msg.text = "رمزها مطابقت ندارن."; return
        data = _load_json(USERS_DB)
        for usr in data.get("users", []):
            if usr["username"] == u:
                self.msg.text = "این نام کاربری قبلاً ثبت شده."; return
        data.setdefault("users", []).append({
            "username": u,
            "password": _hash_password(p1),
            "email":    em,
            "created":  datetime.now().isoformat(),
            "is_pro":   False,
        })
        _save_json(USERS_DB, data)
        self.msg.text = "✓ ثبت‌نام موفق! وارد شو."
        self.msg.color = (0, 0.8, 0, 1)


# ================================================================
#  Main Assistant Screen
# ================================================================

class MainScreen(Screen):
    is_listening = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ctrl   = None
        self._voice  = None
        self._build_ui()
        Clock.schedule_once(self._init_engines, 0.5)

    def _build_ui(self):
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        with self.canvas.before:
            Color(*CLR_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        # ---- Top bar ----------------------------------------
        top = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        self.title_lbl = Label(
            text="[b]ELZ[/b] ASSISTANT",
            markup=True,
            font_size=sp(20),
            color=CLR_PRIMARY)
        top.add_widget(self.title_lbl)

        self.pro_badge = Label(
            text="",
            font_size=sp(11),
            color=CLR_GOLD,
            size_hint_x=None, width=dp(60))
        top.add_widget(self.pro_badge)

        btn_settings = Button(
            text="⚙",
            background_color=(0.1, 0.1, 0.12, 1),
            color=CLR_PRIMARY,
            font_size=sp(20),
            size_hint_x=None, width=dp(44))
        btn_settings.bind(on_press=lambda *_: setattr(
            self.manager, "current", "settings"))
        top.add_widget(btn_settings)
        root.add_widget(top)

        # ---- Status label -----------------------------------
        self.status_lbl = Label(
            text="بگو  hi elz  تا شروع کنیم",
            font_size=sp(14),
            color=CLR_GREY,
            size_hint_y=None, height=dp(30))
        root.add_widget(self.status_lbl)

        # ---- Waveform ---------------------------------------
        self.waveform = WaveformWidget(size_hint_y=None, height=dp(90))
        root.add_widget(self.waveform)

        # ---- Log / output -----------------------------------
        scroll = ScrollView(size_hint=(1, 1))
        self.log_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=(dp(4), dp(4)))
        self.log_box.bind(minimum_height=self.log_box.setter("height"))
        scroll.add_widget(self.log_box)
        root.add_widget(scroll)

        # ---- Manual text input ------------------------------
        bottom = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        self.text_cmd = TextInput(
            hint_text="یا دستور بنویس …",
            background_color=(0.1, 0.1, 0.12, 1),
            foreground_color=(1, 0.84, 0, 1),
            cursor_color=(1, 0.42, 0, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(14),
            padding=(dp(10), dp(8)),
            multiline=False)
        bottom.add_widget(self.text_cmd)

        btn_send = Button(
            text="→",
            background_color=(1, 0.42, 0, 1),
            color=(0, 0, 0, 1),
            bold=True,
            font_size=sp(20),
            size_hint_x=None, width=dp(52))
        btn_send.bind(on_press=self._on_text_cmd)
        bottom.add_widget(btn_send)
        root.add_widget(bottom)

        self.add_widget(root)

    def _init_engines(self, *_):
        def _speak(text):
            Clock.schedule_once(lambda dt: self._add_log("ELZ", text, CLR_PRIMARY), 0)
            if self._voice:
                self._voice.speak(text)

        self._ctrl  = Controller(_speak)
        self._voice = VoiceEngine(on_command_callback=self._on_voice_command)
        self._voice.start()

        pro = _is_pro()
        self.pro_badge.text = "PRO ✓" if pro else ""
        self._add_log("ELZ", "سیستم آماده‌ست. بگو  hi elz !", CLR_GOLD)

    def _on_voice_command(self, text: str):
        Clock.schedule_once(lambda dt: self._handle_command(text), 0)

    def _on_text_cmd(self, *_):
        text = self.text_cmd.text.strip()
        if text:
            self.text_cmd.text = ""
            self._handle_command(text)

    def _handle_command(self, text: str):
        self._add_log("تو", text, CLR_GOLD)
        if self._ctrl:
            self._ctrl.handle(text)
        # waveform animation
        self.waveform.set_amplitude(0.8)
        Clock.schedule_once(lambda dt: self.waveform.set_amplitude(0), 1.5)

    def _add_log(self, sender: str, text: str, color):
        lbl = Label(
            text=f"[b]{sender}:[/b]  {text}",
            markup=True,
            font_size=sp(13),
            color=color,
            size_hint_y=None,
            text_size=(Window.width - dp(30), None),
            halign="right")
        lbl.bind(texture_size=lbl.setter("size"))
        self.log_box.add_widget(lbl)

    def on_enter(self):
        pro = _is_pro()
        self.pro_badge.text = "PRO ✓" if pro else ""


# ================================================================
#  Settings Screen
# ================================================================

class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()

    def _build_ui(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        with self.canvas.before:
            Color(*CLR_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        btn_back = Button(
            text="←",
            background_color=(0.1, 0.1, 0.12, 1),
            color=CLR_PRIMARY,
            font_size=sp(20),
            size_hint_x=None, width=dp(44))
        btn_back.bind(on_press=lambda *_: setattr(self.manager, "current", "main"))
        top.add_widget(btn_back)
        top.add_widget(Label(
            text="[b]تنظیمات[/b]", markup=True,
            font_size=sp(22), color=CLR_PRIMARY))
        root.add_widget(top)

        scroll = ScrollView()
        box = BoxLayout(orientation="vertical", spacing=dp(10),
                        size_hint_y=None, padding=(0, dp(4)))
        box.bind(minimum_height=box.setter("height"))

        s = _load_json(SETTINGS)

        # --- Wake word -----------------------------------------
        box.add_widget(self._section("کلمه بیدارسازی (wake word)"))
        self._wake_input = TextInput(
            text=s.get("wake_word", "hi elz"),
            background_color=(0.1, 0.1, 0.12, 1),
            foreground_color=(1, 0.84, 0, 1),
            cursor_color=(1, 0.42, 0, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(14),
            multiline=False,
            size_hint_y=None, height=dp(44))
        box.add_widget(self._wake_input)

        # --- Language ------------------------------------------
        box.add_widget(self._section("زبان دستیار"))
        lang_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self._lang_fa = self._toggle_btn("فارسی", s.get("language") == "fa",
                                         lambda *_: self._set_lang("fa"))
        self._lang_en = self._toggle_btn("English", s.get("language") == "en",
                                         lambda *_: self._set_lang("en"))
        lang_row.add_widget(self._lang_fa)
        lang_row.add_widget(self._lang_en)
        box.add_widget(lang_row)

        # --- Voice speed ---------------------------------------
        box.add_widget(self._section("سرعت صدا"))
        self._speed_slider = Slider(
            min=0.5, max=2.0,
            value=s.get("voice_speed", 1.0),
            size_hint_y=None, height=dp(40))
        box.add_widget(self._speed_slider)

        # --- Sound effects -------------------------------------
        box.add_widget(self._section("جلوه صوتی"))
        row_sfx = BoxLayout(size_hint_y=None, height=dp(44))
        row_sfx.add_widget(Label(text="فعال", color=CLR_TEXT, font_size=sp(14)))
        self._sw_sfx = Switch(active=s.get("sound_effects", True))
        row_sfx.add_widget(self._sw_sfx)
        box.add_widget(row_sfx)

        # --- Dark mode -----------------------------------------
        row_dm = BoxLayout(size_hint_y=None, height=dp(44))
        row_dm.add_widget(Label(text="حالت تاریک", color=CLR_TEXT, font_size=sp(14)))
        self._sw_dark = Switch(active=s.get("dark_mode", True))
        row_dm.add_widget(self._sw_dark)
        box.add_widget(row_dm)

        # --- Continuous listening ------------------------------
        row_cl = BoxLayout(size_hint_y=None, height=dp(44))
        row_cl.add_widget(Label(text="گوش‌دادن پیوسته", color=CLR_TEXT, font_size=sp(14)))
        self._sw_cl = Switch(active=s.get("continuous_listening", False))
        row_cl.add_widget(self._sw_cl)
        box.add_widget(row_cl)

        # --- Haptic --------------------------------------------
        row_hap = BoxLayout(size_hint_y=None, height=dp(44))
        row_hap.add_widget(Label(text="لرزش", color=CLR_TEXT, font_size=sp(14)))
        self._sw_hap = Switch(active=s.get("haptic_feedback", True))
        row_hap.add_widget(self._sw_hap)
        box.add_widget(row_hap)

        # --- Pro activation ------------------------------------
        box.add_widget(self._section("فعال‌سازی نسخه PRO"))
        self._pro_input = TextInput(
            hint_text="کد فعال‌سازی را وارد کن",
            background_color=(0.1, 0.1, 0.12, 1),
            foreground_color=(1, 0.84, 0, 1),
            cursor_color=(1, 0.42, 0, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(14),
            multiline=False,
            size_hint_y=None, height=dp(44))
        box.add_widget(self._pro_input)

        btn_activate = Button(
            text="فعال‌سازی PRO",
            background_color=(1, 0.42, 0, 1),
            color=(0, 0, 0, 1),
            bold=True,
            font_size=sp(15),
            size_hint_y=None, height=dp(48))
        btn_activate.bind(on_press=self._activate_pro)
        box.add_widget(btn_activate)

        self._pro_msg = Label(text="", color=CLR_GOLD,
                              font_size=sp(13), size_hint_y=None, height=dp(30))
        box.add_widget(self._pro_msg)

        # --- Save button ---------------------------------------
        btn_save = Button(
            text="ذخیره تنظیمات",
            background_color=(0, 0.5, 0, 1),
            color=(1, 1, 1, 1),
            bold=True,
            font_size=sp(16),
            size_hint_y=None, height=dp(52))
        btn_save.bind(on_press=self._save)
        box.add_widget(btn_save)

        box.add_widget(Widget(size_hint_y=None, height=dp(20)))
        scroll.add_widget(box)
        root.add_widget(scroll)
        self.add_widget(root)

    def _section(self, title: str) -> Label:
        return Label(
            text=f"[b]{title}[/b]",
            markup=True,
            font_size=sp(13),
            color=CLR_GOLD,
            size_hint_y=None, height=dp(28),
            halign="right",
            text_size=(Window.width - dp(32), None))

    def _toggle_btn(self, text, active, callback) -> Button:
        btn = Button(
            text=text,
            background_color=(1, 0.42, 0, 0.9) if active else (0.1, 0.1, 0.12, 1),
            color=(0, 0, 0, 1) if active else CLR_PRIMARY,
            font_size=sp(14))
        btn.bind(on_press=callback)
        return btn

    def _set_lang(self, lang):
        self._lang_fa.background_color = (1, 0.42, 0, 0.9) if lang == "fa" else (0.1, 0.1, 0.12, 1)
        self._lang_en.background_color = (1, 0.42, 0, 0.9) if lang == "en" else (0.1, 0.1, 0.12, 1)
        self._lang_fa.color = (0, 0, 0, 1) if lang == "fa" else CLR_PRIMARY
        self._lang_en.color = (0, 0, 0, 1) if lang == "en" else CLR_PRIMARY
        self._current_lang = lang

    def _activate_pro(self, *_):
        code     = self._pro_input.text.strip()
        lic_data = _load_json(LICENSE)
        if code in lic_data.get("pro_codes", []):
            s = _load_json(SETTINGS)
            s["is_pro"] = True
            _save_json(SETTINGS, s)
            self._pro_msg.text  = "✓ نسخه PRO فعال شد!"
            self._pro_msg.color = (0, 0.9, 0, 1)
        else:
            self._pro_msg.text  = "✗ کد نامعتبر"
            self._pro_msg.color = CLR_RED

    def _save(self, *_):
        s = _load_json(SETTINGS)
        s["wake_word"]            = self._wake_input.text.strip().lower()
        s["voice_speed"]          = round(self._speed_slider.value, 1)
        s["sound_effects"]        = self._sw_sfx.active
        s["dark_mode"]            = self._sw_dark.active
        s["continuous_listening"] = self._sw_cl.active
        s["haptic_feedback"]      = self._sw_hap.active
        if hasattr(self, "_current_lang"):
            s["language"] = self._current_lang
        _save_json(SETTINGS, s)

        popup = Popup(
            title="تنظیمات ذخیره شد",
            content=Label(text="✓", color=(0, 0.9, 0, 1), font_size=sp(32)),
            size_hint=(0.4, 0.3))
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 1.2)


# ================================================================
#  App
# ================================================================

class ELZApp(App):
    current_user = {}

    def build(self):
        sm = ScreenManager(transition=FadeTransition(duration=0.35))
        sm.add_widget(SplashScreen(name="splash"))
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(RegisterScreen(name="register"))
        sm.add_widget(MainScreen(name="main"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm

    def on_start(self):
        # Request Android permissions
        try:
            from android.permissions import request_permissions, Permission  # type: ignore
            request_permissions([
                Permission.RECORD_AUDIO,
                Permission.READ_CONTACTS,
                Permission.CALL_PHONE,
                Permission.SEND_SMS,
                Permission.WRITE_SETTINGS,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ])
        except ImportError:
            pass


if __name__ == "__main__":
    ELZApp().run()
