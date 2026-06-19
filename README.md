# 🤖 ELZ Assistant — دستیار هوشمند Iron Man



---

## ساختار پروژه

```
ELZHOTS/
├── python/
│   ├── main.py          ← برنامه اصلی Kivy (UI کامل)
│   ├── voice.py         ← موتور صدا (TTS + STT + wake-word)
│   └── control.py       ← پردازش دستورات + کنترل دستگاه
├── cpp/
│   ├── voice_processor.cpp    ← پردازش صدای NDK
│   ├── system_controller.cpp  ← عملیات سیستمی NDK
│   └── CMakeLists.txt         ← تنظیمات build C++
├── json/
│   ├── users.json        ← اطلاعات کاربران
│   ├── settings.json     ← تنظیمات دستیار
│   ├── license.json      ← کدهای PRO
│   ├── memory.json       ← یادداشت، آلارم، یادآوری
│   └── command_log.json  ← لاگ دستورات
├── buildozer.spec        ← تنظیمات build APK اندروید
└── requirements.txt      ← وابستگی‌های Python
```

---

## مراحل اولیه (هنگام باز کردن برنامه)

1. **Splash / Boot** — انیمیشن راه‌اندازی با تم Iron Man
2. **درخواست مجوز** — میکروفون، مخاطبین، تماس، پیام، ذخیره‌سازی
3. **ثبت‌نام / ورود** — اطلاعات در `users.json` با رمز SHA-256 ذخیره می‌شه
4. **راه‌اندازی موتور صدا** — آماده شنیدن wake-word
5. **صفحه اصلی** — آماده دریافت دستور

---

## فعال‌سازی نسخه PRO

```
کد فعال‌سازی:  M.ELZHOTS
```

روش‌های فعال‌سازی:
- **صدایی:** بگو `activate M.ELZHOTS`
- **متنی:** در صفحه اصلی تایپ کن `activate M.ELZHOTS`
- **تنظیمات:** ⚙ → فیلد فعال‌سازی → وارد کن → دکمه فعال‌سازی

### امکانات PRO
| ویژگی | رایگان | PRO |
|-------|--------|-----|
| دستور صوتی | ✓ | ✓ |
| باز کردن برنامه | ✓ | ✓ |
| آلارم + یادداشت | ✓ | ✓ |
| تماس گرفتن | ✗ | ✓ |
| ارسال پیام | ✗ | ✓ |
| دسترسی مخاطبین | ✗ | ✓ |
| کنترل بلوتوث/وای‌فای | ✗ | ✓ |
| اطلاعات پیشرفته سیستم | ✗ | ✓ |

---

## دستورات پشتیبانی شده

### فارسی
| دستور | عملکرد |
|-------|---------|
| `باز کن تلگرام` | باز کردن برنامه |
| `زنگ بزن [نام]` | تماس (PRO) |
| `پیام بده [نام]` | پیام (PRO) |
| `صدا رو ببر بالا/پایین` | کنترل صدا |
| `روشنایی رو زیاد/کم کن` | کنترل نور |
| `باتری` | سطح باتری |
| `ساعت چنده` | ساعت |
| `آلارم بذار ۷:۳۰` | آلارم |
| `یادداشت بنویس ...` | یادداشت |
| `activate M.ELZHOTS` | فعال PRO |

### English
| Command | Action |
|---------|--------|
| `open youtube` | Launch app |
| `call [name]` | Make call (PRO) |
| `volume up/down` | Volume control |
| `battery` | Battery level |
| `set alarm 7:30` | Set alarm |
| `note buy milk` | Save note |

---

## Build برای اندروید

### پیش‌نیازها
```bash
pip install buildozer
sudo apt install -y build-essential git python3-dev \
  libffi-dev libssl-dev libbz2-dev zlib1g-dev
```

### ساخت APK
```bash
# اولین build (دانلود Android SDK/NDK - زمان‌بر)
buildozer android debug

# نصب روی دستگاه متصل
buildozer android deploy run
```

### فایل APK
پس از build موفق در `bin/` پیدا می‌شه:
```
bin/assistant-1.0.0-arm64-v8a-debug.apk
```

---

## اجرا روی کامپیوتر (توسعه)

```bash
cd python
pip install -r ../requirements.txt
python main.py
```

---

## JSON ها

| فایل | محتوا |
|------|-------|
| `users.json` | لیست کاربران با رمز هش‌شده |
| `settings.json` | همه تنظیمات دستیار |
| `license.json` | کدهای PRO و ویژگی‌های مجاز |
| `memory.json` | یادداشت، آلارم، یادآوری |
| `command_log.json` | تاریخچه کامل دستورات |

---

## معماری

```
                 ┌─────────────────┐
                 │   main.py (UI)  │
                 │   Kivy + KV     │
                 └────────┬────────┘
                          │
           ┌──────────────┴──────────────┐
           │                             │
    ┌──────▼──────┐             ┌────────▼───────┐
    │  voice.py   │             │  control.py     │
    │  Wake Word  │             │  Command Parser │
    │  STT / TTS  │             │  Device Bridge  │
    └──────┬──────┘             └────────┬────────┘
           │                             │
    ┌──────▼─────────────────────────────▼────────┐
    │         C++ NDK Libraries (JNI)              │
    │  voice_processor.cpp | system_controller.cpp │
    └──────────────────────────────────────────────┘
           │                             │
    ┌──────▼──────┐             ┌────────▼────────┐
    │  JSON Store │             │  Android APIs    │
    │  users      │             │  Contacts/SMS    │
    │  settings   │             │  Camera/Calls    │
    │  memory     │             │  Audio/Bright    │
    │  logs       │             │  Battery/WiFi    │
    └─────────────┘             └─────────────────┘
```
