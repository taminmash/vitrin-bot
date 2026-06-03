#!/usr/bin/env python3
import asyncio
import json
import os
from datetime import datetime
from telegram import Bot
from config import BOT_TOKEN

# آی‌دی کانال‌ها
CHANNELS = [
    -1003945260173,  # کانال ویترین
    -1003854428039,  # کانال حیاط خلوت
]

# فایل برای ذخیره شماره روز جاری
DAY_FILE = "spanish_day.json"

# محتوای ۹۰ روز — روزی ۲ پست
LESSONS = [
    # ─── ماه ۱: پایه‌های زندگی ───

    # هفته ۱: معرفی و احوال‌پرسی
    """📍 روز ۱ — اولین قدم! 🇪🇸

¡Hola!
(بخون: اولا)

یعنی: سلام! 👋

💡 نکته جالب:
اسپانیایی‌ها علامت تعجب رو از اول جمله هم می‌نویسن ¡
خاصه نه؟ 😄

📲 t.me/vitrinspain""",

    """📍 روز ۱ — ادامه 🇪🇸

¡Adiós!
(بخون: آدیوس)

یعنی: خداحافظ! 👋

💡 کاربرد:
وقتی از مغازه یا جایی خارج میشی بگو ¡Adiós!
خیلی طبیعی‌تر از هیچی نگفتنه 😊

📲 t.me/vitrinspain""",

    """📍 روز ۲ — چطوری؟ 🇪🇸

¿Cómo estás?
(بخون: کومو استاس)

یعنی: حالت چطوره؟ 🙂

💡 جواب ساده:
Bien, gracias = خوبم، ممنون
(بخون: بیِن، گراسیاس)

📲 t.me/vitrinspain""",

    """📍 روز ۲ — ادامه 🇪🇸

¿Y tú?
(بخون: ای تو)

یعنی: تو چطور؟ 🙂

💡 مکالمه کامل:
- ¿Cómo estás? — حالت چطوره؟
- Bien, gracias. ¿Y tú? — خوبم، ممنون. تو چطور؟

📲 t.me/vitrinspain""",

    """📍 روز ۳ — اسمت چیه؟ 🇪🇸

¿Cómo te llamas?
(بخون: کومو ته یاماس)

یعنی: اسمت چیه؟ 👤

💡 جواب:
Me llamo Sara = اسمم ساراست
(بخون: مه یامو سارا)

📲 t.me/vitrinspain""",

    """📍 روز ۳ — ادامه 🇪🇸

Me llamo...
(بخون: مه یامو)

💡 ترجمه تحت‌اللفظی:
«صدام می‌کنن...»
نه «اسمم هست»!
اسپانیایی خلاقانه‌ست 😄

📲 t.me/vitrinspain""",

    """📍 روز ۴ — اهل کجایی؟ 🇪🇸

¿De dónde eres?
(بخون: ده دونده ارِس)

یعنی: اهل کجایی؟ 🌍

💡 جواب:
Soy de Irán = اهل ایرانم 🇮🇷

📲 t.me/vitrinspain""",

    """📍 روز ۴ — ادامه 🇪🇸

Soy de...
(بخون: سوی ده)

یعنی: اهل ... هستم

💡 مثال‌ها:
Soy de España = اهل اسپانیام 🇪🇸
Soy de Teherán = اهل تهرانم

📲 t.me/vitrinspain""",

    """📍 روز ۵ — چند سالته؟ 🇪🇸

¿Cuántos años tienes?
(بخون: کوانتوس آنیوس تیِنِس)

یعنی: چند سالته؟ 🎂

💡 جواب:
Tengo 30 años = سی سالمه
(بخون: تنگو تِرِئینتا آنیوس)

📲 t.me/vitrinspain""",

    """📍 روز ۵ — ادامه 🇪🇸

Tengo... años
(بخون: تنگو... آنیوس)

یعنی: ... سال دارم

💡 ترجمه تحت‌اللفظی:
«سال دارم» نه «سالمه»!
توی اسپانیایی سن رو «دارن» 😄

📲 t.me/vitrinspain""",

    """📍 روز ۶ — خوشحال شدم! 🇪🇸

Mucho gusto
(بخون: موچو گوستو)

یعنی: خوشحال شدم 🤝

💡 جواب:
Igualmente = منم همینطور
(بخون: ایگوالمنته)

📲 t.me/vitrinspain""",

    """📍 روز ۶ — ادامه 🇪🇸

Encantado / Encantada
(بخون: اِنکانتادو / اِنکانتادا)

یعنی: خوشوقتم (مؤدبانه‌تر) 🤝

💡 نکته:
مرد بگه: Encantado
زن بگه: Encantada

📲 t.me/vitrinspain""",

    """📍 روز ۷ — مرور هفته اول 🎉

این هفته یاد گرفتی:
✅ ¡Hola! / ¡Adiós!
✅ ¿Cómo estás? / Bien
✅ ¿Cómo te llamas? / Me llamo...
✅ ¿De dónde eres? / Soy de...
✅ ¿Cuántos años tienes? / Tengo...
✅ Mucho gusto / Igualmente

💪 یه هفته، ۶ مکالمه واقعی!

📲 t.me/vitrinspain""",

    """📍 روز ۷ — چالش هفته اول 🎯

خودت رو به اسپانیایی معرفی کن:

¡Hola! Me llamo [اسم].
Soy de Irán. Tengo [سن] años.
Mucho gusto! 😊

این جمله رو حفظ کن — همیشه لازمه! 🌟

📲 t.me/vitrinspain""",

    # هفته ۲: اعداد، رنگ‌ها، روزهای هفته
    """📍 روز ۸ — اعداد ۱ تا ۵ 🇪🇸

uno = ۱ (بخون: اونو)
dos = ۲ (بخون: دوس)
tres = ۳ (بخون: تِرِس)
cuatro = ۴ (بخون: کواترو)
cinco = ۵ (بخون: سینکو)

💡 نکته:
uno قبل از اسم میشه un
مثلاً: un café = یه قهوه ☕

📲 t.me/vitrinspain""",

    """📍 روز ۸ — ادامه 🇪🇸

seis = ۶ (بخون: سِئیس)
siete = ۷ (بخون: سیِته)
ocho = ۸ (بخون: اوچو)
nueve = ۹ (بخون: نوئِوه)
diez = ۱۰ (بخون: دیِث)

💡 کاربرد:
Mesa para dos = میز برای دو نفر 🍽️

📲 t.me/vitrinspain""",

    """📍 روز ۹ — اعداد ۱۱ تا ۱۵ 🇪🇸

once = ۱۱ (بخون: اونسه)
doce = ۱۲ (بخون: دوسه)
trece = ۱۳ (بخون: تِرِسه)
catorce = ۱۴ (بخون: کاتورسه)
quince = ۱۵ (بخون: کینسه)

💡 نکته:
۱۳ توی اسپانیا هم عدد بدشانسیه! 😄

📲 t.me/vitrinspain""",

    """📍 روز ۹ — ادامه 🇪🇸

dieciséis = ۱۶ (بخون: دیِسیسِئیس)
diecisiete = ۱۷ (بخون: دیِسیسیِته)
dieciocho = ۱۸ (بخون: دیِسیوچو)
diecinueve = ۱۹ (بخون: دیِسینوئِوه)
veinte = ۲۰ (بخون: وِئینته)

💡 نکته جالب:
۱۶ تا ۱۹ = ۱۰ + عدد — مثل فارسی! 😊

📲 t.me/vitrinspain""",

    """📍 روز ۱۰ — رنگ‌ها (۱) 🇪🇸

rojo = قرمز 🔴 (بخون: روخو)
azul = آبی 🔵 (بخون: آثول)
verde = سبز 🟢 (بخون: وِرده)
amarillo = زرد 🟡 (بخون: آماریو)

💡 نکته:
توی اسپانیایی رنگ بعد از اسم میاد!
coche rojo = ماشین قرمز 🚗

📲 t.me/vitrinspain""",

    """📍 روز ۱۰ — ادامه 🇪🇸

blanco = سفید ⚪ (بخون: بلانکو)
negro = مشکی ⚫ (بخون: نِگرو)
naranja = نارنجی 🟠 (بخون: ناranخا)
rosa = صورتی 🌸 (بخون: روسا)
morado = بنفش 🟣 (بخون: موْرادو)

💡 کاربرد:
¿De qué color es? = چه رنگیه؟ 🎨

📲 t.me/vitrinspain""",

    """📍 روز ۱۱ — روزهای هفته (۱) 🇪🇸

lunes = دوشنبه (بخون: لونِس)
martes = سه‌شنبه (بخون: مارتِس)
miércoles = چهارشنبه (بخون: میِرکولِس)
jueves = پنج‌شنبه (بخون: خوئِوِس)

💡 نکته:
هفته اسپانیایی از دوشنبه شروع میشه! 📅

📲 t.me/vitrinspain""",

    """📍 روز ۱۱ — ادامه 🇪🇸

viernes = جمعه (بخون: ویِرنِس)
sábado = شنبه (بخون: سابادو)
domingo = یکشنبه (بخون: دومینگو)

💡 کاربرد:
Hoy es lunes = امروز دوشنبه‌ست
(بخون: اوی اِس لونِس)

📲 t.me/vitrinspain""",

    """📍 روز ۱۲ — ماه‌های سال (۱) 🇪🇸

enero = ژانویه (بخون: اِنِرو)
febrero = فوریه (بخون: فِبِرِرو)
marzo = مارس (بخون: مارثو)
abril = آوریل (بخون: آبریل)
mayo = مه (بخون: مایو)
junio = ژوئن (بخون: خونیو)

📲 t.me/vitrinspain""",

    """📍 روز ۱۲ — ادامه 🇪🇸

julio = ژوئیه (بخون: خولیو)
agosto = اوت (بخون: آگوستو)
septiembre = سپتامبر (بخون: سِپتیِمبِره)
octubre = اکتبر (بخون: اوکتوبِره)
noviembre = نوامبر (بخون: نوویِمبِره)
diciembre = دسامبر (بخون: دیسیِمبِره)

📲 t.me/vitrinspain""",

    """📍 روز ۱۳ — تاریخ و زمان 🇪🇸

hoy = امروز (بخون: اوی)
mañana = فردا (بخون: مانیانا)
ayer = دیروز (بخون: آیِر)
esta semana = این هفته (بخون: استا سِمانا)
este mes = این ماه (بخون: استه مِس)

💡 کاربرد:
¿Qué día es hoy? = امروز چه روزیه؟

📲 t.me/vitrinspain""",

    """📍 روز ۱۳ — ادامه 🇪🇸

¿Cuándo? = کِی؟ (بخون: کواندو)
ahora = الان (بخون: آاورا)
después = بعداً (بخون: دِسپوئِس)
antes = قبلاً (بخون: آنتِس)
siempre = همیشه (بخون: سیِمپِره)
nunca = هرگز (بخون: نونکا)

📲 t.me/vitrinspain""",

    """📍 روز ۱۴ — مرور هفته دوم 🎉

این هفته یاد گرفتی:
✅ اعداد ۱ تا ۲۰
✅ ۹ رنگ اصلی
✅ روزهای هفته
✅ ماه‌های سال
✅ کلمات زمانی

💡 چالش:
امروز بگو چه روزیه به اسپانیایی!
Hoy es... 😄

📲 t.me/vitrinspain""",

    # هفته ۳: خانواده و آدم‌ها
    """📍 روز ۱۵ — خانواده (۱) 🇪🇸

padre = پدر 👨 (بخون: پادِره)
madre = مادر 👩 (بخون: مادِره)
hijo = پسر 👦 (بخون: ایخو)
hija = دختر 👧 (بخون: ایخا)

💡 نکته:
mi = مال من
mi padre = پدرم 😊

📲 t.me/vitrinspain""",

    """📍 روز ۱۵ — ادامه 🇪🇸

hermano = برادر (بخون: اِرمانو)
hermana = خواهر (بخون: اِرمانا)
abuelo = پدربزرگ (بخون: آبوئِلو)
abuela = مادربزرگ (بخون: آبوئِلا)

💡 کاربرد:
Tengo dos hermanos = دو برادر دارم 👨‍👨‍👦

📲 t.me/vitrinspain""",

    """📍 روز ۱۶ — خانواده (۲) 🇪🇸

esposo/marido = شوهر (بخون: اِسپوسو/ماریدو)
esposa/mujer = زن (بخون: اِسپوسا/موخِر)
novio = نامزد/پسردوست (بخون: نوویو)
novia = نامزد/دختردوست (بخون: نوویا)

💡 نکته:
mujer هم یعنی «زن» هم «خانم»
بسته به context فرق داره 😊

📲 t.me/vitrinspain""",

    """📍 روز ۱۶ — ادامه 🇪🇸

tío = عمو/دایی (بخون: تیو)
tía = عمه/خاله (بخون: تیا)
primo = پسرعمو/پسردایی (بخون: پِریمو)
prima = دخترعمو/دختردایی (بخون: پِریما)

💡 نکته جالب:
اسپانیایی بین عمو و دایی فرق نمیذاره — هر دو tío! 😄

📲 t.me/vitrinspain""",

    """📍 روز ۱۷ — توصیف آدم‌ها (۱) 🇪🇸

alto/alta = قد بلند (بخون: آلتو/آلتا)
bajo/baja = قد کوتاه (بخون: باخو/باخا)
joven = جوان (بخون: خوون)
mayor = مسن (بخون: مایور)

💡 نکته:
صفت برای مذکر و مؤنث فرق داره!
él es alto / ella es alta

📲 t.me/vitrinspain""",

    """📍 روز ۱۷ — ادامه 🇪🇸

simpático = خوش‌برخورد (بخون: سیمپاتیکو)
inteligente = باهوش (بخون: اینتِلیخِنته)
trabajador = سخت‌کوش (بخون: تراباخادور)
amable = مهربان (بخون: آمابله)

💡 کاربرد:
Mi madre es muy amable = مادرم خیلی مهربونه 💕

📲 t.me/vitrinspain""",

    """📍 روز ۱۸ — ضمایر شخصی 🇪🇸

yo = من (بخون: یو)
tú = تو (بخون: تو)
él/ella = او (بخون: اِل/اِیا)
nosotros = ما (بخون: نوسوتروس)
ellos/ellas = آن‌ها (بخون: اِیوس/اِیاس)

💡 نکته مهم:
توی اسپانیایی معمولاً ضمیر حذف میشه!
فعل خودش شخص رو نشون میده 😊

📲 t.me/vitrinspain""",

    """📍 روز ۱۸ — ادامه 🇪🇸

فعل ser = بودن

soy = منم (بخون: سوی)
eres = تویی (بخون: اِرِس)
es = اوست (بخون: اِس)
somos = ماییم (بخون: سوموس)

💡 کاربرد:
Soy iraní = ایرانیم
Eres muy simpático = خیلی خوش‌برخوردی 😊

📲 t.me/vitrinspain""",

    """📍 روز ۱۹ — فعل estar 🇪🇸

estar = بودن (برای حالت موقت)

estoy = هستم (بخون: استوی)
estás = هستی (بخون: استاس)
está = هست (بخون: استا)
estamos = هستیم (بخون: استاموس)

💡 فرق ser و estar:
ser = ویژگی ثابت (ایرانیم)
estar = حالت موقت (خوبم / اینجام)

📲 t.me/vitrinspain""",

    """📍 روز ۱۹ — ادامه 🇪🇸

💡 مثال‌های estar:

Estoy bien = خوبم
Estoy en Madrid = توی مادریدم
Estoy cansado = خسته‌ام
El café está frío = قهوه سرده

📲 t.me/vitrinspain""",

    """📍 روز ۲۰ — فعل tener 🇪🇸

tener = داشتن

tengo = دارم (بخون: تنگو)
tienes = داری (بخون: تیِنِس)
tiene = داره (بخون: تیِنه)
tenemos = داریم (بخون: تِنِموس)

💡 کاربرد:
Tengo hambre = گرسنمه
Tengo 30 años = سی سالمه

📲 t.me/vitrinspain""",

    """📍 روز ۲۰ — ادامه 🇪🇸

💡 مثال‌های tener:

Tengo un piso = یه آپارتمان دارم
Tiene dos hijos = دو تا بچه داره
Tenemos tiempo = وقت داریم
¿Tienes coche? = ماشین داری؟ 🚗

📲 t.me/vitrinspain""",

    """📍 روز ۲۱ — مرور هفته سوم 🎉

این هفته یاد گرفتی:
✅ اعضای خانواده
✅ توصیف آدم‌ها
✅ ضمایر شخصی
✅ فعل ser (ثابت)
✅ فعل estar (موقت)
✅ فعل tener (داشتن)

💪 سه هفته، خیلی پیشرفت کردی! 🌟

📲 t.me/vitrinspain""",

    # هفته ۴: خانه و محیط
    """📍 روز ۲۲ — اتاق‌های خانه 🇪🇸

salón = پذیرایی (بخون: سالون)
cocina = آشپزخانه (بخون: کوسینا)
dormitorio = اتاق خواب (بخون: دورمیتوریو)
baño = حمام (بخون: بانیو)
terraza = تراس (بخون: تِراثا)

💡 کاربرد:
¿Dónde está el baño? = دستشویی کجاست؟ 😅

📲 t.me/vitrinspain""",

    """📍 روز ۲۲ — ادامه 🇪🇸

piso = آپارتمان (بخون: پیسو)
casa = خانه (بخون: کاسا)
habitación = اتاق (بخون: آبیتاسیون)
garaje = پارکینگ (بخون: گاراخه)
ascensor = آسانسور (بخون: آسِنسور)

💡 نکته مهاجرتی:
piso = آپارتمان — کلمه‌ای که خیلی میشنوی! 🏢

📲 t.me/vitrinspain""",

    """📍 روز ۲۳ — وسایل خانه 🇪🇸

mesa = میز (بخون: مِسا)
silla = صندلی (بخون: سیا)
cama = تخت (بخون: کاما)
sofá = مبل (بخون: سوفا)
armario = کمد (بخون: آرماریو)

💡 نکته:
hay = هست/وجود داره
Hay una mesa = یه میز هست 😊

📲 t.me/vitrinspain""",

    """📍 روز ۲۳ — ادامه 🇪🇸

nevera = یخچال (بخون: نِوِرا)
lavadora = ماشین لباسشویی (بخون: لاوادورا)
horno = فر (بخون: اورنو)
microondas = مایکروفر (بخون: میکرواوندِس)
lavavajillas = ماشین ظرفشویی (بخون: لاوابا خیاس)

📲 t.me/vitrinspain""",

    """📍 روز ۲۴ — حروف اضافه مکان 🇪🇸

en = در/توی (بخون: اِن)
sobre = روی (بخون: سوبِره)
debajo de = زیر (بخون: دِباخو ده)
al lado de = کنار (بخون: آل لادو ده)
delante de = جلوی (بخون: دِلانته ده)
detrás de = پشت (بخون: دِتِراس ده)

📲 t.me/vitrinspain""",

    """📍 روز ۲۴ — ادامه 🇪🇸

💡 مثال‌های کاربردی:

El gato está sobre la mesa = گربه روی میزه 🐱
El baño está al lado = دستشویی کناریه
La llave está debajo = کلید زیرشه 🔑

📲 t.me/vitrinspain""",

    """📍 روز ۲۵ — توصیف خانه 🇪🇸

grande = بزرگ (بخون: گرانده)
pequeño = کوچیک (بخون: پِکِنیو)
bonito = قشنگ (بخون: بونیتو)
nuevo = نو (بخون: نوئِوو)
viejo = قدیمی (بخون: ویِخو)
luminoso = روشن/پر نور (بخون: لومینوسو)

📲 t.me/vitrinspain""",

    """📍 روز ۲۵ — ادامه 🇪🇸

💡 کاربرد توصیف خانه:

Mi casa es grande y bonita = خونه‌ام بزرگ و قشنگه 🏠
El piso es luminoso = آپارتمان پرنوره
Busco una habitación pequeña = دنبال یه اتاق کوچیک میگردم

📲 t.me/vitrinspain""",

    """📍 روز ۲۶ — محله و شهر 🇪🇸

calle = خیابان (بخون: کایه)
plaza = میدان (بخون: پلاثا)
parque = پارک (بخون: پارکه)
barrio = محله (بخون: باریو)
centro = مرکز شهر (بخون: سِنترو)

💡 کاربرد:
Vivo en el centro = توی مرکز شهر زندگی می‌کنم

📲 t.me/vitrinspain""",

    """📍 روز ۲۶ — ادامه 🇪🇸

cerca = نزدیک (بخون: سِرکا)
lejos = دور (بخون: لِخوس)
a pie = پیاده (بخون: آ پیِه)
en metro = با مترو
a cinco minutos = پنج دقیقه‌ای

💡 کاربرد:
Está cerca, a diez minutos a pie = نزدیکه، ده دقیقه پیاده

📲 t.me/vitrinspain""",

    """📍 روز ۲۷ — اجاره خانه 🇪🇸

alquiler = اجاره (بخون: آلکیلِر)
alquilar = اجاره دادن/کردن
precio = قیمت (بخون: پِرِسیو)
incluido = شامل (بخون: اینکلوئیدو)
gastos = هزینه‌ها (بخون: گاستوس)

💡 نکته مهاجرتی:
¿Están incluidos los gastos? = هزینه‌ها شامله؟ 🏠

📲 t.me/vitrinspain""",

    """📍 روز ۲۷ — ادامه 🇪🇸

contrato = قرارداد (بخون: کونتِراتو)
fianza = ودیعه (بخون: فیانثا)
propietario = صاحب‌خانه (بخون: پِروپیِتاریو)
inquilino = مستاجر (بخون: اینکیلینو)
comunidad = شارژ (بخون: کوموُنیداد)

💡 نکته مهاجرتی:
این کلمات رو موقع اجاره خانه حتماً میشنوی! 📋

📲 t.me/vitrinspain""",

    """📍 روز ۲۸ — مرور ماه اول 🎉🎉

یه ماه گذشت! عالیه!
این‌ها رو یاد گرفتی:
✅ احوال‌پرسی و معرفی کامل
✅ اعداد ۱ تا ۲۰
✅ رنگ‌ها، روزها، ماه‌ها
✅ خانواده و توصیف آدم‌ها
✅ فعل‌های ser، estar، tener
✅ خانه، محله و اجاره

💪 ماه دوم: زندگی روزمره 🌟

📲 t.me/vitrinspain""",

    # ─── ماه ۲: زندگی روزمره ───

    # هفته ۵: غذا و رستوران
    """📍 روز ۲۹ — وعده‌های غذایی 🇪🇸

desayuno = صبحانه (بخون: دِسایونو)
almuerzo = ناهار (بخون: آلموئِرثو)
cena = شام (بخون: سِنا)
merienda = میان‌وعده (بخون: مِریِندا)

💡 نکته فرهنگی:
اسپانیایی‌ها شام رو ساعت ۹ یا ۱۰ شب می‌خورن! 🌙

📲 t.me/vitrinspain""",

    """📍 روز ۲۹ — ادامه 🇪🇸

💡 برنامه غذایی اسپانیایی:

۸ صبح: desayuno کوچیک ☕
۲ بعدازظهر: almuerzo — مهم‌ترین وعده 🍽️
۵ عصر: merienda — قهوه و شیرینی 🧁
۹ شب: cena — سبک‌تر از ناهار 🥗

📲 t.me/vitrinspain""",

    """📍 روز ۳۰ — خوراکی‌های پایه 🇪🇸

pan = نان (بخون: پان)
leche = شیر (بخون: لِچه)
huevo = تخم‌مرغ (بخون: وئِوو)
fruta = میوه (بخون: فروتا)
verdura = سبزی (بخون: وِردورا)
carne = گوشت (بخون: کارنه)

📲 t.me/vitrinspain""",

    """📍 روز ۳۰ — ادامه 🇪🇸

arroz = برنج (بخون: آروث)
pasta = ماکارونی (بخون: پاستا)
aceite = روغن (بخون: آسِئیته)
sal = نمک (بخون: سال)
azúcar = شکر (بخون: آثوکار)

💡 کاربرد:
¿Tiene...? = ... دارید؟
توی مغازه کاربرد داره! 🛒

📲 t.me/vitrinspain""",

    """📍 روز ۳۱ — نوشیدنی‌ها 🇪🇸

agua = آب (بخون: آگوا)
café = قهوه (بخون: کافه)
té = چای (بخون: ته)
zumo = آب‌میوه (بخون: ثومو)
cerveza = آبجو (بخون: سِروِثا)
vino = شراب (بخون: بینو)

📲 t.me/vitrinspain""",

    """📍 روز ۳۱ — ادامه 🇪🇸

💡 سفارش قهوه توی اسپانیا:

café solo = اسپرسو
café con leche = قهوه با شیر ☕
cortado = اسپرسو با کمی شیر
café americano = قهوه آمریکایی

کاربرد:
Un café con leche, por favor 😊

📲 t.me/vitrinspain""",

    """📍 روز ۳۲ — توی رستوران (۱) 🇪🇸

Una mesa para dos, por favor = میز برای دو نفر لطفاً
La carta, por favor = منو لطفاً
¿Qué recomienda? = چی پیشنهاد میدی؟
¿Cuál es el plato del día? = غذای روز چیه؟

💡 نکته:
por favor = لطفاً — همیشه لازمه! 🙏

📲 t.me/vitrinspain""",

    """📍 روز ۳۲ — ادامه 🇪🇸

Para mí... = برای من...
De primero... = اول...
De segundo... = دوم...
De postre... = دسر...
Para beber... = نوشیدنی...

💡 مثال:
Para mí, la paella. Para beber, agua.
= برای من پائلا. نوشیدنی هم آب.

📲 t.me/vitrinspain""",

    """📍 روز ۳۳ — توی رستوران (۲) 🇪🇸

¡Está delicioso! = خیلی خوشمزه‌ست! (بخون: استا دِلیسیوسو)
La cuenta, por favor = صورتحساب لطفاً
¿Está incluido el servicio? = سرویس شامله؟
¿Aceptan tarjeta? = کارت قبول می‌کنید؟

💡 نکته:
توی اسپانیا انعام اجباری نیست ولی مرسومه 😊

📲 t.me/vitrinspain""",

    """📍 روز ۳۳ — ادامه 🇪🇸

💡 غذاهای اسپانیایی معروف:

🥘 paella = پائلا — برنج با دریایی
🍳 tortilla = تورتیا — املت اسپانیایی
🥩 jamón = ژامبون — گوشت خشک
🍩 churros = چوروس — شیرینی سرخ‌شده
🍅 gazpacho = گاثپاچو — سوپ سرد

📲 t.me/vitrinspain""",

    """📍 روز ۳۴ — مرور هفته پنجم 🎉

این هفته یاد گرفتی:
✅ وعده‌های غذایی
✅ خوراکی و نوشیدنی‌های پایه
✅ سفارش قهوه
✅ جملات کامل رستوران
✅ غذاهای اسپانیایی معروف

💡 چالش:
یه سفارش کامل رستوران به اسپانیایی بده! 🍽️

📲 t.me/vitrinspain""",

    # هفته ۶: خرید و مغازه
    """📍 روز ۳۵ — انواع مغازه 🇪🇸

panadería = نانوایی (بخون: پاناداِریا)
farmacia = داروخانه (بخون: فارماسیا)
mercado = بازار (بخون: مِرکادو)
supermercado = سوپرمارکت (بخون: سوپِرمِرکادو)
tienda = مغازه (بخون: تیِندا)

💡 نکته:
farmacia با صلیب سبز مشخصه ✚

📲 t.me/vitrinspain""",

    """📍 روز ۳۵ — ادامه 🇪🇸

carnicería = قصابی (بخون: کارنیسِریا)
frutería = میوه‌فروشی (بخون: فروتِریا)
panadería = نانوایی (بخون: پاناداِریا)
ferretería = آهن‌فروشی (بخون: فِرِتِریا)
quiosco = دکه روزنامه (بخون: کیوسکو)

💡 نکته:
بازارهای محلی (mercadillo) خیلی ارزون‌ترن! 🛒

📲 t.me/vitrinspain""",

    """📍 روز ۳۶ — خرید کردن (۱) 🇪🇸

¿Cuánto cuesta? = چقدر میشه؟ (بخون: کوانتو کوئِستا)
¿Tiene...? = ... دارید؟
Quiero... = می‌خوام... (بخون: کیِرو)
Me llevo esto = این رو برمیدارم
¿Puedo ver...? = میتونم ... رو ببینم؟

📲 t.me/vitrinspain""",

    """📍 روز ۳۶ — ادامه 🇪🇸

caro = گرونه (بخون: کارو)
barato = ارزونه (بخون: باراتو)
rebaja = تخفیف (بخون: رِباخا)
oferta = حراج (بخون: اوفِرتا)
gratis = رایگان (بخون: گِراتیس)

💡 کاربرد:
¿Tiene algo más barato? = چیز ارزون‌تری دارید؟ 😄

📲 t.me/vitrinspain""",

    """📍 روز ۳۷ — پرداخت 🇪🇸

efectivo = نقد (بخون: اِفِکتیوو)
tarjeta = کارت (بخون: تارخِتا)
¿Acepta tarjeta? = کارت قبول می‌کنید؟
ticket/recibo = رسید (بخون: تیکِت/رِسیبو)
cambio = باقیمانده/پس‌پول (بخون: کامبیو)

💡 نکته مهاجرتی:
توی اسپانیا اکثر مغازه‌ها کارت قبول می‌کنن 💳

📲 t.me/vitrinspain""",

    """📍 روز ۳۷ — ادامه 🇪🇸

¿Me da una bolsa? = یه کیسه میدید؟
¿Puede envolverlo? = میتونید بپیچیدش؟
¿Tiene garantía? = ضمانت داره؟
¿Se puede cambiar? = میشه عوض کرد؟

💡 نکته:
توی اسپانیا کیسه پلاستیکی پولیه — ۱۰ سنت 😄

📲 t.me/vitrinspain""",

    """📍 روز ۳۸ — لباس و سایز 🇪🇸

talla = سایز (بخون: تایا)
pequeño/S = کوچیک
mediano/M = متوسط (بخون: مِدیانو)
grande/L = بزرگ
extra grande/XL = خیلی بزرگ

💡 کاربرد:
¿Puedo probármelo? = میتونم امتحان کنم؟ 👗

📲 t.me/vitrinspain""",

    """📍 روز ۳۸ — ادامه 🇪🇸

probador = اتاق پرو (بخون: پروبادور)
¿Cómo le queda? = چطور بهتون میاد؟
Me queda bien = خوب بهم میاد
Me queda grande = بزرگه
Me queda pequeño = کوچیکه

📲 t.me/vitrinspain""",

    """📍 روز ۳۹ — مرور هفته ششم 🎉

این هفته یاد گرفتی:
✅ انواع مغازه
✅ پرسیدن قیمت
✅ تخفیف و حراج
✅ پرداخت
✅ خرید لباس

💡 چالش:
یه خرید کامل به اسپانیایی شبیه‌سازی کن! 🛍️

📲 t.me/vitrinspain""",

    # هفته ۷: حمل‌ونقل و شهر
    """📍 روز ۴۰ — وسایل نقلیه 🇪🇸

metro = مترو (بخون: مِترو)
autobús = اتوبوس (بخون: آئوتوبوس)
taxi = تاکسی
tren = قطار (بخون: تِرِن)
avión = هواپیما (بخون: آویون)
bicicleta = دوچرخه (بخون: بیسیکلِتا)

📲 t.me/vitrinspain""",

    """📍 روز ۴۰ — ادامه 🇪🇸

💡 حمل‌ونقل عمومی مادرید:

🚇 Metro — ۱۲ خط، خیلی کاربردی
🚌 EMT — اتوبوس شهری
🚆 Cercanías — قطار حومه
🛵 Movilidad — دوچرخه اشتراکی BiciMAD

📲 t.me/vitrinspain""",

    """📍 روز ۴۱ — پرسیدن مسیر (۱) 🇪🇸

¿Dónde está...? = ... کجاست؟
¿Cómo llego a...? = چطور برم به...؟
todo recto = مستقیم (بخون: تودو رِکتو)
a la derecha = سمت راست (بخون: دِرِچا)
a la izquierda = سمت چپ (بخون: ایثکیِردا)

📲 t.me/vitrinspain""",

    """📍 روز ۴۱ — ادامه 🇪🇸

la primera calle = اولین خیابان (بخون: پِریمِرا کایه)
la segunda calle = دومین خیابان (بخون: سِگوندا)
en el semáforo = سر چراغ (بخون: سِمافورو)
en la rotonda = دور میدان (بخون: روتوندا)
cruzar = رد کردن (بخون: کروثار)

📲 t.me/vitrinspain""",

    """📍 روز ۴۲ — توی مترو 🇪🇸

billete = بلیت (بخون: بیِتِه)
abono = کارت ماهانه (بخون: آبونو)
ida y vuelta = رفت و برگشت (بخون: ایدا ای بوئِلتا)
andén = سکو (بخون: آندِن)
próxima parada = ایستگاه بعدی

📲 t.me/vitrinspain""",

    """📍 روز ۴۲ — ادامه 🇪🇸

💡 بلیت مترو مادرید:

Billete sencillo = بلیت تکی — ۱.۵ یورو
Tarjeta de 10 viajes = ۱۰ سفره — ارزون‌تر
Abono mensual = کارت ماهانه — بهترین گزینه

¿En qué parada bajo? = کدوم ایستگاه پیاده بشم؟

📲 t.me/vitrinspain""",

    """📍 روز ۴۳ — مکان‌های مهم شهر 🇪🇸

ayuntamiento = شهرداری (بخون: آیونتامیِنتو)
hospital = بیمارستان (بخون: اوسپیتال)
comisaría = کلانتری (بخون: کومیساریا)
embajada = سفارت (بخون: اِمباخادا)
correos = پست (بخون: کورِئوس)

💡 نکته مهاجرتی:
این مکان‌ها رو حفظ کن — حتماً لازم میشن! 🏛️

📲 t.me/vitrinspain""",

    """📍 روز ۴۳ — ادامه 🇪🇸

extranjería = اداره اتباع خارجی (بخون: اِکستِرانخِریا)
notaría = دفتر اسناد رسمی (بخون: نوتاریا)
gestoría = دفتر خدمات اداری (بخون: خِستوریا)
biblioteca = کتابخانه (بخون: بیبلیوتِکا)
oficina de empleo = اداره کار (بخون: اوفیسینا ده اِمپلِئو)

📲 t.me/vitrinspain""",

    """📍 روز ۴۴ — مرور هفته هفتم 🎉

این هفته یاد گرفتی:
✅ وسایل نقلیه
✅ پرسیدن مسیر
✅ بلیت مترو
✅ مکان‌های مهم شهر
✅ اماکن اداری

💡 چالش:
از خونه‌ات به نزدیک‌ترین داروخانه مسیر بده به اسپانیایی! 🗺️

📲 t.me/vitrinspain""",

    # هفته ۸: کار و روتین روزانه
    """📍 روز ۴۵ — ساعت 🇪🇸

¿Qué hora es? = ساعت چنده؟
Son las tres = ساعت سه‌ست
Es la una = ساعت یک‌ست
y media = و نیم (بخون: مِدیا)
y cuarto = و ربع (بخون: کوارتو)
menos cuarto = کمتر از ربع

📲 t.me/vitrinspain""",

    """📍 روز ۴۵ — ادامه 🇪🇸

💡 مثال‌های ساعت:

Son las tres y media = ساعت ۳:۳۰
Son las cuatro y cuarto = ساعت ۴:۱۵
Son las cinco menos cuarto = ساعت ۴:۴۵
Son las doce = ساعت ۱۲

نکته: فقط برای ۱ بعدازظهر «es» میگیم، بقیه «son»

📲 t.me/vitrinspain""",

    """📍 روز ۴۶ — روتین صبح 🇪🇸

levantarse = بیدار شدن (بخون: لِوانتارسه)
ducharse = دوش گرفتن (بخون: دوچارسه)
desayunar = صبحانه خوردن (بخون: دِسایونار)
vestirse = لباس پوشیدن (بخون: وِستیرسه)
salir = رفتن (بخون: سالیر)

💡 نکته:
فعل‌های se = کار روی خودت 😊

📲 t.me/vitrinspain""",

    """📍 روز ۴۶ — ادامه 🇪🇸

💡 روتین کامل به اسپانیایی:

Me levanto a las siete = ساعت ۷ بیدار میشم
Me ducho = دوش میگیرم
Desayuno = صبحانه میخورم
Salgo de casa a las ocho = ساعت ۸ از خونه میرم

📲 t.me/vitrinspain""",

    """📍 روز ۴۷ — مشاغل 🇪🇸

médico = دکتر (بخون: مِدیکو)
abogado = وکیل (بخون: آبوگادو)
ingeniero = مهندس (بخون: اینخِنیِرو)
profesor = معلم (بخون: پروفِسور)
cocinero = آشپز (بخون: کوسینِرو)

💡 کاربرد:
¿A qué te dedicas? = چیکاره‌ای؟
Soy ingeniero = مهندسم 👷

📲 t.me/vitrinspain""",

    """📍 روز ۴۷ — ادامه 🇪🇸

arquitecto = معمار (بخون: آرکیتِکتو)
contable = حسابدار (بخون: کونتابله)
comercial = فروشنده (بخون: کومِرسیال)
autónomo = خوداشتغال (بخون: آئوتونومو)
empresario = کارآفرین (بخون: اِمپِرِساریو)

💡 نکته مهاجرتی:
autónomo = کسی که برای خودش کار میکنه — مثل فریلنسر 💼

📲 t.me/vitrinspain""",

    """📍 روز ۴۸ — محیط کار 🇪🇸

oficina = اداره (بخون: اوفیسینا)
reunión = جلسه (بخون: رِئونیون)
jefe = رئیس (بخون: خِفه)
compañero = همکار (بخون: کومپانیِرو)
sueldo = حقوق (بخون: سوئِلدو)

💡 نکته مهاجرتی:
¿Cuánto es el sueldo neto? = حقوق خالص چقدره؟ 💼

📲 t.me/vitrinspain""",

    """📍 روز ۴۸ — ادامه 🇪🇸

contrato = قرارداد (بخون: کونتِراتو)
jornada completa = تمام‌وقت (بخون: خورنادا)
media jornada = نیمه‌وقت
vacaciones = تعطیلات/مرخصی (بخون: واکاسیونِس)
baja = مرخصی استعلاجی (بخون: باخا)

💡 نکته:
توی اسپانیا ۲۲ روز مرخصی سالانه حق توست! 🏖️

📲 t.me/vitrinspain""",

    """📍 روز ۴۹ — اعداد بزرگ‌تر 🇪🇸

veinte = ۲۰ (بخون: وِئینته)
treinta = ۳۰ (بخون: تِرِئینتا)
cuarenta = ۴۰ (بخون: کوارِنتا)
cincuenta = ۵۰ (بخون: سینکوئِنتا)
sesenta = ۶۰ (بخون: سِسِنتا)
setenta = ۷۰ (بخون: سِتِنتا)
ochenta = ۸۰ (بخون: اوچِنتا)
noventa = ۹۰ (بخون: نوبِنتا)
cien = ۱۰۰ (بخون: سیِن)
mil = ۱۰۰۰ (بخون: میل)

📲 t.me/vitrinspain""",

    """📍 روز ۴۹ — ادامه 🇪🇸

💡 کاربرد اعداد بزرگ:

El alquiler es mil euros = اجاره هزار یورو است
Gano dos mil al mes = ماهی دوهزار درمیارم
El vuelo cuesta trescientos euros = پرواز سیصد یورو

📲 t.me/vitrinspain""",

    """📍 روز ۵۰ — مرور هفته هشتم 🎉

این هفته یاد گرفتی:
✅ ساعت کامل
✅ روتین روزانه
✅ مشاغل مختلف
✅ محیط کار
✅ اعداد بزرگ‌تر

💪 نصف راه رو اومدی! 🏆

📲 t.me/vitrinspain""",

    # ─── ماه ۳: موقعیت‌های واقعی ───

    # هفته ۹: بانک، اداره، دکتر
    """📍 روز ۵۱ — توی بانک (۱) 🇪🇸

cuenta bancaria = حساب بانکی (بخون: کوئِنتا بانکاریا)
abrir una cuenta = باز کردن حساب
tarjeta de débito = کارت دبیت
tarjeta de crédito = کارت اعتباری
cajero automático = خودپرداز (بخون: کاخِرو)

💡 نکته مهاجرتی:
اولین کاری که توی اسپانیا باید بکنی! 🏦

📲 t.me/vitrinspain""",

    """📍 روز ۵۱ — ادامه 🇪🇸

transferencia = انتقال وجه (بخون: ترانسفِرِنسیا)
ingreso = واریز (بخون: اینگِرِسو)
retirar dinero = برداشت پول
comisión = کارمزد (بخون: کومیسیون)
IBAN = شماره حساب بین‌المللی

💡 جمله مهم:
Quiero abrir una cuenta = می‌خوام حساب باز کنم 🏦

📲 t.me/vitrinspain""",

    """📍 روز ۵۲ — مدارک و اداره 🇪🇸

NIE = شماره شناسایی خارجی — مهم‌ترین مدرک!
pasaporte = پاسپورت (بخون: پاساپورته)
certificado = گواهی‌نامه (بخون: سِرتیفیکادو)
cita previa = وقت قبلی (بخون: سیتا پِرِویا)
empadronamiento = ثبت محل سکونت

💡 نکته مهاجرتی:
بدون NIE هیچ کاری نمیشه کرد! اول اینو بگیر 🔑

📲 t.me/vitrinspain""",

    """📍 روز ۵۲ — ادامه 🇪🇸

Solicitar cita = گرفتن وقت (بخون: سولیسیتار سیتا)
rellenar un formulario = پر کردن فرم (بخون: رِیِنار)
firma = امضا (بخون: فیرما)
fotocopia = کپی (بخون: فوتوکوپیا)
adjuntar = ضمیمه کردن (بخون: آدخونتار)

💡 نکته:
برای هر کار اداری باید cita previa بگیری — آنلاین! 💻

📲 t.me/vitrinspain""",

    """📍 روز ۵۳ — توی مطب دکتر 🇪🇸

Me duele... = ... درد میکنه (بخون: مه دوئِله)
la cabeza = سر (بخون: کابِثا)
el estómago = معده (بخون: استوماگو)
la garganta = گلو (بخون: گارگانتا)
la espalda = کمر (بخون: اِسپالدا)
el pecho = سینه (بخون: پِچو)

📲 t.me/vitrinspain""",

    """📍 روز ۵۳ — ادامه 🇪🇸

Tengo fiebre = تب دارم (بخون: فیِبِره)
Tengo tos = سرفه دارم (بخون: توس)
Estoy mareado = سرم گیجه (بخون: مارِادو)
Me cuesta respirar = نفسم تنگه (بخون: رِسپیرار)

💡 کاربرد:
Me duele mucho la cabeza = سرم خیلی درد میکنه 🤕

📲 t.me/vitrinspain""",

    """📍 روز ۵۴ — داروخانه 🇪🇸

receta = نسخه (بخون: رِسِتا)
pastilla = قرص (بخون: پاستیا)
jarabe = شربت (بخون: خاراب)
pomada = پماد (بخون: پومادا)
venda = باند (بخون: وِندا)

💡 کاربرد:
¿Tiene algo para el dolor de cabeza? = چیزی برای سردرد دارید؟

📲 t.me/vitrinspain""",

    """📍 روز ۵۴ — ادامه 🇪🇸

¿Cuándo lo tomo? = کِی بخورمش؟
tres veces al día = روزی سه بار
en ayunas = ناشتا (بخون: آیوناس)
con las comidas = با غذا
antes de dormir = قبل از خواب

💡 نکته:
شربت Ibuprofeno = ایبوپروفن — داروی مسکن معروف اسپانیا 💊

📲 t.me/vitrinspain""",

    """📍 روز ۵۵ — اورژانس 🇪🇸

¡Ayuda! = کمک! (بخون: آیودا)
¡Llame a una ambulancia! = آمبولانس خبر کنید!
¡Fuego! = آتش! (بخون: فوئِگو)
¡Policía! = پلیس! (بخون: پولیسیا)
Número de emergencias = ۱۱۲

💡 مهم:
112 = شماره اورژانس اسپانیا — حفظش کن! 🚨

📲 t.me/vitrinspain""",

    """📍 روز ۵۵ — ادامه 🇪🇸

Me han robado = دزدیده شدم (بخون: روبادو)
He tenido un accidente = تصادف کردم
Estoy perdido = گم شدم (بخون: پِردیدو)
Necesito ayuda = به کمک نیاز دارم
¿Habla inglés? = انگلیسی حرف میزنید؟

📲 t.me/vitrinspain""",

    """📍 روز ۵۶ — بیمه درمانی 🇪🇸

seguro médico = بیمه درمانی (بخون: سِگورو مِدیکو)
tarjeta sanitaria = کارت بیمه درمانی
médico de cabecera = پزشک عمومی (بخون: کابِسِرا)
especialista = متخصص (بخون: اِسپِسیالیستا)
urgencias = اورژانس بیمارستان (بخون: اورخِنسیاس)

💡 نکته مهاجرتی:
بعد از NIE باید بیمه بگیری — بدون بیمه گرون تموم میشه! 🏥

📲 t.me/vitrinspain""",

    """📍 روز ۵۶ — مرور هفته نهم 🎉

این هفته یاد گرفتی:
✅ بانک و حساب
✅ مدارک اداری
✅ دکتر و علائم بیماری
✅ داروخانه
✅ اورژانس
✅ بیمه درمانی

💡 این هفته مهم‌ترین هفته برای زندگی در اسپانیاست! 🌟

📲 t.me/vitrinspain""",

    # هفته ۱۰: سفر و توریسم
    """📍 روز ۵۷ — فرودگاه 🇪🇸

vuelo = پرواز (بخون: بوئِلو)
puerta de embarque = گیت (بخون: پوئِرتا ده اِمبارکه)
equipaje = چمدان (بخون: اِکیپاخه)
facturar = تحویل چمدان (بخون: فاکتورار)
aduana = گمرک (بخون: آدوانا)

💡 کاربرد:
¿Dónde está la puerta cinco? = گیت پنج کجاست؟ ✈️

📲 t.me/vitrinspain""",

    """📍 روز ۵۷ — ادامه 🇪🇸

retraso = تأخیر (بخون: رِتِراسو)
cancelado = لغو شده (بخون: کانسِلادو)
embarque = سوارشدن (بخون: اِمبارکه)
escala = توقف میانی (بخون: اِسکالا)
vuelo directo = پرواز مستقیم

💡 کاربرد:
¿El vuelo tiene retraso? = پرواز تأخیر داره؟

📲 t.me/vitrinspain""",

    """📍 روز ۵۸ — هتل 🇪🇸

habitación = اتاق (بخون: آبیتاسیون)
reserva = رزرو (بخون: رِسِروا)
check-in = ورود
check-out = خروج
llave = کلید (بخون: یاوه)

💡 کاربرد:
Tengo una reserva a nombre de... = رزرو به اسم ... دارم 🏨

📲 t.me/vitrinspain""",

    """📍 روز ۵۸ — ادامه 🇪🇸

¿Está incluido el desayuno? = صبحانه شامله؟
individual = یک‌نفره (بخون: ایندیویدوال)
doble = دونفره (بخون: دوبله)
con baño = با حمام
wifi = وای‌فای (بخون: وی‌فی)

💡 کاربرد:
¿Hay wifi? ¿Cuál es la contraseña? = وای‌فای دارید؟ رمز چیه؟

📲 t.me/vitrinspain""",

    """📍 روز ۵۹ — جاهای دیدنی 🇪🇸

museo = موزه (بخون: موسئو)
iglesia = کلیسا (بخون: ایگلِسیا)
playa = ساحل (بخون: پلایا)
montaña = کوه (بخون: مونتانیا)
castillo = قلعه (بخون: کاستیو)

💡 کاربرد:
¿Qué hay que ver aquí? = اینجا چی دیدنی داره؟ 🗺️

📲 t.me/vitrinspain""",

    """📍 روز ۵۹ — ادامه 🇪🇸

entrada = بلیت ورودی (بخون: اِنترادا)
¿Está abierto? = بازه؟ (بخون: آبیِرتو)
¿A qué hora cierra? = کِی میبنده؟ (بخون: سیِرا)
gratis = رایگان
descuento = تخفیف (بخون: دِسکوئِنتو)

💡 نکته:
خیلی از موزه‌های اسپانیا یه روز در هفته رایگانه! 🎨

📲 t.me/vitrinspain""",

    """📍 روز ۶۰ — آب‌وهوا 🇪🇸

¿Qué tiempo hace? = هوا چطوره؟
hace calor = گرمه (بخون: آسه کالور)
hace frío = سرده (بخون: فریو)
llueve = باران میاد (بخون: یوئِوه)
hace sol = آفتابیه (بخون: سول)
hay niebla = مه داره (بخون: نیِبلا)

📲 t.me/vitrinspain""",

    """📍 روز ۶۰ — ادامه 🇪🇸

💡 آب‌وهوای شهرهای اسپانیا:

☀️ مادرید — خشک، تابستون خیلی گرم
🌊 بارسلونا — مدیترانه‌ای، معتدل
🌧️ بیلبائو — بارانی‌تر، شبیه شمال اروپا
🌴 مالاگا — گرم‌ترین، بهترین برای زمستان

📲 t.me/vitrinspain""",

    """📍 روز ۶۱ — شهرهای معروف اسپانیا 🇪🇸

Madrid = مادرید — پایتخت 🏛️
Barcelona = بارسلونا — گائودی 🏗️
Valencia = والنسیا — پائلا 🥘
Sevilla = سویل — فلامنکو 💃
Granada = گرانادا — الحمرا 🏰

📲 t.me/vitrinspain""",

    """📍 روز ۶۱ — ادامه 🇪🇸

Bilbao = بیلبائو — موزه گوگنهایم 🎨
Málaga = مالاگا — ساحل و آفتاب ☀️
Zaragoza = ساراگوسا — مرکز اسپانیا
Alicante = آلیکانته — کاستا بلانکا 🌊
San Sebastián = سان سباستیان — بهترین غذا در اسپانیا 🍽️

📲 t.me/vitrinspain""",

    """📍 روز ۶۲ — مرور هفته دهم 🎉

این هفته یاد گرفتی:
✅ فرودگاه
✅ هتل
✅ جاهای دیدنی
✅ آب‌وهوا
✅ شهرهای معروف اسپانیا

💡 چالش:
یه سفر یک‌روزه به مادرید برنامه‌ریزی کن به اسپانیایی! ✈️

📲 t.me/vitrinspain""",

    # هفته ۱۱: احساسات و نظر دادن
    """📍 روز ۶۳ — احساسات (۱) 🇪🇸

estoy feliz = خوشحالم (بخون: فِلیث)
estoy triste = ناراحتم (بخون: تِریسته)
estoy cansado = خسته‌ام (بخون: کانسادو)
estoy nervioso = عصبیم (بخون: نِرویوسو)
estoy emocionado = هیجان‌زده‌ام (بخون: اِموسیونادو)

📲 t.me/vitrinspain""",

    """📍 روز ۶۳ — ادامه 🇪🇸

tengo miedo = می‌ترسم (بخون: میِدو)
tengo hambre = گرسنمه (بخون: آمبِره)
tengo sed = تشنمه (بخون: سِد)
tengo sueño = خوابم میاد (بخون: سوئِنیو)
tengo prisa = عجله دارم (بخون: پِریسا)

💡 نکته:
احساسات جسمی با tener (داشتن) میان! 😊

📲 t.me/vitrinspain""",

    """📍 روز ۶۴ — احساسات (۲) 🇪🇸

me alegra = خوشحالم میکنه (بخون: آلِگِرا)
me molesta = اذیتم میکنه (بخون: مولِستا)
me preocupa = نگرانم میکنه (بخون: پِرِئوکوپا)
me sorprende = تعجبم میکنه (بخون: سورپِرِنده)
me encanta = عاشقشم (بخون: اِنکانتا)

📲 t.me/vitrinspain""",

    """📍 روز ۶۴ — ادامه 🇪🇸

💡 مثال‌های عاشقانه:

Me encanta España = عاشق اسپانیام ❤️
Me encanta el café = قهوه رو خیلی دوست دارم ☕
Me gusta mucho = خیلی دوستش دارم
No me gusta nada = اصلاً دوستش ندارم

📲 t.me/vitrinspain""",

    """📍 روز ۶۵ — موافقت و مخالفت 🇪🇸

Sí = بله (بخون: سی)
No = نه
Claro = البته (بخون: کلارو)
De acuerdo = موافقم (بخون: آکوئِردو)
No estoy de acuerdo = موافق نیستم
Por supuesto = حتماً (بخون: سوپوئِستو)

📲 t.me/vitrinspain""",

    """📍 روز ۶۵ — ادامه 🇪🇸

Quizás = شاید (بخون: کیثاس)
Depende = بستگی داره (بخون: دِپِنده)
A lo mejor = شاید (بخون: آ لو مِخور)
Exactamente = دقیقاً (بخون: اِکساکتامِنته)
Por favor, no = خواهشاً نه

📲 t.me/vitrinspain""",

    """📍 روز ۶۶ — نظر دادن 🇪🇸

Creo que... = فکر می‌کنم... (بخون: کِرئو که)
En mi opinión... = به نظر من... (بخون: اوپینیون)
Me parece bien = به نظرم خوبه
Me parece mal = به نظرم بده
¿Qué piensas? = چی فکر می‌کنی؟

📲 t.me/vitrinspain""",

    """📍 روز ۶۶ — ادامه 🇪🇸

Estoy de acuerdo contigo = باهات موافقم
No lo veo así = اینطوری نمی‌بینمش
Tienes razón = حق داری (بخون: تیِنِس راثون)
No tienes razón = حق نداری
Puede ser = شاید (بخون: پوئِده سِر)

📲 t.me/vitrinspain""",

    """📍 روز ۶۷ — تعریف و تشکر 🇪🇸

Gracias = ممنون (بخون: گراسیاس)
Muchas gracias = خیلی ممنون
De nada = خواهش می‌کنم (بخون: ده نادا)
¡Qué bonito! = چه قشنگه! (بخون: که بونیتو)
¡Qué bien! = عالیه! (بخون: که بیِن)
¡Increíble! = باورنکردنیه! (بخون: اینکِرِیبله)

📲 t.me/vitrinspain""",

    """📍 روز ۶۷ — ادامه 🇪🇸

Lo siento = متأسفم (بخون: لو سیِنتو)
Perdón = ببخشید (بخون: پِردون)
Disculpe = عذر می‌خوام (رسمی)
No pasa nada = اشکالی نداره (بخون: پاسا نادا)
No te preocupes = نگران نباش

📲 t.me/vitrinspain""",

    """📍 روز ۶۸ — مرور هفته یازدهم 🎉

این هفته یاد گرفتی:
✅ احساسات با estar و tener
✅ me gusta / me encanta
✅ موافقت و مخالفت
✅ نظر دادن
✅ تعریف و عذرخواهی

💡 این هفته = مکالمه واقعی‌تر شدی! 🗣️

📲 t.me/vitrinspain""",

    # هفته ۱۲: مرور کلی
    """📍 روز ۶۹ — مکالمه کامل: معرفی 🇪🇸

¡Hola! Me llamo Dara.
Soy de Irán. Tengo 32 años.
Soy ingeniero. Vivo en Madrid.
Estoy aprendiendo español. 😄

یعنی:
سلام! اسمم داراست.
اهل ایرانم. ۳۲ سالمه.
مهندسم. توی مادرید زندگی می‌کنم.
دارم اسپانیایی یاد می‌گیرم.

📲 t.me/vitrinspain""",

    """📍 روز ۶۹ — ادامه 🇪🇸

💡 حالا نوبت توئه!
این الگو رو با اطلاعات خودت پر کن:

¡Hola! Me llamo _____.
Soy de _____. Tengo _____ años.
Soy _____. Vivo en _____.
¡Mucho gusto! 😊

📲 t.me/vitrinspain""",

    """📍 روز ۷۰ — مکالمه کامل: رستوران 🇪🇸

🙋 Buenos días, una mesa para dos.
👨‍🍳 ¿Qué van a tomar?
🙋 Para mí, la paella. De beber, agua.
👨‍🍳 ¿Algo más?
🙋 No, gracias. La cuenta, por favor.

ترجمه:
صبح بخیر، میز برای دو نفر.
چی میل دارید؟ / برای من پائلا. نوشیدنی آب.
چیز دیگه؟ / نه ممنون. صورتحساب لطفاً.

📲 t.me/vitrinspain""",

    """📍 روز ۷۰ — ادامه 🇪🇸

💡 جملات کاربردی رستوران:

¿Tiene menú del día? = منوی روز دارید؟
¿Está bueno? = خوشمزه‌ست؟
¡Está riquísimo! = خیلی خوشمزه‌ست!
¿Me trae más pan? = نان بیشتر میارید؟
El servicio está incluido = سرویس شامله

📲 t.me/vitrinspain""",

    """📍 روز ۷۱ — مکالمه کامل: خرید 🇪🇸

🙋 ¿Tiene esta camiseta en azul?
🛍️ Sí, ¿qué talla?
🙋 La mediana, por favor.
🛍️ ¿Cuánto cuesta?
🙋 Veinte euros. ¿Acepta tarjeta?
🛍️ Sí. Aquí tiene.

ترجمه:
این تیشرت رنگ آبی دارید؟ / بله، چه سایز؟
متوسط لطفاً. / چقدر میشه؟
بیست یورو. کارت قبول می‌کنید؟ / بله. بفرمایید.

📲 t.me/vitrinspain""",

    """📍 روز ۷۱ — ادامه 🇪🇸

💡 جملات مهم خرید:

¿Puedo devolver esto? = میتونم پسش بدم؟
¿Tiene factura? = فاکتور داری؟
¿Cuánto tiempo de garantía? = ضمانت چند وقته؟
¿Hay descuento si compro dos? = اگه دوتا بخرم تخفیف داری؟

📲 t.me/vitrinspain""",

    """📍 روز ۷۲ — مکالمه کامل: مسیر 🇪🇸

🙋 Perdón, ¿dónde está el metro más cercano?
🧑 Todo recto y luego a la derecha.
🙋 ¿Está lejos?
🧑 No, a cinco minutos a pie.
🙋 Muchas gracias.
🧑 De nada.

ترجمه:
ببخشید، نزدیک‌ترین مترو کجاست؟
مستقیم برو بعد سمت راست.
دوره؟ / نه، پنج دقیقه پیاده.
خیلی ممنون. / خواهش می‌کنم.

📲 t.me/vitrinspain""",

    """📍 روز ۷۲ — ادامه 🇪🇸

💡 جملات مهم مسیر:

¿Está muy lejos? = خیلی دوره؟
¿Cuánto tiempo se tarda? = چقدر طول میکشه؟
¿Puedo ir a pie? = میشه پیاده رفت؟
¿Qué línea de metro? = کدوم خط مترو؟
¿Dónde hay que bajar? = کجا پیاده بشم؟

📲 t.me/vitrinspain""",

    """📍 روز ۷۳ — مکالمه کامل: دکتر 🇪🇸

🙋 Buenos días, tengo cita con el médico.
👩‍⚕️ ¿Cómo se llama?
🙋 Me llamo Dara Ahmadi.
👩‍⚕️ ¿Qué le pasa?
🙋 Me duele mucho la garganta y tengo fiebre.
👩‍⚕️ Voy a examinarle.

ترجمه:
صبح بخیر، وقت دارم با دکتر.
اسمتون؟ / اسمم دارا احمدیه.
چه مشکلی دارید؟
گلوم خیلی درد میکنه و تب دارم.
معاینه‌تون می‌کنم.

📲 t.me/vitrinspain""",

    """📍 روز ۷۳ — ادامه 🇪🇸

💡 جملات مهم دکتر:

¿Desde cuándo? = از کِی؟
¿Tiene alergia a algún medicamento? = به دارویی حساسیت داری؟
¿Tiene el seguro médico? = بیمه درمانی دارید؟
¿Me puede dar la baja? = برگه استعلاجی میدید؟

📲 t.me/vitrinspain""",

    """📍 روز ۷۴ — ۵۰ کلمه پرکاربرد 🇪🇸

sí/no = بله/نه
por favor = لطفاً
gracias = ممنون
perdón = ببخشید
hola/adiós = سلام/خداحافظ
bien/mal = خوب/بد
más/menos = بیشتر/کمتر
mucho/poco = خیلی/کم
aquí/allí = اینجا/آنجا
hoy/mañana = امروز/فردا

📲 t.me/vitrinspain""",

    """📍 روز ۷۴ — ادامه 🇪🇸

ahora/después = الان/بعداً
siempre/nunca = همیشه/هرگز
todo/nada = همه/هیچ
grande/pequeño = بزرگ/کوچیک
nuevo/viejo = جدید/قدیمی
bueno/malo = خوب/بد
fácil/difícil = آسون/سخت
cerca/lejos = نزدیک/دور
abierto/cerrado = باز/بسته
rápido/lento = سریع/آروم

📲 t.me/vitrinspain""",

    # هفته ۱۳: روزهای پایانی
    """📍 روز ۷۵ — گرامر پایه: فعل‌های ar 🇪🇸

hablar = حرف زدن:
hablo = حرف میزنم
hablas = حرف میزنی
habla = حرف میزنه
hablamos = حرف میزنیم
habláis = حرف میزنید
hablan = حرف میزنن

💡 فعل‌های ar همه اینطوری صرف میشن!
مثلاً: trabajar, escuchar, comprar

📲 t.me/vitrinspain""",

    """📍 روز ۷۵ — ادامه 🇪🇸

💡 فعل‌های ar پرکاربرد:

hablar = حرف زدن
trabajar = کار کردن
comprar = خرید کردن
escuchar = گوش دادن
buscar = دنبال گشتن
llamar = زنگ زدن

همه با همون الگوی hablar صرف میشن! 😊

📲 t.me/vitrinspain""",

    """📍 روز ۷۶ — گرامر پایه: فعل‌های er/ir 🇪🇸

comer = خوردن:
como = میخورم
comes = میخوری
come = میخوره
comemos = میخوریم

vivir = زندگی کردن:
vivo = زندگی می‌کنم
vives = زندگی می‌کنی
vive = زندگی می‌کنه

📲 t.me/vitrinspain""",

    """📍 روز ۷۶ — ادامه 🇪🇸

💡 فعل‌های er/ir پرکاربرد:

beber = نوشیدن
leer = خواندن
correr = دویدن
escribir = نوشتن
abrir = باز کردن
salir = رفتن/خروج

سه دسته فعل در اسپانیایی: ar، er، ir 💡

📲 t.me/vitrinspain""",

    """📍 روز ۷۷ — جملات انگیزشی 🇪🇸

¡Sí se puede! = میشه! 💪
Poco a poco = قدم به قدم (بخون: پوکو آ پوکو)
¡Ánimo! = روحیه داشته باش! (بخون: آنیمو)
¡Tú puedes! = تو می‌تونی! (بخون: تو پوئِدِس)
El que la sigue, la consigue = ادامه بده، بهش میرسی

📲 t.me/vitrinspain""",

    """📍 روز ۷۷ — ادامه 🇪🇸

💡 فرهنگ اسپانیایی:

🕐 Siesta = چرت نیمروز — هنوز مرسومه!
💃 Flamenco = رقص فلامنکو — نماد اسپانیا
⚽ Fútbol = فوتبال — دین دوم اسپانیایی‌ها
🍅 La Tomatina = جشن پرتاب گوجه!
🎉 Las Fallas = جشن آتش در والنسیا

📲 t.me/vitrinspain""",

    """📍 روز ۷۸ — قدم بعدی 🇪🇸

بعد از این دوره چیکار کنی؟

📚 سطح A2 یاد بگیر:
گذشته (pretérito)
آینده (futuro)
جملات پیچیده‌تر

🎧 گوش بده به:
پادکست‌های اسپانیایی مبتدی
سریال‌های اسپانیایی با زیرنویس

💬 صحبت کن:
با ایرانی‌های مقیم اسپانیا
اپ Tandem یا HelloTalk

📲 t.me/vitrinspain""",

    """📍 روز ۷۸ — ادامه 🇪🇸

💡 بهترین منابع رایگان:

📱 Duolingo — تمرین روزانه
📺 Dreaming Spanish — یوتیوب
🎙️ SpanishPod101 — پادکست
📖 Anki — کارت‌های حفظیات
🗣️ Language Exchange — مکالمه با بومی

📲 t.me/vitrinspain""",

    """📍 روز ۷۹ — تست نهایی (۱) 🇪🇸

این جملات رو ترجمه کن:

سلام! حالت چطوره؟
→ ¡___! ¿___ ___?

اسمم ساراست و اهل ایرانم.
→ Me ___ Sara y ___ de Irán.

میز برای سه نفر لطفاً.
→ Una ___ para ___, por favor.

جواب‌ها فردا! 😄

📲 t.me/vitrinspain""",

    """📍 روز ۷۹ — ادامه — جواب‌ها! 🇪🇸

✅ ¡Hola! ¿Cómo estás?
✅ Me llamo Sara y soy de Irán.
✅ Una mesa para tres, por favor.

چند تا درست داشتی؟ 😄

📲 t.me/vitrinspain""",

    """📍 روز ۸۰ — تست نهایی (۲) 🇪🇸

این جملات رو ترجمه کن:

دستشویی کجاست؟
→ ¿___ ___ el ___?

چقدر میشه؟
→ ¿___ ___?

تخم‌مرغ دارید؟
→ ¿___ ___?

گلوم درد میکنه.
→ Me ___ la ___.

📲 t.me/vitrinspain""",

    """📍 روز ۸۰ — ادامه — جواب‌ها! 🇪🇸

✅ ¿Dónde está el baño?
✅ ¿Cuánto cuesta?
✅ ¿Tiene huevos?
✅ Me duele la garganta.

آفرین! 🌟

📲 t.me/vitrinspain""",

    """📍 روز ۸۱ — تست نهایی (۳) 🇪🇸

مکالمه زیر رو کامل کن:

🙋 Buenos días, ___ una mesa para dos.
👨‍🍳 ¿Qué ___ a tomar?
🙋 Para mí, la paella. Para beber, ___.
👨‍🍳 ¿Algo más?
🙋 No, gracias. La ___, por favor.

📲 t.me/vitrinspain""",

    """📍 روز ۸۱ — ادامه — جواب‌ها! 🇪🇸

✅ Buenos días, quiero una mesa para dos.
✅ ¿Qué van a tomar?
✅ Para mí, la paella. Para beber, agua.
✅ La cuenta, por favor.

عالیه! رستوران اسپانیا منتظرته! 🍽️

📲 t.me/vitrinspain""",

    """📍 روز ۸۲ — جمع‌بندی کامل دوره 🇪🇸

در این دوره یاد گرفتی:

✅ معرفی و احوال‌پرسی
✅ اعداد، رنگ‌ها، روزها
✅ خانواده و توصیف
✅ فعل‌های اصلی
✅ خانه و اجاره
✅ غذا و رستوران

📲 t.me/vitrinspain""",

    """📍 روز ۸۲ — ادامه 🇪🇸

✅ خرید و مغازه
✅ حمل‌ونقل و شهر
✅ کار و زمان
✅ بانک و اداره
✅ دکتر و اورژانس
✅ سفر و توریسم
✅ احساسات و نظر

💪 این سطح A1 کامله! 🏆

📲 t.me/vitrinspain""",

    """📍 روز ۸۳ — ۱۰ جمله طلایی اسپانیایی 🇪🇸

این ۱۰ جمله رو همیشه میدونی:

¿Puede repetir, por favor? = میتونید تکرار کنید؟
No entiendo = نمی‌فهمم
¿Cómo se dice...? = ... رو چطور میگن؟
¿Habla inglés? = انگلیسی حرف میزنید؟
Estoy aprendiendo español = دارم اسپانیایی یاد میگیرم

📲 t.me/vitrinspain""",

    """📍 روز ۸۳ — ادامه 🇪🇸

No sé = نمیدونم (بخون: نو سه)
¿Puede escribirlo? = میتونید بنویسیدش؟
Habla más despacio, por favor = آروم‌تر حرف بزنید لطفاً
¿Qué significa...? = ... یعنی چی؟
¿Puede ayudarme? = میتونید کمکم کنید؟

💡 این ۱۰ جمله توی هر موقعیتی نجاتت میده! 🌟

📲 t.me/vitrinspain""",

    """📍 روز ۸۴ — پیام آخر 🏆

¡Felicidades! = تبریک!
(بخون: فِلیسیداداس)

۸۴ روز پیش با ¡Hola! شروع کردی
امروز میتونی توی اسپانیا زندگی کنی! 💪

¡Hasta pronto! = تا زود!
(بخون: آستا پِرونتو)

ما اینجاییم برای سطح A2 هم!
📲 t.me/vitrinspain

🇪🇸 Vitrin Spanish""",
]


def load_day():
    """شماره روز جاری رو از فایل بخون"""
    if os.path.exists(DAY_FILE):
        with open(DAY_FILE, "r") as f:
            data = json.load(f)
            return data.get("day", 0)
    return 0


def save_day(day):
    """شماره روز رو ذخیره کن"""
    with open(DAY_FILE, "w") as f:
        json.dump({"day": day}, f)


async def send_lessons():
    """دو پست بعدی رو به هر دو کانال بفرست"""
    bot = Bot(token=BOT_TOKEN)

    current_day = load_day()

    if current_day >= len(LESSONS):
        print("✅ همه درس‌ها ارسال شدن!")
        return

    # دو پست ارسال کن
    posts_to_send = LESSONS[current_day:current_day + 2]

    for post in posts_to_send:
        for channel_id in CHANNELS:
            try:
                await bot.send_message(
                    chat_id=channel_id,
                    text=post,
                    parse_mode=None
                )
                print(f"✅ ارسال شد به کانال {channel_id}")
                await asyncio.sleep(2)  # ۲ ثانیه صبر بین پیام‌ها
            except Exception as e:
                print(f"❌ خطا در ارسال به {channel_id}: {e}")

        await asyncio.sleep(5)  # ۵ ثانیه بین دو پست

    # روز رو آپدیت کن
    save_day(current_day + 2)
    print(f"📅 روز آپدیت شد: {current_day + 2} از {len(LESSONS)}")


if __name__ == "__main__":
    asyncio.run(send_lessons())
