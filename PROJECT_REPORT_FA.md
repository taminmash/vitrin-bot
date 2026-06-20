# گزارش بازبینی امنیتی و پاک‌سازی پروژه

## خلاصه

در این مرحله فقط تغییرات امنیتی و پاک‌سازی خواسته‌شده انجام شد. جریان مکالمه، منطق کسب‌وکار، stateها، callbackها و مسیرهای ثبت/تایید پیام تغییر نکردند.

## فایل‌های تغییرکرده

- `config.py`
- `database.py`
- `comment_handlers.py`
- `welcome.png` حذف شد
- `PROJECT_REPORT_FA.md` به‌روزرسانی شد و این گزارش جایگزین گزارش قدیمی شد

## موارد حساس پیدا شده

در اسکن پروژه این موارد پیدا شد:

- توکن واقعی ربات تلگرام به‌صورت fallback در `config.py`
- متغیر `DATABASE_URL` در `database.py`
- چاپ مستقیم `DATABASE_URL` در لاگ‌ها
- چاپ debug مربوط به post/comment در `database.py` و `comment_handlers.py`
- مقدارهای ثابت `ADMIN_ID`
- مقدارهای ثابت `CHANNEL_VITRIN` و `CHANNEL_HAYAT`
- لینک‌های ثابت کانال‌ها

## تغییرات امنیتی انجام‌شده

### حذف توکن hard-code شده

توکن fallback از `config.py` حذف شد. از این به بعد ربات فقط از متغیر محیطی `BOT_TOKEN` استفاده می‌کند.

قبل:

```python
BOT_TOKEN = os.environ.get("BOT_TOKEN", "<hard-coded token removed>")
```

بعد:

```python
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Missing required environment variable: BOT_TOKEN")
```

دلیل حذف: توکن ربات یک secret واقعی است و نباید در repository ذخیره شود. پیشنهاد امنیتی: توکن قبلی باید در BotFather revoke شود، چون قبلا داخل کد بوده است.

### اعتبارسنجی متغیرهای محیطی ضروری

برای `BOT_TOKEN` و `DATABASE_URL` validation اضافه شد. اگر هرکدام موجود نباشند، برنامه در زمان startup با خطای واضح متوقف می‌شود.

برای دیتابیس اکنون:

```python
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Missing required environment variable: DATABASE_URL")
```

دلیل: قبلا نبودن `DATABASE_URL` باعث خطای مبهم `psycopg2.connect(None)` می‌شد.

### حذف چاپ secrets و داده‌های حساس

از `database.py` این مورد حذف شد:

```python
print("DATABASE_URL =", DATABASE_URL)
```

دلیل: `DATABASE_URL` معمولا شامل username، password، host و نام دیتابیس است و نباید در لاگ‌ها چاپ شود.

همچنین debug printهای مربوط به دریافت کامنت‌ها و post id از `database.py` و `comment_handlers.py` حذف شدند. این تغییر رفتار ربات را عوض نمی‌کند، فقط خروجی لاگ را تمیزتر و امن‌تر می‌کند.

## پاک‌سازی فایل استفاده‌نشده

فایل `welcome.png` حذف شد.

دلیل: در هیچ‌کدام از فایل‌های اجرایی پروژه به آن reference وجود نداشت و در `/start` یا جای دیگری استفاده نمی‌شد. حذف آن باعث تغییر رفتار ربات نمی‌شود.

## مواردی که عمدا تغییر نکردند

برای حفظ رفتار فعلی ربات، این مقدارها همچنان در `config.py` ثابت مانده‌اند:

- `ADMIN_ID = 8747305714`
- `CHANNEL_VITRIN = -1003945260173`
- `CHANNEL_HAYAT = -1003854428039`
- `CHANNEL_VITRIN_LINK = "t.me/vitrinspain"`
- `CHANNEL_HAYAT_LINK = "t.me/hayatkhalvatspain"`

این‌ها secret در سطح توکن یا credential دیتابیس نیستند، اما شناسه‌ها و تنظیمات حساس عملیاتی محسوب می‌شوند. اگر تایید بدهید، در مرحله بعد می‌توان آن‌ها را هم به متغیرهای محیطی منتقل کرد؛ این کار نیازمند تنظیم env در محیط deploy است و به همین دلیل در این مرحله انجام نشد تا رفتار و اجرای فعلی ناخواسته نشکند.

## وضعیت secrets بعد از تغییرات

نتیجه اسکن بعد از تغییرات:

- هیچ Telegram bot token با الگوی رایج `number:token` در repository پیدا نشد.
- هیچ مقدار hard-code شده‌ای برای `DATABASE_URL` پیدا نشد.
- هیچ چاپ مستقیم `DATABASE_URL` در کد اجرایی باقی نمانده است.
- فایل `welcome.png` دیگر در لیست فایل‌های پروژه نیست.
- مقدارهای ثابت `ADMIN_ID` و شناسه کانال‌ها همچنان باقی هستند، چون تغییر آن‌ها به env می‌تواند behavior/deployment فعلی را تغییر دهد و خارج از محدوده تغییرات تاییدشده بود.

## نکته مهم خارج از محدوده این تغییر

در `comment_handlers.py` از قبل یک مشکل ساختاری دیده می‌شود: چند خط انتهای فایل ظاهرا بیرون از تابع `save_comment` قرار دارند و شامل `await` در سطح فایل هستند. این مورد می‌تواند باعث خطای import شود. چون درخواست فعلی صراحتا گفته بود فقط security fixes و cleanup انجام شود و منطق/رفتار تغییر نکند، این باگ را در این مرحله اصلاح نکردم و برای تغییر بعدی منتظر تایید شما می‌مانم.
