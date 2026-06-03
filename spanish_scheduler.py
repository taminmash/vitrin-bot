#!/usr/bin/env python3
import asyncio
import json
import os
from telegram import Bot
from playwright.sync_api import sync_playwright
from config import BOT_TOKEN

CHANNELS = [
    -1003945260173,
    -1003854428039,
]

DAY_FILE = "spanish_day.json"

LESSONS = [
    {"day": "روز ۱", "word": "¡Hola!", "pronunciation": "بخون: اولا", "meaning": "یعنی: سلام! 👋", "tip": "اسپانیایی‌ها علامت تعجب رو از <b>اول جمله هم</b> می‌نویسن ¡<br>خاصه نه؟ 😄"},
    {"day": "روز ۱ — ادامه", "word": "¡Adiós!", "pronunciation": "بخون: آدیوس", "meaning": "یعنی: خداحافظ! 👋", "tip": "وقتی از مغازه یا جایی خارج میشی بگو <b>¡Adiós!</b><br>خیلی طبیعی‌تره 😊"},
    {"day": "روز ۲", "word": "¿Cómo estás?", "pronunciation": "بخون: کومو استاس", "meaning": "یعنی: حالت چطوره؟ 🙂", "tip": "جواب ساده:<br><b>Bien, gracias</b> = خوبم، ممنون"},
    {"day": "روز ۲ — ادامه", "word": "¿Y tú?", "pronunciation": "بخون: ای تو", "meaning": "یعنی: تو چطور؟ 🙂", "tip": "بعد از <b>Bien, gracias</b> بگو <b>¿Y tú?</b><br>مکالمه کامل میشه! 😊"},
    {"day": "روز ۳", "word": "¿Cómo te llamas?", "pronunciation": "بخون: کومو ته یاماس", "meaning": "یعنی: اسمت چیه؟ 👤", "tip": "جواب:<br><b>Me llamo Sara</b> = اسمم ساراست"},
    {"day": "روز ۳ — ادامه", "word": "Me llamo...", "pronunciation": "بخون: مه یامو", "meaning": "یعنی: صدام می‌کنن... 👤", "tip": "ترجمه تحت‌اللفظی: «صدام می‌کنن...»<br>نه «اسمم هست»! اسپانیایی جالبه 😄"},
    {"day": "روز ۴", "word": "¿De dónde eres?", "pronunciation": "بخون: ده دونده ارِس", "meaning": "یعنی: اهل کجایی؟ 🌍", "tip": "جواب:<br><b>Soy de Irán</b> = اهل ایرانم 🇮🇷"},
    {"day": "روز ۴ — ادامه", "word": "Soy de Irán", "pronunciation": "بخون: سوی ده ایران", "meaning": "یعنی: اهل ایرانم 🇮🇷", "tip": "<b>Soy de España</b> = اهل اسپانیام 🇪🇸<br><b>Soy de Teherán</b> = اهل تهرانم"},
    {"day": "روز ۵", "word": "Tengo 30 años", "pronunciation": "بخون: تنگو تِرِئینتا آنیوس", "meaning": "یعنی: سی سالمه 🎂", "tip": "¿Cuántos años tienes? = چند سالته؟<br>ترجمه تحت‌اللفظی: <b>سال دارم</b> 😄"},
    {"day": "روز ۵ — ادامه", "word": "Mucho gusto", "pronunciation": "بخون: موچو گوستو", "meaning": "یعنی: خوشحال شدم 🤝", "tip": "جواب:<br><b>Igualmente</b> = منم همینطور 🤝"},
    {"day": "روز ۶", "word": "uno, dos, tres", "pronunciation": "بخون: اونو، دوس، تِرِس", "meaning": "یعنی: ۱، ۲، ۳ 🔢", "tip": "<b>uno</b> قبل از اسم میشه <b>un</b><br>un café = یه قهوه ☕"},
    {"day": "روز ۶ — ادامه", "word": "cuatro, cinco, seis", "pronunciation": "بخون: کواترو، سینکو، سِئیس", "meaning": "یعنی: ۴، ۵، ۶ 🔢", "tip": "siete=۷، ocho=۸، nueve=۹، diez=۱۰<br>Mesa para dos = میز برای دو نفر 🍽️"},
    {"day": "روز ۷", "word": "rojo, azul, verde", "pronunciation": "بخون: روخو، آثول، وِرده", "meaning": "یعنی: قرمز 🔴 آبی 🔵 سبز 🟢", "tip": "رنگ توی اسپانیایی <b>بعد از اسم</b> میاد!<br>coche rojo = ماشین قرمز 🚗"},
    {"day": "روز ۷ — ادامه", "word": "amarillo, blanco, negro", "pronunciation": "بخون: آماریو، بلانکو، نِگرو", "meaning": "یعنی: زرد 🟡 سفید ⚪ مشکی ⚫", "tip": "¿De qué color es? = چه رنگیه؟ 🎨<br>naranja = نارنجی 🟠 | rosa = صورتی 🌸"},
    {"day": "روز ۸", "word": "lunes ... domingo", "pronunciation": "بخون: لونِس ... دومینگو", "meaning": "یعنی: روزهای هفته 📅", "tip": "هفته اسپانیایی از <b>دوشنبه</b> شروع میشه!<br>Hoy es lunes = امروز دوشنبه‌ست"},
    {"day": "روز ۸ — ادامه", "word": "enero ... diciembre", "pronunciation": "بخون: اِنِرو ... دیسیِمبِره", "meaning": "یعنی: ماه‌های سال 📆", "tip": "hoy = امروز | mañana = فردا<br>ayer = دیروز | ahora = الان"},
    {"day": "روز ۹", "word": "padre, madre, hermano", "pronunciation": "بخون: پادِره، مادِره، اِرمانو", "meaning": "یعنی: پدر، مادر، برادر 👨‍👩‍👦", "tip": "mi = مال من<br>mi padre = پدرم | mi madre = مادرم 😊"},
    {"day": "روز ۹ — ادامه", "word": "esposo/a, novio/a", "pronunciation": "بخون: اِسپوسو/آ، نوویو/آ", "meaning": "یعنی: شوهر/زن، نامزد 💑", "tip": "tío = عمو/دایی | tía = عمه/خاله<br>اسپانیایی بین عمو و دایی فرق نمیذاره! 😄"},
    {"day": "روز ۱۰", "word": "alto, simpático, amable", "pronunciation": "بخون: آلتو، سیمپاتیکو، آمابله", "meaning": "یعنی: قد بلند، خوش‌برخورد، مهربان 😊", "tip": "صفت مذکر و مؤنث فرق داره!<br>él es alto / ella es alta"},
    {"day": "روز ۱۰ — ادامه", "word": "yo, tú, él/ella, nosotros", "pronunciation": "بخون: یو، تو، اِل/اِیا، نوسوتروس", "meaning": "یعنی: من، تو، او، ما 👥", "tip": "توی اسپانیایی ضمیر معمولاً <b>حذف</b> میشه!<br>فعل خودش شخص رو نشون میده 😊"},
    {"day": "روز ۱۱", "word": "soy, eres, es, somos", "pronunciation": "بخون: سوی، اِرِس، اِس، سوموس", "meaning": "یعنی: منم، تویی، اوست، ماییم 🔵", "tip": "فعل <b>ser</b> = بودن (ثابت)<br>Soy iraní = ایرانیم<br>Eres muy simpático = خیلی خوش‌برخوردی"},
    {"day": "روز ۱۱ — ادامه", "word": "estoy, estás, está", "pronunciation": "بخون: استوی، استاس، استا", "meaning": "یعنی: هستم، هستی، هست 🟡", "tip": "<b>ser</b> = ثابت (ایرانیم)<br><b>estar</b> = موقت (خوبم/اینجام)<br>Estoy cansado = خسته‌ام"},
    {"day": "روز ۱۲", "word": "tengo, tienes, tiene", "pronunciation": "بخون: تنگو، تیِنِس، تیِنه", "meaning": "یعنی: دارم، داری، داره 🤲", "tip": "Tengo hambre = گرسنمه<br>Tengo 30 años = سی سالمه<br>¿Tienes coche? = ماشین داری؟ 🚗"},
    {"day": "روز ۱۲ — ادامه", "word": "salón, cocina, baño", "pronunciation": "بخون: سالون، کوسینا، بانیو", "meaning": "یعنی: پذیرایی، آشپزخانه، حمام 🏠", "tip": "مهم‌ترین جمله:<br><b>¿Dónde está el baño?</b> = دستشویی کجاست؟ 😅"},
    {"day": "روز ۱۳", "word": "mesa, cama, sofá, nevera", "pronunciation": "بخون: مِسا، کاما، سوفا، نِوِرا", "meaning": "یعنی: میز، تخت، مبل، یخچال 🪑", "tip": "hay = هست/وجود داره<br>Hay una mesa = یه میز هست 😊"},
    {"day": "روز ۱۳ — ادامه", "word": "en, sobre, debajo de", "pronunciation": "بخون: اِن، سوبِره، دِباخو ده", "meaning": "یعنی: توی، روی، زیر 📍", "tip": "al lado de = کنار<br>delante de = جلوی<br>detrás de = پشت"},
    {"day": "روز ۱۴", "word": "grande, pequeño, bonito", "pronunciation": "بخون: گرانده، پِکِنیو، بونیتو", "meaning": "یعنی: بزرگ، کوچیک، قشنگ 🏠", "tip": "alquiler = اجاره | fianza = ودیعه<br>¿Están incluidos los gastos? = هزینه‌ها شامله؟"},
    {"day": "روز ۱۴ — ادامه", "word": "calle, plaza, barrio", "pronunciation": "بخون: کایه، پلاثا، باریو", "meaning": "یعنی: خیابان، میدان، محله 🏙️", "tip": "cerca = نزدیک | lejos = دور<br>Está a diez minutos a pie = ده دقیقه پیاده"},
    {"day": "روز ۱۵ — مرور ماه اول 🎉", "word": "¡Un mes!", "pronunciation": "بخون: اون مِس", "meaning": "یعنی: یه ماه! 🏆", "tip": "✅ احوال‌پرسی ✅ اعداد و رنگ‌ها<br>✅ خانواده ✅ فعل‌های اصلی<br>✅ خانه ✅ محله<br>ماه دوم: زندگی روزمره! 🌟"},
    {"day": "روز ۱۵ — ادامه", "word": "desayuno, almuerzo, cena", "pronunciation": "بخون: دِسایونو، آلموئِرثو، سِنا", "meaning": "یعنی: صبحانه، ناهار، شام 🍽️", "tip": "اسپانیایی‌ها شام رو ساعت ۹-۱۰ شب می‌خورن! 🌙<br>ناهار مهم‌ترین وعده‌ست"},
    {"day": "روز ۱۶", "word": "pan, leche, huevo, fruta", "pronunciation": "بخون: پان، لِچه، وئِوو، فروتا", "meaning": "یعنی: نان، شیر، تخم‌مرغ، میوه 🥚", "tip": "carne = گوشت | arroz = برنج<br>¿Tiene huevos? = تخم‌مرغ داری؟ 🛒"},
    {"day": "روز ۱۶ — ادامه", "word": "agua, café, té, zumo", "pronunciation": "بخون: آگوا، کافه، ته، ثومو", "meaning": "یعنی: آب، قهوه، چای، آب‌میوه ☕", "tip": "Un café con leche, por favor = یه قهوه با شیر لطفاً ☕<br>café solo = اسپرسو"},
    {"day": "روز ۱۷", "word": "Una mesa para dos", "pronunciation": "بخون: اونا مِسا پارا دوس", "meaning": "یعنی: میز برای دو نفر 🍽️", "tip": "La carta, por favor = منو لطفاً<br>¿Qué recomienda? = چی پیشنهاد میدی؟"},
    {"day": "روز ۱۷ — ادامه", "word": "Para mí la paella", "pronunciation": "بخون: پارا می لا پائلا", "meaning": "یعنی: برای من پائلا 🥘", "tip": "¡Está delicioso! = خیلی خوشمزه‌ست!<br>La cuenta, por favor = صورتحساب لطفاً"},
    {"day": "روز ۱۸", "word": "farmacia, supermercado", "pronunciation": "بخون: فارماسیا، سوپِرمِرکادو", "meaning": "یعنی: داروخانه، سوپرمارکت 🏪", "tip": "farmacia با صلیب سبز مشخصه ✚<br>panadería = نانوایی | carnicería = قصابی"},
    {"day": "روز ۱۸ — ادامه", "word": "¿Cuánto cuesta?", "pronunciation": "بخون: کوانتو کوئِستا", "meaning": "یعنی: چقدر میشه؟ 💰", "tip": "caro = گرونه | barato = ارزونه<br>rebaja = تخفیف | oferta = حراج<br>¿Acepta tarjeta? = کارت قبول می‌کنید؟"},
    {"day": "روز ۱۹", "word": "talla, mediano, grande", "pronunciation": "بخون: تایا، مِدیانو، گرانده", "meaning": "یعنی: سایز، متوسط، بزرگ 👗", "tip": "¿Puedo probármelo? = میتونم امتحان کنم؟<br>Me queda bien = خوب بهم میاد"},
    {"day": "روز ۱۹ — ادامه", "word": "metro, autobús, tren", "pronunciation": "بخون: مِترو، آئوتوبوس، تِرِن", "meaning": "یعنی: مترو، اتوبوس، قطار 🚇", "tip": "abono mensual = کارت ماهانه<br>بهترین گزینه برای مادرید! 💳"},
    {"day": "روز ۲۰", "word": "¿Dónde está...?", "pronunciation": "بخون: دونده استا", "meaning": "یعنی: ... کجاست؟ 📍", "tip": "todo recto = مستقیم ➡️<br>a la derecha = راست | a la izquierda = چپ"},
    {"day": "روز ۲۰ — ادامه", "word": "billete, abono", "pronunciation": "بخون: بیِتِه، آبونو", "meaning": "یعنی: بلیت، کارت ماهانه 🎫", "tip": "ayuntamiento = شهرداری<br>hospital = بیمارستان<br>embajada = سفارت"},
    {"day": "روز ۲۱", "word": "¿Qué hora es?", "pronunciation": "بخون: که اورا اِس", "meaning": "یعنی: ساعت چنده؟ ⏰", "tip": "Son las tres = ساعت ۳<br>y media = و نیم | y cuarto = و ربع"},
    {"day": "روز ۲۱ — ادامه", "word": "levantarse, ducharse", "pronunciation": "بخون: لِوانتارسه، دوچارسه", "meaning": "یعنی: بیدار شدن، دوش گرفتن 🚿", "tip": "Me levanto a las siete = ساعت ۷ بیدار میشم<br>فعل‌های se = کار روی خودت"},
    {"day": "روز ۲۲", "word": "médico, abogado, ingeniero", "pronunciation": "بخون: مِدیکو، آبوگادو، اینخِنیِرو", "meaning": "یعنی: دکتر، وکیل، مهندس 👷", "tip": "¿A qué te dedicas? = چیکاره‌ای؟<br>Soy ingeniero = مهندسم 💼<br>autónomo = خوداشتغال"},
    {"day": "روز ۲۲ — ادامه", "word": "sueldo, contrato, vacaciones", "pronunciation": "بخون: سوئِلدو، کونتِراتو، واکاسیونِس", "meaning": "یعنی: حقوق، قرارداد، تعطیلات 💼", "tip": "¿Cuánto es el sueldo neto? = حقوق خالص چقدره؟<br>۲۲ روز مرخصی سالانه حق توست! 🏖️"},
    {"day": "روز ۲۳ — نصف راه! 🏆", "word": "¡A mitad!", "pronunciation": "بخون: آ میتاد", "meaning": "یعنی: نصف راه! 🏆", "tip": "✅ وعده‌های غذایی ✅ خرید<br>✅ حمل‌ونقل ✅ مشاغل<br>✅ ساعت ✅ روتین روزانه<br>💪 ادامه بده!"},
    {"day": "روز ۲۳ — ادامه", "word": "NIE", "pronunciation": "بخون: ان-ای-ای", "meaning": "یعنی: شماره شناسایی خارجی 🪪", "tip": "مهم‌ترین مدرک برای زندگی در اسپانیا!<br>بدون NIE هیچ کاری نمیشه کرد 🔑"},
    {"day": "روز ۲۴", "word": "cuenta bancaria, IBAN", "pronunciation": "بخون: کوئِنتا بانکاریا، ایبان", "meaning": "یعنی: حساب بانکی، شماره بین‌المللی 🏦", "tip": "Quiero abrir una cuenta = می‌خوام حساب باز کنم<br>cajero automático = خودپرداز 🏧"},
    {"day": "روز ۲۴ — ادامه", "word": "cita previa", "pronunciation": "بخون: سیتا پِرِویا", "meaning": "یعنی: وقت قبلی 📋", "tip": "برای هر کار اداری باید cita previa بگیری<br>آنلاین روی سایت دولتی 💻<br>empadronamiento = ثبت محل سکونت"},
    {"day": "روز ۲۵", "word": "Me duele la garganta", "pronunciation": "بخون: مه دوئِله لا گارگانتا", "meaning": "یعنی: گلوم درد میکنه 🤒", "tip": "la cabeza = سر | el estómago = معده<br>Tengo fiebre = تب دارم | Tengo tos = سرفه دارم"},
    {"day": "روز ۲۵ — ادامه", "word": "receta, pastilla, jarabe", "pronunciation": "بخون: رِسِتا، پاستیا، خاراب", "meaning": "یعنی: نسخه، قرص، شربت 💊", "tip": "¿Tiene algo para el dolor de cabeza?<br>= چیزی برای سردرد دارید؟<br>tres veces al día = روزی سه بار"},
    {"day": "روز ۲۶", "word": "¡Ayuda! ¡Llame al 112!", "pronunciation": "بخون: آیودا! یامه آل سیِنتودوسه", "meaning": "یعنی: کمک! با ۱۱۲ تماس بگیرید! 🚨", "tip": "<b>112</b> = شماره اورژانس اسپانیا 🚨<br>Me han robado = دزدیده شدم<br>Estoy perdido = گم شدم"},
    {"day": "روز ۲۶ — ادامه", "word": "seguro médico, tarjeta sanitaria", "pronunciation": "بخون: سِگورو مِدیکو، تارخِتا سانیتاریا", "meaning": "یعنی: بیمه درمانی، کارت بیمه 🏥", "tip": "médico de cabecera = پزشک عمومی<br>urgencias = اورژانس بیمارستان<br>بعد از NIE باید بیمه بگیری! 🏥"},
    {"day": "روز ۲۷", "word": "vuelo, equipaje, aduana", "pronunciation": "بخون: بوئِلو، اِکیپاخه، آدوانا", "meaning": "یعنی: پرواز، چمدان، گمرک ✈️", "tip": "puerta de embarque = گیت<br>retraso = تأخیر | cancelado = لغو شده"},
    {"day": "روز ۲۷ — ادامه", "word": "reserva, habitación", "pronunciation": "بخون: رِسِروا، آبیتاسیون", "meaning": "یعنی: رزرو، اتاق 🏨", "tip": "¿Está incluido el desayuno? = صبحانه شامله؟<br>¿Hay wifi? = وای‌فای دارید؟<br>individual = یک‌نفره | doble = دونفره"},
    {"day": "روز ۲۸", "word": "museo, playa, castillo", "pronunciation": "بخون: موسئو، پلایا، کاستیو", "meaning": "یعنی: موزه، ساحل، قلعه 🏰", "tip": "¿Qué hay que ver aquí? = اینجا چی دیدنی داره؟<br>entrada = بلیت ورودی | gratis = رایگان"},
    {"day": "روز ۲۸ — ادامه", "word": "hace calor, hace frío, llueve", "pronunciation": "بخون: آسه کالور، آسه فریو، یوئِوه", "meaning": "یعنی: گرمه، سرده، باران میاد ☀️❄️🌧️", "tip": "¿Qué tiempo hace? = هوا چطوره؟<br>Madrid = خشک ☀️ | Barcelona = مدیترانه‌ای 🌊"},
    {"day": "روز ۲۹", "word": "estoy feliz, triste, cansado", "pronunciation": "بخون: فِلیث، تِریسته، کانسادو", "meaning": "یعنی: خوشحالم، ناراحتم، خسته‌ام 😊😢😴", "tip": "tengo hambre = گرسنمه<br>tengo sueño = خوابم میاد<br>tengo prisa = عجله دارم"},
    {"day": "روز ۲۹ — ادامه", "word": "me encanta, me gusta", "pronunciation": "بخون: مه اِنکانتا، مه گوستا", "meaning": "یعنی: عاشقشم، دوستش دارم ❤️", "tip": "Me encanta España = عاشق اسپانیام ❤️<br>No me gusta nada = اصلاً دوستش ندارم"},
    {"day": "روز ۳۰", "word": "De acuerdo, Claro, Quizás", "pronunciation": "بخون: آکوئِردو، کلارو، کیثاس", "meaning": "یعنی: موافقم، البته، شاید 👍", "tip": "Tienes razón = حق داری<br>Depende = بستگی داره<br>Exactamente = دقیقاً"},
    {"day": "روز ۳۰ — ادامه", "word": "Creo que... / Me parece bien", "pronunciation": "بخون: کِرئو که / مه پارِسه بیِن", "meaning": "یعنی: فکر می‌کنم / به نظرم خوبه 💭", "tip": "Muchas gracias = خیلی ممنون<br>Lo siento = متأسفم<br>No pasa nada = اشکالی نداره"},
    {"day": "روز ۳۱ — مکالمه کامل: معرفی", "word": "¡Hola! Me llamo Dara.", "pronunciation": "بخون: مه یامو دارا", "meaning": "یعنی: سلام! اسمم داراست 👤", "tip": "Soy de Irán. Tengo 32 años.<br>Soy ingeniero. Vivo en Madrid.<br>Estoy aprendiendo español! 😄"},
    {"day": "روز ۳۱ — مکالمه کامل: رستوران", "word": "Una mesa para dos, por favor", "pronunciation": "بخون: اونا مِسا پارا دوس", "meaning": "یعنی: میز برای دو نفر 🍽️", "tip": "Para mí, la paella. De beber, agua.<br>¡Está delicioso! La cuenta, por favor.<br>= برای من پائلا. خوشمزه! صورتحساب."},
    {"day": "روز ۳۲ — مکالمه کامل: خرید", "word": "¿Tiene esta camiseta en azul?", "pronunciation": "بخون: کامیسِتا اِن آثول", "meaning": "یعنی: این تیشرت رنگ آبی دارید؟ 👕", "tip": "La mediana, por favor. ¿Cuánto cuesta?<br>Veinte euros. ¿Acepta tarjeta?<br>= متوسط. بیست یورو. کارت قبول می‌کنید؟"},
    {"day": "روز ۳۲ — مکالمه کامل: مسیر", "word": "¿Dónde está el metro más cercano?", "pronunciation": "بخون: دونده استا اِل مِترو", "meaning": "یعنی: نزدیک‌ترین مترو کجاست؟ 🚇", "tip": "Todo recto y luego a la derecha.<br>A cinco minutos a pie.<br>= مستقیم، بعد راست. پنج دقیقه پیاده."},
    {"day": "روز ۳۳ — مکالمه کامل: دکتر", "word": "Me duele la garganta y tengo fiebre", "pronunciation": "بخون: مه دوئِله لا گارگانتا", "meaning": "یعنی: گلوم درد میکنه و تب دارم 🤒", "tip": "Tengo cita con el médico.<br>¿Desde cuándo? = از کِی؟<br>¿Tiene alergia? = حساسیت داری؟"},
    {"day": "روز ۳۳ — گرامر: فعل‌های ar", "word": "hablar = حرف زدن", "pronunciation": "بخون: آبلار", "meaning": "یعنی: حرف زدن 🗣️", "tip": "hablo / hablas / habla<br>hablamos / habláis / hablan<br>trabajar, comprar, escuchar هم اینطوری! 😊"},
    {"day": "روز ۳۴", "word": "comer, vivir, escribir", "pronunciation": "بخون: کومِر، بیبیر، اِسکِریبیر", "meaning": "یعنی: خوردن، زندگی کردن، نوشتن 📝", "tip": "como / comes / come / comemos<br>vivo / vives / vive / vivimos<br>سه دسته فعل: ar، er، ir 💡"},
    {"day": "روز ۳۴ — ادامه", "word": "¿Puede repetir, por favor?", "pronunciation": "بخون: پوئِده رِپِتیر، پور فاوور", "meaning": "یعنی: میتونید تکرار کنید؟ 🔄", "tip": "No entiendo = نمی‌فهمم<br>Habla más despacio = آروم‌تر حرف بزنید<br>¿Puede ayudarme? = کمکم می‌کنید؟"},
    {"day": "روز ۳۵ — ۲۰ کلمه طلایی ✨", "word": "por favor, gracias, perdón", "pronunciation": "بخون: پور فاوور، گراسیاس، پِردون", "meaning": "یعنی: لطفاً، ممنون، ببخشید ✨", "tip": "De nada = خواهش می‌کنم<br>No pasa nada = اشکالی نداره<br>siempre/nunca = همیشه/هرگز"},
    {"day": "روز ۳۵ — ادامه", "word": "¡Sí se puede!", "pronunciation": "بخون: سی سه پوئِده", "meaning": "یعنی: میشه! 💪", "tip": "Poco a poco = قدم به قدم<br>¡Ánimo! = روحیه داشته باش!<br>¡Tú puedes! = تو می‌تونی! 🌟"},
    {"day": "روز ۳۶ — Madrid 🏛️", "word": "Madrid, la capital", "pronunciation": "بخون: مادِرید، لا کاپیتال", "meaning": "یعنی: مادرید، پایتخت 🏛️", "tip": "Barcelona = بارسلونا — گائودی 🏗️<br>Valencia = والنسیا — پائلا 🥘<br>Sevilla = سویل — فلامنکو 💃"},
    {"day": "روز ۳۶ — فرهنگ اسپانیایی", "word": "Siesta, Flamenco, Fútbol", "pronunciation": "بخون: سیِستا، فلامِنکو، فوتبول", "meaning": "یعنی: چرت نیمروز، فلامنکو، فوتبال 💃⚽", "tip": "🕐 Siesta هنوز مرسومه!<br>🍅 La Tomatina = جشن پرتاب گوجه<br>🎉 Las Fallas = جشن آتش در والنسیا"},
    {"day": "روز ۳۷ — تست نهایی ✅", "word": "¡A examinarse!", "pronunciation": "بخون: آ اِکسامینارسه", "meaning": "یعنی: وقت تست! 📝", "tip": "✅ ¡Hola! ¿Cómo estás?<br>✅ Me llamo... Soy de Irán.<br>✅ Una mesa para dos, por favor."},
    {"day": "روز ۳۷ — ادامه", "word": "Nivel A2 — قدم بعدی", "pronunciation": "بخون: نیوِل آ دوس", "meaning": "یعنی: سطح A2 📚", "tip": "📚 pretérito = گذشته<br>📚 futuro = آینده<br>📱 Duolingo | 📺 Dreaming Spanish"},
    {"day": "روز ۳۸ — جمع‌بندی کامل 🏆", "word": "Lo que aprendiste", "pronunciation": "بخون: لو که آپِرِندیسته", "meaning": "یعنی: چیزی که یاد گرفتی 🏆", "tip": "✅ معرفی ✅ اعداد و رنگ‌ها<br>✅ خانواده ✅ فعل‌های اصلی<br>✅ خانه ✅ غذا ✅ خرید<br>✅ حمل‌ونقل ✅ دکتر ✅ احساسات"},
    {"day": "روز ۳۸ — ادامه", "word": "¡Felicidades!", "pronunciation": "بخون: فِلیسیداداس", "meaning": "یعنی: تبریک! 🎉", "tip": "۷۶ روز پیش با ¡Hola! شروع کردی!<br>امروز A1 کاملته! 💪<br>¡Hasta pronto! = تا زود! 🇪🇸"},
]


def generate_card_html(lesson):
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Vazirmatn:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ width: 420px; height: 520px; background: transparent; font-family: 'Vazirmatn', 'DejaVu Sans', sans-serif; }}
  .card {{ width: 420px; height: 520px; border-radius: 28px; position: relative; overflow: hidden; }}
  .card::before {{ content: ''; position: absolute; inset: 0; background: linear-gradient(145deg, #c0392b 0%, #922b21 40%, #1a1a2e 100%); z-index: 0; }}
  .card::after {{ content: ''; position: absolute; width: 320px; height: 320px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.08); top: -80px; left: -60px; z-index: 1; }}
  .dots {{ position: absolute; bottom: 80px; right: 24px; display: grid; grid-template-columns: repeat(4, 6px); gap: 5px; z-index: 1; opacity: 0.2; }}
  .dots span {{ width: 6px; height: 6px; border-radius: 50%; background: #fff; display: block; }}
  .card-inner {{ position: relative; z-index: 2; height: 100%; display: flex; flex-direction: column; padding: 28px; }}
  .top-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
  .day-badge {{ background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.2); color: #fff; font-size: 12px; font-weight: 600; padding: 6px 14px; border-radius: 20px; }}
  .flag {{ font-size: 28px; }}
  .main-word {{ font-family: 'Playfair Display', serif; font-size: 46px; font-weight: 900; color: #fff; line-height: 1.1; margin-bottom: 8px; text-shadow: 0 4px 20px rgba(0,0,0,0.3); direction: ltr; text-align: right; }}
  .pronunciation {{ color: rgba(255,220,100,0.9); font-size: 14px; font-weight: 600; margin-bottom: 6px; direction: rtl; }}
  .meaning {{ color: rgba(255,255,255,0.9); font-size: 19px; font-weight: 700; margin-bottom: 16px; }}
  .divider {{ width: 48px; height: 3px; background: rgba(255,220,100,0.7); border-radius: 2px; margin-bottom: 14px; }}
  .tip-box {{ background: rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 14px 16px; flex: 1; display: flex; align-items: flex-start; gap: 10px; }}
  .tip-icon {{ font-size: 20px; flex-shrink: 0; margin-top: 2px; }}
  .tip-text {{ color: rgba(255,255,255,0.85); font-size: 13px; line-height: 1.8; }}
  .tip-text b {{ color: rgba(255,220,100,0.95); font-weight: 700; }}
  .bottom-bar {{ display: flex; justify-content: space-between; align-items: center; margin-top: 14px; }}
  .brand {{ color: rgba(255,255,255,0.4); font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; direction: ltr; }}
  .channel {{ color: rgba(255,220,100,0.7); font-size: 11px; font-weight: 600; }}
</style>
</head>
<body>
<div class="card">
  <div class="dots"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
  <div class="card-inner">
    <div class="top-bar">
      <div class="day-badge">📍 {lesson['day']}</div>
      <div class="flag">🇪🇸</div>
    </div>
    <div class="main-word">{lesson['word']}</div>
    <div class="pronunciation">🔊 {lesson['pronunciation']}</div>
    <div class="meaning">{lesson['meaning']}</div>
    <div class="divider"></div>
    <div class="tip-box">
      <div class="tip-icon">💡</div>
      <div class="tip-text">{lesson['tip']}</div>
    </div>
    <div class="bottom-bar">
      <div class="channel">📲 t.me/vitrinspain</div>
      <div class="brand">VITRIN SPANISH</div>
    </div>
  </div>
</div>
</body>
</html>"""


def create_card_image(lesson, output_path):
    html_content = generate_card_html(lesson)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 420, "height": 520})
        page.set_content(html_content)
        page.wait_for_timeout(2000)
        page.screenshot(path=output_path, clip={"x": 0, "y": 0, "width": 420, "height": 520})
        browser.close()


def load_day():
    if os.path.exists(DAY_FILE):
        with open(DAY_FILE, "r") as f:
            return json.load(f).get("day", 0)
    return 0


def save_day(day):
    with open(DAY_FILE, "w") as f:
        json.dump({"day": day}, f)


async def send_lessons():
    bot = Bot(token=BOT_TOKEN)
    current_day = load_day()

    if current_day >= len(LESSONS):
        print("✅ همه درس‌ها ارسال شدن!")
        return

    posts_to_send = LESSONS[current_day:current_day + 2]

    for i, lesson in enumerate(posts_to_send):
        img_path = f"/tmp/spanish_card_{i}.png"
        print(f"🎨 در حال ساخت تصویر: {lesson['day']}")
        create_card_image(lesson, img_path)

        for channel_id in CHANNELS:
            try:
                with open(img_path, "rb") as img:
                    await bot.send_photo(chat_id=channel_id, photo=img)
                print(f"✅ ارسال شد به {channel_id}")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"❌ خطا: {e}")

        if os.path.exists(img_path):
            os.remove(img_path)

        await asyncio.sleep(5)

    save_day(current_day + 2)
    print(f"📅 روز آپدیت شد: {current_day + 2} از {len(LESSONS)}")


if __name__ == "__main__":
    asyncio.run(send_lessons())
