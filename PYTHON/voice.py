"""
=============================================================
  ELZ Assistant - Voice Engine
  File: voice.py
  Purpose: Wake-word detection, speech recognition, TTS
           All audio I/O for the ELZ assistant on Android
=============================================================
"""

import os
import json
import time
import threading
import queue
import re
from datetime import datetime
from pathlib import Path

# Android / Kivy-compatible imports (fallback for desktop dev)
try:
    from android.permissions import request_permissions, Permission          # type: ignore
    from jnius import autoclass                                              # type: ignore
    IS_ANDROID = True
except ImportError:
    IS_ANDROID = False

# TTS engine
try:
    import pyttsx3                                                           # type: ignore
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

# Speech Recognition
try:
    import speech_recognition as sr                                          # type: ignore
    HAS_SR = True
except ImportError:
    HAS_SR = False

# ----------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent.parent
JSON_DIR    = BASE_DIR / "json"
SETTINGS    = JSON_DIR / "settings.json"
CMD_LOG     = JSON_DIR / "command_log.json"


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


# ================================================================
class TTSEngine:
    """Text-to-Speech wrapper (Android TTS or pyttsx3)."""

    def __init__(self, settings: dict):
        self._settings  = settings
        self._lock      = threading.Lock()
        self._engine    = None
        self._android_tts = None
        self._init()

    def _init(self):
        if IS_ANDROID:
            try:
                TTS = autoclass("android.speech.tts.TextToSpeech")
                ctx = autoclass("org.kivy.android.PythonActivity").mActivity
                self._android_tts = TTS(ctx, None)
                import time; time.sleep(0.5)
            except Exception as e:
                print(f"[TTS] Android init failed: {e}")
        elif HAS_PYTTSX3:
            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate",
                    int(150 * self._settings.get("voice_speed", 1.0)))
                self._engine.setProperty("pitch",
                    int(100 * self._settings.get("voice_pitch", 1.0)))
            except Exception as e:
                print(f"[TTS] pyttsx3 init failed: {e}")

    def speak(self, text: str) -> None:
        """Speak text asynchronously."""
        def _do():
            with self._lock:
                if IS_ANDROID and self._android_tts:
                    try:
                        from jnius import autoclass as ac
                        Bundle = ac("android.os.Bundle")
                        self._android_tts.speak(
                            text, 0,   # QUEUE_FLUSH
                            None, "elz_utt_" + str(int(time.time()))
                        )
                    except Exception as e:
                        print(f"[TTS] speak error: {e}")
                elif self._engine:
                    try:
                        self._engine.say(text)
                        self._engine.runAndWait()
                    except Exception as e:
                        print(f"[TTS] pyttsx3 speak error: {e}")
                else:
                    print(f"[TTS] (no engine) >> {text}")

        threading.Thread(target=_do, daemon=True).start()

    def stop(self) -> None:
        if IS_ANDROID and self._android_tts:
            try:
                self._android_tts.stop()
            except Exception:
                pass
        elif self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass


# ================================================================
class WakeWordDetector:
    """
    Listens for the configured wake-word ("hi elz" by default).
    On Android uses SpeechRecognizer; on desktop uses speech_recognition.
    """

    def __init__(self, wake_word: str, on_detected_callback, language: str = "fa-IR"):
        self._wake_word  = wake_word.lower().strip()
        self._callback   = on_detected_callback
        self._language   = language
        self._running    = False
        self._thread     = None

    # ---- public ------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print(f"[WakeWord] Listening for '{self._wake_word}' …")

    def stop(self) -> None:
        self._running = False

    # ---- private -----------------------------------------------
    def _listen_loop(self):
        if HAS_SR:
            recognizer = sr.Recognizer()
            recognizer.energy_threshold       = 300
            recognizer.dynamic_energy_threshold = True
            with sr.Microphone(sample_rate=16000) as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                while self._running:
                    try:
                        audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)
                        text  = recognizer.recognize_google(
                            audio, language=self._language).lower()
                        print(f"[WakeWord] heard: '{text}'")
                        if self._wake_word in text:
                            self._callback(text)
                    except sr.WaitTimeoutError:
                        pass
                    except sr.UnknownValueError:
                        pass
                    except Exception as e:
                        print(f"[WakeWord] error: {e}")
                        time.sleep(1)
        else:
            # Simulated mode for environments without mic
            print("[WakeWord] speech_recognition not available – simulation mode")
            while self._running:
                time.sleep(60)


# ================================================================
class SpeechRecognizer:
    """One-shot speech recognition after wake word fires."""

    def __init__(self, language: str = "fa-IR"):
        self._language = language
        if HAS_SR:
            self._rec = sr.Recognizer()
            self._rec.energy_threshold        = 250
            self._rec.dynamic_energy_threshold = True
        else:
            self._rec = None

    def listen_once(self, timeout: int = 8) -> str:
        """Capture one utterance and return text (or empty string)."""
        if not self._rec:
            return ""
        try:
            with sr.Microphone(sample_rate=16000) as source:
                self._rec.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._rec.listen(source, timeout=timeout, phrase_time_limit=10)
            text = self._rec.recognize_google(audio, language=self._language)
            print(f"[STT] recognized: '{text}'")
            return text
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            return ""
        except Exception as e:
            print(f"[STT] error: {e}")
            return ""


# ================================================================
class VoiceEngine:
    """
    Top-level voice engine.

    Lifecycle
    ---------
    1. start()          – boots wake-word detector
    2. <wake word heard> – plays greeting, starts command listener
    3. command received  – calls on_command_callback(text)
    4. stop()           – shuts everything down
    """

    # Greeting messages (Farsi + English)
    _GREETINGS = [
        "سلام، من ELZ هستم. چطور می‌تونم کمکت کنم؟",
        "سلام! ELZ در خدمته. بفرمایید.",
        "Hello! ELZ is ready. How can I help you?",
    ]

    def __init__(self, on_command_callback=None):
        self._settings   = _load_json(SETTINGS)
        self._language   = self._settings.get("language", "fa")
        self._wake_word  = self._settings.get("wake_word", "hi elz").lower()
        self._on_command = on_command_callback or (lambda text: print(f"[CMD] {text}"))

        lang_code = "fa-IR" if self._language == "fa" else "en-US"
        self._tts      = TTSEngine(self._settings)
        self._wwd      = WakeWordDetector(self._wake_word, self._on_wake, lang_code)
        self._stt      = SpeechRecognizer(lang_code)
        self._active   = False          # True when in command-taking mode
        self._cmd_queue: queue.Queue = queue.Queue()

    # ---- public ------------------------------------------------
    def start(self) -> None:
        print("[VoiceEngine] Starting …")
        self._wwd.start()

    def stop(self) -> None:
        print("[VoiceEngine] Stopping …")
        self._wwd.stop()
        self._tts.stop()

    def speak(self, text: str) -> None:
        self._tts.speak(text)

    def listen_for_command(self) -> str:
        """Block until one command utterance is captured."""
        return self._stt.listen_once()

    def reload_settings(self) -> None:
        self._settings  = _load_json(SETTINGS)
        self._wake_word = self._settings.get("wake_word", "hi elz").lower()

    # ---- callbacks --------------------------------------------
    def _on_wake(self, heard_text: str) -> None:
        print(f"[VoiceEngine] Wake word detected in: '{heard_text}'")
        greeting = self._GREETINGS[0]
        self._tts.speak(greeting)
        self._log_event("wake_word", heard_text)

        # Start command capture in a new thread
        threading.Thread(target=self._capture_command, daemon=True).start()

    def _capture_command(self) -> None:
        time.sleep(2.0)   # wait for greeting TTS to finish
        command = self._stt.listen_once(timeout=10)
        if command:
            self._log_event("command", command)
            self._on_command(command)
        else:
            self._tts.speak("متوجه نشدم، لطفاً دوباره بگو.")

    # ---- logging -----------------------------------------------
    def _log_event(self, event_type: str, text: str) -> None:
        data = _load_json(CMD_LOG)
        if "logs" not in data:
            data["logs"] = []
        data["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "type":      event_type,
            "text":      text,
        })
        _save_json(CMD_LOG, data)


# ================================================================
#  Module-level convenience helpers
# ================================================================

_global_engine: VoiceEngine | None = None


def get_engine(on_command=None) -> VoiceEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = VoiceEngine(on_command)
    return _global_engine


def speak(text: str) -> None:
    get_engine().speak(text)


def start_listening(on_command=None) -> None:
    get_engine(on_command).start()


def stop_listening() -> None:
    if _global_engine:
        _global_engine.stop()


# ================================================================
if __name__ == "__main__":
    def handle_command(text):
        print(f"[DEMO] Command received: {text}")

    engine = VoiceEngine(on_command_callback=handle_command)
    engine.start()
    engine.speak("سلام ای ال زی آماده است")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        engine.stop()
