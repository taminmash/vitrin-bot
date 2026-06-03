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
    {"lesson": "درس ۱", "word": "¡Hola!", "pronunciation": "اُلا", "meaning": "یعنی: سلام! 👋", "tip": "نکته: حرف <b>H</b> در اسپانیایی همیشه ساکته!<br>hola = اُلا — نه هولا 😊"},
    {"lesson": "درس ۲", "word": "¡Adiós!", "pronunciation": "آدیوس", "meaning": "یعنی: خداحافظ! 👋", "tip": "نکته: <b>ó</b> یعنی تکیه روی این هجاست<br>آ-دی-اُس — هر هجا جدا و واضح 😊"},
    {"lesson": "درس ۳", "word": "¿Cómo estás?", "pronunciation": "کُمُ اِستاس", "meaning": "یعنی: حالت چطوره؟ 🙂", "tip": "نکته: <b>¿</b> علامت سوال از اول جمله میاد!<br>Bien, gracias = بیِن، گِراثیاس = خوبم، ممنون"},
    {"lesson": "درس ۴", "word": "¿Y tú?", "pronunciation": "ای تو", "meaning": "یعنی: تو چطور؟ 🙂", "tip": "نکته: <b>Y</b> در اسپانیایی یعنی «و» یا «ای»<br>بعد از Bien, gracias بگو ¿Y tú? 😊"},
    {"lesson": "درس ۵", "word": "¿Cómo te llamas?", "pronunciation": "کُمُ تِه یاماس", "meaning": "یعنی: اسمت چیه؟ 👤", "tip": "نکته: <b>LL</b> در اسپانیایی مثل «ی» فارسیه<br>llamas = یاماس — نه لاماس! 😄"},
    {"lesson": "درس ۶", "word": "Me llamo...", "pronunciation": "مِه یامُ", "meaning": "یعنی: صدام می‌کنن... 👤", "tip": "نکته: <b>LL</b> = «ی» — llamo = یامُ<br>ترجمه واقعی: «صدام می‌کنن...» نه «اسمم هست» 😄"},
    {"lesson": "درس ۷", "word": "¿De dónde eres?", "pronunciation": "دِه دُندِه اِرِس", "meaning": "یعنی: اهل کجایی؟ 🌍", "tip": "نکته: <b>D</b> بین دو vowel نرم میشه — مثل «ذ»<br>Soy de Irán = سُی دِه ایران = اهل ایرانم 🇮🇷"},
    {"lesson": "درس ۸", "word": "Soy de Irán", "pronunciation": "سُی دِه ایران", "meaning": "یعنی: اهل ایرانم 🇮🇷", "tip": "نکته: <b>OY</b> در soy مثل «اُی» سریع<br>Soy de España = سُی دِه اِسپانیا 🇪🇸"},
    {"lesson": "درس ۹", "word": "Tengo 30 años", "pronunciation": "تِنگُ تِرِئینتا آنیُس", "meaning": "یعنی: سی سالمه 🎂", "tip": "نکته: <b>Ñ</b> مثل «نی» فارسیه — años = آنیُس<br>¿Cuántos años tienes? = چند سالته؟"},
    {"lesson": "درس ۱۰", "word": "Mucho gusto", "pronunciation": "موچُ گُستُ", "meaning": "یعنی: خوشحال شدم 🤝", "tip": "نکته: <b>CH</b> مثل «چ» فارسیه — mucho = موچُ<br>Igualmente = ایگوالمِنتِه = منم همینطور 🤝"},
    {"lesson": "درس ۱۱", "word": "uno, dos, tres", "pronunciation": "اونُ، دُس، تِرِس", "meaning": "یعنی: ۱، ۲، ۳ 🔢", "tip": "نکته: <b>U</b> مثل «اُ» کوتاه<br>uno قبل از اسم میشه un — un café = یه قهوه ☕"},
    {"lesson": "درس ۱۲", "word": "cuatro, cinco, seis", "pronunciation": "کواترُ، ثینکُ، سِئیس", "meaning": "یعنی: ۴، ۵، ۶ 🔢", "tip": "نکته: <b>C</b> قبل از i یا e در اسپانیا مثل «ث»<br>cinco = ثینکُ — نه سینکو! 😊"},
    {"lesson": "درس ۱۳", "word": "rojo, azul, verde", "pronunciation": "رُخُ، آثول، وِردِه", "meaning": "یعنی: قرمز 🔴 آبی 🔵 سبز 🟢", "tip": "نکته: <b>J</b> مثل «خ» — rojo = رُخُ<br><b>Z</b> مثل «ث» — azul = آثول<br>رنگ بعد از اسم میاد: coche rojo 🚗"},
    {"lesson": "درس ۱۴", "word": "amarillo, blanco, negro", "pronunciation": "آماریُ، بلانکُ، نِگرُ", "meaning": "یعنی: زرد 🟡 سفید ⚪ مشکی ⚫", "tip": "نکته: <b>LL</b> = «ی» — amarillo = آماریُ نه آماریلو<br>¿De qué color es? = دِه کِه کولُر اِس = چه رنگیه؟"},
    {"lesson": "درس ۱۵", "word": "lunes ... domingo", "pronunciation": "لونِس ... دومینگُ", "meaning": "یعنی: روزهای هفته 📅", "tip": "هفته از <b>lunes</b> (دوشنبه) شروع میشه نه یکشنبه!<br>Hoy es lunes = اُی اِس لونِس = امروز دوشنبه‌ست"},
    {"lesson": "درس ۱۶", "word": "enero ... diciembre", "pronunciation": "اِنِرُ ... دیثیِمبرِه", "meaning": "یعنی: ماه‌های سال 📆", "tip": "نکته: <b>C</b> قبل از e = «ث» — diciembre = دیثیِمبرِه<br>hoy = اُی | mañana = مانیانا | ayer = آیِر"},
    {"lesson": "درس ۱۷", "word": "padre, madre, hermano", "pronunciation": "پادرِه، مادرِه، اِرمانُ", "meaning": "یعنی: پدر، مادر، برادر 👨‍👩‍👦", "tip": "نکته: <b>H</b> ساکته — hermano = اِرمانُ نه هِرمانُ<br>mi = می = مال من | mi padre = پدرم 😊"},
    {"lesson": "درس ۱۸", "word": "esposo/a, novio/a", "pronunciation": "اِسپُسُ/آ، نُبیُ/آ", "meaning": "یعنی: شوهر/زن، نامزد 💑", "tip": "نکته: <b>V</b> مثل «ب» نرم — novio = نُبیُ نه نُویو<br>tío = تیُ = عمو/دایی | tía = تیا = عمه/خاله"},
    {"lesson": "درس ۱۹", "word": "alto, simpático, amable", "pronunciation": "آلتُ، سیمپاتیکُ، آمابلِه", "meaning": "یعنی: قد بلند، خوش‌برخورد، مهربان 😊", "tip": "صفت مذکر و مؤنث فرق داره!<br>él es alto (مرد) / ella es alta (زن)<br>muy = موی = خیلی 💕"},
    {"lesson": "درس ۲۰", "word": "yo, tú, él/ella", "pronunciation": "یُ، تو، اِل/اِیا", "meaning": "یعنی: من، تو، او 👤", "tip": "نکته: <b>Y</b> در yo مثل «ی» فارسیه<br>توی اسپانیایی ضمیر معمولاً <b>حذف</b> میشه!<br>فعل خودش شخص رو نشون میده 😊"},
    {"lesson": "درس ۲۱", "word": "soy, eres, es, somos", "pronunciation": "سُی، اِرِس، اِس، سُمُس", "meaning": "یعنی: منم، تویی، اوست، ماییم 🔵", "tip": "فعل <b>ser</b> = بودن برای ویژگی <b>ثابت</b><br>Soy iraní = ایرانیم (همیشه)<br>Eres muy simpático = خیلی خوش‌برخوردی 😊"},
    {"lesson": "درس ۲۲", "word": "estoy, estás, está", "pronunciation": "اِستُی، اِستاس، اِستا", "meaning": "یعنی: هستم، هستی، هست 🟡", "tip": "فعل <b>estar</b> = بودن برای حالت <b>موقت</b><br>ser = ثابت: Soy iraní<br>estar = موقت: Estoy cansado = خسته‌ام"},
    {"lesson": "درس ۲۳", "word": "tengo, tienes, tiene", "pronunciation": "تِنگُ، تیِنِس، تیِنِه", "meaning": "یعنی: دارم، داری، داره 🤲", "tip": "فعل <b>tener</b> = داشتن<br>Tengo hambre = تِنگُ آمبرِه = گرسنمه<br>¿Tienes coche? = ماشین داری؟ 🚗"},
    {"lesson": "درس ۲۴", "word": "salón, cocina, baño", "pronunciation": "سالُن، کوثینا، بانیُ", "meaning": "یعنی: پذیرایی، آشپزخانه، حمام 🏠", "tip": "نکته: <b>Ñ</b> = «نی» — baño = بانیُ نه بانو<br><b>C</b> قبل از i = «ث» — cocina = کوثینا<br>¿Dónde está el baño? = دستشویی کجاست؟ 😅"},
    {"lesson": "درس ۲۵", "word": "mesa, cama, sofá, nevera", "pronunciation": "مِسا، کاما، سُفا، نِبِرا", "meaning": "یعنی: میز، تخت، مبل، یخچال 🪑", "tip": "نکته: <b>V</b> = «ب» نرم — nevera = نِبِرا نه نِوِرا<br>hay = آی = هست/وجود داره<br>Hay una mesa = یه میز هست 😊"},
    {"lesson": "درس ۲۶", "word": "en, sobre, debajo de", "pronunciation": "اِن، سُبرِه، دِباخُ دِه", "meaning": "یعنی: توی، روی، زیر 📍", "tip": "نکته: <b>J</b> = «خ» — debajo = دِباخُ<br>al lado de = کنار | delante de = جلوی<br>detrás de = پشت"},
    {"lesson": "درس ۲۷", "word": "grande, pequeño, bonito", "pronunciation": "گراندِه، پِکِنیُ، بُنیتُ", "meaning": "یعنی: بزرگ، کوچیک، قشنگ 🏠", "tip": "نکته: <b>Ñ</b> = «نی» — pequeño = پِکِنیُ<br>alquiler = آلکیلِر = اجاره<br>fianza = فیانثا = ودیعه"},
    {"lesson": "درس ۲۸", "word": "calle, plaza, barrio", "pronunciation": "کایِه، پلاثا، باریُ", "meaning": "یعنی: خیابان، میدان، محله 🏙️", "tip": "نکته: <b>LL</b> = «ی» — calle = کایِه نه کالِه<br><b>Z</b> = «ث» — plaza = پلاثا<br>cerca = ثِرکا = نزدیک | lejos = لِخُس = دور"},
    {"lesson": "درس ۲۹ — مرور ماه اول 🎉", "word": "¡Un mes!", "pronunciation": "اون مِس", "meaning": "یعنی: یه ماه! 🏆", "tip": "✅ احوال‌پرسی ✅ اعداد و رنگ‌ها<br>✅ خانواده ✅ فعل‌های اصلی<br>✅ خانه ✅ محله | ماه دوم: زندگی روزمره! 🌟"},
    {"lesson": "درس ۳۰", "word": "desayuno, almuerzo, cena", "pronunciation": "دِسایونُ، آلموئِرثُ، ثِنا", "meaning": "یعنی: صبحانه، ناهار، شام 🍽️", "tip": "نکته: <b>Z</b> = «ث» — almuerzo = آلموئِرثُ<br><b>C</b> قبل از e = «ث» — cena = ثِنا<br>اسپانیایی‌ها شام رو ساعت ۹-۱۰ شب می‌خورن! 🌙"},
    {"lesson": "درس ۳۱", "word": "pan, leche, huevo", "pronunciation": "پان، لِچِه، وئِبُ", "meaning": "یعنی: نان، شیر، تخم‌مرغ 🥚", "tip": "نکته: <b>H</b> ساکته — huevo = وئِبُ نه هوئِبو<br><b>V</b> = «ب» نرم — huevo = وئِبُ<br><b>CH</b> = «چ» — leche = لِچِه"},
    {"lesson": "درس ۳۲", "word": "agua, café, té, zumo", "pronunciation": "آگوا، کافِه، تِه، ثومُ", "meaning": "یعنی: آب، قهوه، چای، آب‌میوه ☕", "tip": "نکته: <b>Z</b> = «ث» — zumo = ثومُ<br>Un café con leche, por favor ☕<br>café solo = کافِه سُلُ = اسپرسو"},
    {"lesson": "درس ۳۳", "word": "Una mesa para dos", "pronunciation": "اونا مِسا پارا دُس", "meaning": "یعنی: میز برای دو نفر 🍽️", "tip": "La carta, por favor = لا کارتا، پُر فابُر = منو لطفاً<br>نکته: <b>V</b> = «ب» — favor = فابُر<br>¿Qué recomienda? = کِه رِکُمیِندا = چی پیشنهاد میدی؟"},
    {"lesson": "درس ۳۴", "word": "Para mí la paella", "pronunciation": "پارا می لا پاِیا", "meaning": "یعنی: برای من پائلا 🥘", "tip": "نکته: <b>LL</b> = «ی» — paella = پاِیا نه پائِلا<br>¡Está delicioso! = اِستا دِلیثیُسُ = خیلی خوشمزه‌ست!<br>La cuenta = لا کوئِنتا = صورتحساب"},
    {"lesson": "درس ۳۵", "word": "farmacia, supermercado", "pronunciation": "فارماثیا، سوپِرمِرکادُ", "meaning": "یعنی: داروخانه، سوپرمارکت 🏪", "tip": "نکته: <b>C</b> قبل از i = «ث» — farmacia = فارماثیا<br>farmacia با صلیب سبز مشخصه ✚<br>panadería = پاناداِریا = نانوایی"},
    {"lesson": "درس ۳۶", "word": "¿Cuánto cuesta?", "pronunciation": "کوانتُ کوئِستا", "meaning": "یعنی: چقدر میشه؟ 💰", "tip": "نکته: <b>QU</b> = «ک» — U خونده نمیشه<br>caro = کارُ = گرونه | barato = باراتُ = ارزونه<br>rebaja = رِباخا = تخفیف"},
    {"lesson": "درس ۳۷", "word": "talla, mediano, grande", "pronunciation": "تایا، مِدیانُ، گراندِه", "meaning": "یعنی: سایز، متوسط، بزرگ 👗", "tip": "نکته: <b>LL</b> = «ی» — talla = تایا نه تالا<br>¿Puedo probármelo? = میتونم امتحان کنم؟<br>Me queda bien = مِه کِدا بیِن = خوب بهم میاد"},
    {"lesson": "درس ۳۸", "word": "metro, autobús, tren", "pronunciation": "مِترُ، آوتُبوس، تِرِن", "meaning": "یعنی: مترو، اتوبوس، قطار 🚇", "tip": "نکته: <b>AU</b> = «آو» — autobús = آوتُبوس<br>abono mensual = آبُنُ مِنسوال = کارت ماهانه 💳"},
    {"lesson": "درس ۳۹", "word": "¿Dónde está...?", "pronunciation": "دُندِه اِستا", "meaning": "یعنی: ... کجاست؟ 📍", "tip": "نکته: <b>D</b> بین دو vowel نرم — dónde = دُندِه<br>todo recto = تُدُ رِکتُ = مستقیم ➡️<br>a la derecha = راست | a la izquierda = چپ"},
    {"lesson": "درس ۴۰", "word": "billete, abono", "pronunciation": "بیئِتِه، آبُنُ", "meaning": "یعنی: بلیت، کارت ماهانه 🎫", "tip": "نکته: <b>LL</b> = «ی» — billete = بیئِتِه نه بیلِتِه<br>ayuntamiento = آیونتامیِنتُ = شهرداری<br>embajada = اِمباخادا = سفارت"},
    {"lesson": "درس ۴۱", "word": "¿Qué hora es?", "pronunciation": "کِه اُرا اِس", "meaning": "یعنی: ساعت چنده؟ ⏰", "tip": "نکته: <b>H</b> ساکته — hora = اُرا نه هُرا<br>Son las tres = ساعت ۳ | Es la una = ساعت ۱<br>y media = ای مِدیا = و نیم"},
    {"lesson": "درس ۴۲", "word": "levantarse, ducharse", "pronunciation": "لِبانتارسِه، دوچارسِه", "meaning": "یعنی: بیدار شدن، دوش گرفتن 🚿", "tip": "نکته: <b>V</b> = «ب» — levantarse = لِبانتارسِه<br><b>CH</b> = «چ» — ducharse = دوچارسِه<br>فعل‌های se = کار روی خودت 😊"},
    {"lesson": "درس ۴۳", "word": "médico, abogado, ingeniero", "pronunciation": "مِدیکُ، آبُگادُ، اینخِنیِرُ", "meaning": "یعنی: دکتر، وکیل، مهندس 👷", "tip": "نکته: <b>G</b> قبل از e یا i = «خ» — ingeniero = اینخِنیِرُ<br>¿A qué te dedicas? = چیکاره‌ای؟<br>Soy ingeniero = مهندسم 💼"},
    {"lesson": "درس ۴۴", "word": "sueldo, contrato, vacaciones", "pronunciation": "سوئِلدُ، کُنتراتُ، باکاثیُنِس", "meaning": "یعنی: حقوق، قرارداد، تعطیلات 💼", "tip": "نکته: <b>V</b> = «ب» — vacaciones = باکاثیُنِس<br><b>C</b> قبل از i = «ث» — vacaciones = باکاثیُنِس<br>۲۲ روز مرخصی سالانه حق توست! 🏖️"},
    {"lesson": "درس ۴۵ — نصف راه! 🏆", "word": "¡A mitad!", "pronunciation": "آ میتاد", "meaning": "یعنی: نصف راه! 🏆", "tip": "✅ وعده‌های غذایی ✅ خرید<br>✅ حمل‌ونقل ✅ مشاغل<br>✅ ساعت ✅ روتین روزانه<br>💪 ادامه بده!"},
    {"lesson": "درس ۴۶", "word": "NIE", "pronunciation": "اِن-ای-اِه", "meaning": "یعنی: شماره شناسایی خارجی 🪪", "tip": "Número de Identificación de Extranjero<br>مهم‌ترین مدرک برای زندگی در اسپانیا!<br>بدون NIE هیچ کاری نمیشه کرد 🔑"},
    {"lesson": "درس ۴۷", "word": "cuenta bancaria, IBAN", "pronunciation": "کوئِنتا بانکاریا، ایبان", "meaning": "یعنی: حساب بانکی، شماره بین‌المللی 🏦", "tip": "نکته: <b>QU</b> = «ک» — cuenta = کوئِنتا<br>Quiero abrir una cuenta = می‌خوام حساب باز کنم<br>cajero automático = کاخِرُ = خودپرداز 🏧"},
    {"lesson": "درس ۴۸", "word": "cita previa", "pronunciation": "ثیتا پرِبیا", "meaning": "یعنی: وقت قبلی 📋", "tip": "نکته: <b>C</b> قبل از i = «ث» — cita = ثیتا<br><b>V</b> = «ب» — previa = پرِبیا<br>برای هر کار اداری باید cita previa بگیری 💻"},
    {"lesson": "درس ۴۹", "word": "Me duele la garganta", "pronunciation": "مِه دوئِلِه لا گارگانتا", "meaning": "یعنی: گلوم درد میکنه 🤒", "tip": "la cabeza = کابِثا = سر<br>el estómago = اِستُماگُ = معده<br>Tengo fiebre = فیِبرِه = تب دارم"},
    {"lesson": "درس ۵۰", "word": "receta, pastilla, jarabe", "pronunciation": "رِثِتا، پاستیا، خاراβِه", "meaning": "یعنی: نسخه، قرص، شربت 💊", "tip": "نکته: <b>C</b> قبل از e = «ث» — receta = رِثِتا<br><b>LL</b> = «ی» — pastilla = پاستیا<br><b>J</b> = «خ» — jarabe = خاراβِه"},
    {"lesson": "درس ۵۱", "word": "¡Ayuda! ¡Llame al 112!", "pronunciation": "آیودا! یامِه آل ثیِنتُدُس", "meaning": "یعنی: کمک! با ۱۱۲ تماس بگیرید! 🚨", "tip": "نکته: <b>LL</b> = «ی» — llame = یامِه<br><b>112</b> = شماره اورژانس اسپانیا 🚨<br>Me han robado = مِه آن رُبادُ = دزدیده شدم"},
    {"lesson": "درس ۵۲", "word": "seguro médico", "pronunciation": "سِگورُ مِدیکُ", "meaning": "یعنی: بیمه درمانی 🏥", "tip": "tarjeta sanitaria = تارخِتا سانیتاریا = کارت بیمه<br>نکته: <b>J</b> = «خ» — tarjeta = تارخِتا<br>بعد از NIE باید بیمه بگیری! 🏥"},
    {"lesson": "درس ۵۳", "word": "vuelo, equipaje, aduana", "pronunciation": "بوئِلُ، اِکیپاخِه، آدوانا", "meaning": "یعنی: پرواز، چمدان، گمرک ✈️", "tip": "نکته: <b>V</b> = «ب» نرم — vuelo = بوئِلُ نه وُئِلُ<br><b>J</b> = «خ» — equipaje = اِکیپاخِه<br>retraso = رِتراسُ = تأخیر"},
    {"lesson": "درس ۵۴", "word": "reserva, habitación", "pronunciation": "رِسِربا، آبیتاثیُن", "meaning": "یعنی: رزرو، اتاق 🏨", "tip": "نکته: <b>V</b> = «ب» — reserva = رِسِربا<br><b>H</b> ساکته + <b>C</b> = «ث» — habitación = آبیتاثیُن<br>¿Hay wifi? = آی وی‌فی = وای‌فای دارید؟"},
    {"lesson": "درس ۵۵", "word": "museo, playa, castillo", "pronunciation": "موسِئُ، پلایا، کاستیُ", "meaning": "یعنی: موزه، ساحل، قلعه 🏰", "tip": "نکته: <b>LL</b> = «ی» — castillo = کاستیُ نه کاستیلو<br>¿Está abierto? = آبیِرتُ = بازه؟<br>entrada = اِنترادا = بلیت ورودی"},
    {"lesson": "درس ۵۶", "word": "hace calor, hace frío", "pronunciation": "آثِه کالُر، آثِه فریُ", "meaning": "یعنی: گرمه، سرده ☀️❄️", "tip": "نکته: <b>H</b> ساکته + <b>C</b> = «ث» — hace = آثِه<br>llueve = یوئِبِه = باران میاد 🌧️<br>Madrid = خشک ☀️ | Barcelona = مدیترانه‌ای 🌊"},
    {"lesson": "درس ۵۷", "word": "estoy feliz, triste", "pronunciation": "اِستُی فِلیث، تریستِه", "meaning": "یعنی: خوشحالم، ناراحتم 😊😢", "tip": "نکته: <b>Z</b> = «ث» — feliz = فِلیث<br>tengo hambre = تِنگُ آمبرِه = گرسنمه<br>tengo sueño = تِنگُ سوئِنیُ = خوابم میاد"},
    {"lesson": "درس ۵۸", "word": "me encanta, me gusta", "pronunciation": "مِه اِنکانتا، مِه گوستا", "meaning": "یعنی: عاشقشم، دوستش دارم ❤️", "tip": "نکته: <b>G</b> قبل از u = «گ» — gusta = گوستا<br>Me encanta España = عاشق اسپانیام ❤️<br>No me gusta nada = اصلاً دوستش ندارم"},
    {"lesson": "درس ۵۹", "word": "De acuerdo, Quizás", "pronunciation": "دِه آکوئِردُ، کیثاس", "meaning": "یعنی: موافقم، شاید 👍", "tip": "نکته: <b>Z</b> = «ث» — quizás = کیثاس<br>Tienes razón = تیِنِس راثُن = حق داری<br>Exactamente = اِکساکتامِنتِه = دقیقاً"},
    {"lesson": "درس ۶۰", "word": "Creo que... / Me parece bien", "pronunciation": "کرِئُ کِه / مِه پارِثِه بیِن", "meaning": "یعنی: فکر می‌کنم / به نظرم خوبه 💭", "tip": "نکته: <b>C</b> قبل از e = «ث» — parece = پارِثِه<br>Muchas gracias = موچاس گِراثیاس = خیلی ممنون<br>Lo siento = لُ سیِنتُ = متأسفم"},
    {"lesson": "درس ۶۱ — مکالمه: معرفی", "word": "¡Hola! Me llamo Dara.", "pronunciation": "اُلا! مِه یامُ دارا", "meaning": "یعنی: سلام! اسمم داراست 👤", "tip": "Soy de Irán. Tengo 32 años.<br>Soy ingeniero. Vivo en Madrid.<br>Estoy aprendiendo español! 😄"},
    {"lesson": "درس ۶۲ — مکالمه: رستوران", "word": "Una mesa para dos", "pronunciation": "اونا مِسا پارا دُس", "meaning": "یعنی: میز برای دو نفر 🍽️", "tip": "Para mí, la paella. De beber, agua.<br>¡Está delicioso! La cuenta, por favor.<br>= برای من پائلا. خوشمزه! صورتحساب."},
    {"lesson": "درس ۶۳ — مکالمه: خرید", "word": "¿Tiene esta camiseta en azul?", "pronunciation": "تیِنِه اِستا کامیسِتا اِن آثول", "meaning": "یعنی: این تیشرت رنگ آبی دارید؟ 👕", "tip": "نکته: <b>Z</b> = «ث» — azul = آثول<br>La mediana, por favor. Veinte euros.<br>¿Acepta tarjeta? = آثِپتا = کارت قبول می‌کنید؟"},
    {"lesson": "درس ۶۴ — مکالمه: مسیر", "word": "¿Dónde está el metro?", "pronunciation": "دُندِه اِستا اِل مِترُ", "meaning": "یعنی: مترو کجاست؟ 🚇", "tip": "Todo recto y luego a la derecha.<br>A cinco minutos a pie.<br>= مستقیم، بعد راست. پنج دقیقه پیاده."},
    {"lesson": "درس ۶۵ — مکالمه: دکتر", "word": "Me duele la garganta", "pronunciation": "مِه دوئِلِه لا گارگانتا", "meaning": "یعنی: گلوم درد میکنه 🤒", "tip": "Tengo cita con el médico.<br>¿Desde cuándo? = دِسدِه کواندُ = از کِی؟<br>¿Tiene alergia? = آلِرخیا = حساسیت داری؟"},
    {"lesson": "درس ۶۶ — گرامر: فعل‌های ar", "word": "hablar = حرف زدن", "pronunciation": "آبلار", "meaning": "یعنی: حرف زدن 🗣️", "tip": "نکته: <b>H</b> ساکته — hablar = آبلار نه هابلار<br>hablo / hablas / habla / hablamos<br>trabajar, comprar, escuchar هم اینطوری! 😊"},
    {"lesson": "درس ۶۷ — گرامر: فعل‌های er/ir", "word": "comer, vivir", "pronunciation": "کُمِر، بیبیر", "meaning": "یعنی: خوردن، زندگی کردن 📝", "tip": "نکته: <b>V</b> = «ب» — vivir = بیبیر نه ویویر<br>como / comes / come / comemos<br>سه دسته فعل: ar، er، ir 💡"},
    {"lesson": "درس ۶۸", "word": "¿Puede repetir?", "pronunciation": "پوئِدِه رِپِتیر", "meaning": "یعنی: میتونید تکرار کنید؟ 🔄", "tip": "No entiendo = نُ اِنتیِندُ = نمی‌فهمم<br>Habla más despacio = آبلا ماس دِسپاثیُ = آروم‌تر حرف بزنید<br>نکته: <b>H</b> ساکته — habla = آبلا"},
    {"lesson": "درس ۶۹ — ۲۰ کلمه طلایی ✨", "word": "por favor, gracias, perdón", "pronunciation": "پُر فابُر، گِراثیاس، پِردُن", "meaning": "یعنی: لطفاً، ممنون، ببخشید ✨", "tip": "نکته: <b>V</b> = «ب» — favor = فابُر<br><b>Z/C</b> = «ث» — gracias = گِراثیاس<br>De nada = دِه نادا = خواهش می‌کنم"},
    {"lesson": "درس ۷۰ — فرهنگ اسپانیایی", "word": "Siesta, Flamenco, Fútbol", "pronunciation": "سیِستا، فلامِنکُ، فوتبُل", "meaning": "یعنی: چرت نیمروز، فلامنکو، فوتبال 💃⚽", "tip": "🕐 Siesta هنوز مرسومه!<br>🍅 La Tomatina = جشن پرتاب گوجه<br>🎉 Las Fallas = جشن آتش در والنسیا"},
    {"lesson": "درس ۷۱ — شهرهای اسپانیا", "word": "Madrid, Barcelona, Valencia", "pronunciation": "مادِرید، بارثِلُنا، بالِنثیا", "meaning": "یعنی: مادرید، بارسلونا، والنسیا 🏙️", "tip": "نکته: <b>C</b> قبل از e = «ث» — Barcelona = بارثِلُنا<br><b>V</b> = «ب» — Valencia = بالِنثیا<br>Sevilla = سِبیا | Granada = گِرانادا"},
    {"lesson": "درس ۷۲ — ¡Sí se puede!", "word": "¡Sí se puede!", "pronunciation": "سی سِه پوئِدِه", "meaning": "یعنی: میشه! 💪", "tip": "Poco a poco = پُکُ آ پُکُ = قدم به قدم<br>¡Ánimo! = آنیمُ = روحیه داشته باش!<br>¡Tú puedes! = تو پوئِدِس = تو می‌تونی! 🌟"},
    {"lesson": "درس ۷۳ — تست نهایی ✅", "word": "¡A examinarse!", "pronunciation": "آ اِکسامینارسِه", "meaning": "یعنی: وقت تست! 📝", "tip": "✅ ¡Hola! (اُلا) ¿Cómo estás? (کُمُ اِستاس)<br>✅ Me llamo... (مِه یامُ) Soy de Irán.<br>✅ Una mesa para dos, por favor."},
    {"lesson": "درس ۷۴ — قدم بعدی", "word": "Nivel A2", "pronunciation": "نیبِل آ دُس", "meaning": "یعنی: سطح A2 📚", "tip": "نکته: <b>V</b> = «ب» — nivel = نیبِل<br>📚 pretérito = گذشته | futuro = آینده<br>📱 Duolingo | 📺 Dreaming Spanish"},
    {"lesson": "درس ۷۵ — جمع‌بندی 🏆", "word": "Lo que aprendiste", "pronunciation": "لُ کِه آپِرِندیستِه", "meaning": "یعنی: چیزی که یاد گرفتی 🏆", "tip": "✅ معرفی ✅ اعداد و رنگ‌ها<br>✅ خانواده ✅ فعل‌های اصلی<br>✅ خانه ✅ غذا ✅ خرید<br>✅ حمل‌ونقل ✅ دکتر ✅ احساسات"},
    {"lesson": "درس ۷۶ — روز آخر 🎉", "word": "¡Felicidades!", "pronunciation": "فِلیثیداداس", "meaning": "یعنی: تبریک! 🎉", "tip": "نکته: <b>C</b> قبل از i = «ث» — felicidades = فِلیثیداداس<br>۷۶ درس پیش با ¡Hola! (اُلا) شروع کردی!<br>¡Hasta pronto! = آستا پرُنتُ = تا زود! 🇪🇸"},
]


def generate_card_html(lesson):
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Vazirmatn:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ width: 840px; height: 1080px; background: transparent; font-family: Vazirmatn, DejaVu Sans, sans-serif; }}
  .card {{ width: 840px; height: 1080px; border-radius: 56px; position: relative; overflow: hidden; }}
  .card::before {{ content: ""; position: absolute; inset: 0; background: linear-gradient(145deg, #c0392b 0%, #922b21 40%, #1a1a2e 100%); z-index: 0; }}
  .card::after {{ content: ""; position: absolute; width: 640px; height: 640px; border-radius: 50%; border: 3px solid rgba(255,255,255,0.08); top: -160px; left: -120px; z-index: 1; }}
  .dots {{ position: absolute; bottom: 160px; right: 48px; display: grid; grid-template-columns: repeat(4, 12px); gap: 10px; z-index: 1; opacity: 0.2; }}
  .dots span {{ width: 12px; height: 12px; border-radius: 50%; background: #fff; display: block; }}
  .card-inner {{ position: relative; z-index: 2; height: 100%; display: flex; flex-direction: column; padding: 56px; }}
  .top-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; }}
  .day-badge {{ background: rgba(255,255,255,0.15); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); color: #fff; font-size: 24px; font-weight: 600; padding: 12px 28px; border-radius: 40px; }}
  .flag {{ font-size: 56px; filter: drop-shadow(0 2px 8px rgba(0,0,0,0.3)); }}
  .main-word {{ font-family: Playfair Display, serif; font-size: 110px; font-weight: 900; color: #fff; line-height: 1; margin-bottom: 12px; text-shadow: 0 4px 20px rgba(0,0,0,0.3); letter-spacing: -2px; direction: ltr; text-align: right; }}
  .pronunciation {{ color: rgba(255,220,100,0.9); font-size: 34px; font-weight: 600; margin-bottom: 8px; direction: rtl; }}
  .meaning {{ color: rgba(255,255,255,0.85); font-size: 42px; font-weight: 700; margin-bottom: 40px; }}
  .divider {{ width: 96px; height: 6px; background: rgba(255,220,100,0.7); border-radius: 3px; margin-bottom: 32px; }}
  .tip-box {{ background: rgba(0,0,0,0.25); backdrop-filter: blur(8px); border: 1px solid rgba(255,255,255,0.1); border-radius: 32px; padding: 32px 36px; flex: 1; display: flex; align-items: flex-start; gap: 24px; }}
  .tip-icon {{ font-size: 44px; flex-shrink: 0; margin-top: 4px; }}
  .tip-text {{ color: rgba(255,255,255,0.88); font-size: 30px; line-height: 1.8; }}
  .tip-text b {{ color: rgba(255,220,100,0.95); font-weight: 700; }}
  .bottom-bar {{ display: flex; justify-content: space-between; align-items: flex-end; margin-top: 36px; }}
  .links {{ display: flex; flex-direction: column; gap: 6px; }}
  .link-item {{ color: rgba(255,220,100,0.8); font-size: 22px; font-weight: 600; direction: ltr; }}
  .right-col {{ display: flex; flex-direction: column; align-items: flex-end; gap: 12px; }}
  .audio-btn {{ width: 80px; height: 80px; border-radius: 50%; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); display: flex; align-items: center; justify-content: center; font-size: 36px; }}
  .designer {{ color: rgba(255,255,255,0.3); font-size: 18px; direction: ltr; text-align: right; line-height: 1.6; }}
</style>
</head>
<body>
<div class="card">
  <div class="dots"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
  <div class="card-inner">
    <div class="top-bar">
      <div class="day-badge">📍 {lesson['lesson']}</div>
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
      <div class="links">
        <div class="link-item">📲 t.me/vitrinspain</div>
        <div class="link-item">🌿 t.me/hayatkhalvatspain</div>
        <div class="link-item">🤖 @VitrinSpainBot</div>
      </div>
      <div class="right-col">
        <div class="audio-btn">🔊</div>
        <div class="designer">Design by: Tamin .M<br>@taminmashoori</div>
      </div>
    </div>
  </div>
</div>
</body>
</html>"""


def create_card_image(lesson, output_path):
    html_content = generate_card_html(lesson)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 840, "height": 1080})
        page.set_content(html_content)
        page.wait_for_timeout(2500)
        page.screenshot(path=output_path, clip={"x": 0, "y": 0, "width": 840, "height": 1080})
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
        print(f"🎨 در حال ساخت تصویر: {lesson['lesson']}")
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
    print(f"📅 آپدیت شد: {current_day + 2} از {len(LESSONS)}")


if __name__ == "__main__":
    asyncio.run(send_lessons())
