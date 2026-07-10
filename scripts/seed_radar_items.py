from datetime import datetime, time, timedelta
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.db import db_cursor, init_db  # noqa: E402
from psycopg2.extras import Json  # noqa: E402


SPAIN_TZ = "Europe/Madrid"


def local_datetimes():
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(SPAIN_TZ)).replace(tzinfo=None)
    except Exception:
        now = datetime.now()

    start_date = datetime.combine(now.date(), time.min)
    end_date = start_date + timedelta(days=7)
    return now, start_date, end_date


def sample_items():
    now, start_date, end_date = local_datetimes()
    shared = {
        "country": "Spain",
        "start_date": start_date,
        "end_date": end_date,
        "is_verified": True,
        "is_published": True,
        "published_at": now,
        "expires_at": end_date,
        "content_status": "ready",
        "channel_status": "not_sent",
        "created_at": now,
        "updated_at": now,
    }

    return [
        {
            **shared,
            "title": "هشدار موج گرما در اسپانیا",
            "summary": "در چند استان اسپانیا دمای هوا بالاتر از حد معمول پیش‌بینی شده و بهتر است برنامه‌های بیرونی با احتیاط انجام شود.",
            "body": "اگر در ساعات میانی روز بیرون می‌روید آب کافی همراه داشته باشید، از قرار گرفتن طولانی در آفتاب خودداری کنید و وضعیت سالمندان، کودکان و افراد حساس را بررسی کنید.",
            "type": "alert",
            "category": "فوری",
            "city": "کل اسپانیا",
            "province": "کل اسپانیا",
            "source_url": "https://www.aemet.es/es/eltiempo/prediccion/avisos",
            "source_name": "AEMET",
            "urgency": "urgent",
            "priority_score": 95,
            "audience_tags": ["همه کاربران", "خانواده‌ها", "سالمندان"],
        },
        {
            **shared,
            "title": "تخفیف محصولات تابستانی در Carrefour",
            "summary": "چند گروه از محصولات تابستانی و سوپرمارکتی در فروشگاه‌های Carrefour با تخفیف دوره‌ای عرضه می‌شوند.",
            "body": "برای خریدهای روزمره، قبل از مراجعه حضوری یا سفارش آنلاین، قیمت و موجودی شعبه نزدیک خود را بررسی کنید.",
            "type": "discount",
            "category": "تخفیف‌ها",
            "city": "کل اسپانیا",
            "province": "کل اسپانیا",
            "source_url": "https://www.carrefour.es/ofertas",
            "source_name": "Carrefour España",
            "urgency": "medium",
            "priority_score": 70,
            "audience_tags": ["خانواده‌ها", "دانشجوها", "خرید روزانه"],
        },
        {
            **shared,
            "title": "آفر لوازم آرایشی و بهداشتی در Primor",
            "summary": "Primor برای برخی برندهای آرایشی، بهداشتی و مراقبت پوست آفرهای محدود دوره‌ای دارد.",
            "body": "اگر قصد خرید محصولات مراقبت پوست یا بهداشت شخصی دارید، صفحه پیشنهادهای Primor را قبل از خرید بررسی کنید.",
            "type": "discount",
            "category": "تخفیف‌ها",
            "city": "کل اسپانیا",
            "province": "کل اسپانیا",
            "source_url": "https://www.primor.eu/es_es/ofertas",
            "source_name": "Primor",
            "urgency": "medium",
            "priority_score": 68,
            "audience_tags": ["خرید شخصی", "دانشجوها", "خانواده‌ها"],
        },
        {
            **shared,
            "title": "فستیوال تابستانی آخر هفته",
            "summary": "یک برنامه تابستانی آخر هفته در مادرید می‌تواند گزینه‌ای مناسب برای تفریح و دورهمی باشد.",
            "body": "پیش از حرکت، ساعت دقیق برنامه، ظرفیت، مسیر دسترسی و نیاز به رزرو را از منبع رسمی رویداد بررسی کنید.",
            "type": "event",
            "category": "ایونت‌ها",
            "city": "Madrid",
            "province": "Madrid",
            "source_url": "https://www.esmadrid.com/agenda",
            "source_name": "Madrid Destino",
            "urgency": "low",
            "priority_score": 52,
            "audience_tags": ["مادرید", "آخر هفته", "تفریح"],
        },
        {
            **shared,
            "title": "فرصت کاری برای فارسی‌زبان‌ها در خدمات مشتریان",
            "summary": "یک فرصت نمونه برای فارسی‌زبان‌ها در حوزه پشتیبانی و خدمات مشتریان در مادرید مناسب جویندگان کار است.",
            "body": "برای این نوع فرصت‌ها داشتن زبان فارسی، اسپانیایی یا انگلیسی و تجربه ارتباط با مشتری می‌تواند امتیاز مهمی باشد.",
            "type": "job",
            "category": "کار",
            "city": "Madrid",
            "province": "Madrid",
            "source_url": "https://www.infojobs.net/ofertas-trabajo/atencion-a-cliente/madrid",
            "source_name": "InfoJobs",
            "urgency": "high",
            "priority_score": 86,
            "audience_tags": ["جویندگان کار", "فارسی‌زبان‌ها", "مادرید"],
        },
        {
            **shared,
            "title": "یادآوری مهلت انجام کارهای اداری اقامت",
            "summary": "برای امور اقامت و اداری، بررسی تاریخ نوبت، مدارک و مهلت‌ها می‌تواند از تأخیر یا جریمه جلوگیری کند.",
            "body": "اگر پرونده اقامتی، تمدید مدارک یا نوبت اداری دارید، وضعیت پرونده و مدارک لازم را از سامانه رسمی بررسی کنید.",
            "type": "legal",
            "category": "قوانین",
            "city": "کل اسپانیا",
            "province": "کل اسپانیا",
            "source_url": "https://sede.administracionespublicas.gob.es/",
            "source_name": "Administraciones Públicas",
            "urgency": "high",
            "priority_score": 88,
            "audience_tags": ["اقامت", "اداری", "مهاجران"],
        },
        {
            **shared,
            "title": "آفر قطارهای داخلی اسپانیا برای آخر هفته",
            "summary": "برخی مسیرهای قطار داخلی ممکن است برای سفرهای آخر هفته قیمت‌های مناسب‌تری داشته باشند.",
            "body": "اگر قصد سفر کوتاه دارید، قیمت مسیر، ساعت حرکت و قوانین تغییر یا لغو بلیت را قبل از خرید بررسی کنید.",
            "type": "travel",
            "category": "سفر",
            "city": "کل اسپانیا",
            "province": "کل اسپانیا",
            "source_url": "https://www.renfe.com/es/es",
            "source_name": "Renfe",
            "urgency": "medium",
            "priority_score": 64,
            "audience_tags": ["سفر", "آخر هفته", "دانشجوها"],
        },
        {
            **shared,
            "title": "برنامه‌های رایگان کودک در کتابخانه‌های شهری",
            "summary": "کتابخانه‌های شهری بارسلونا برنامه‌های رایگان یا کم‌هزینه‌ای برای کودکان و خانواده‌ها برگزار می‌کنند.",
            "body": "برای شرکت در برنامه‌های کودک، سن مناسب، ظرفیت و نیاز به ثبت‌نام را از صفحه رسمی کتابخانه‌ها بررسی کنید.",
            "type": "family",
            "category": "خانواده",
            "city": "Barcelona",
            "province": "Barcelona",
            "source_url": "https://ajuntament.barcelona.cat/biblioteques/",
            "source_name": "Biblioteques de Barcelona",
            "urgency": "low",
            "priority_score": 55,
            "audience_tags": ["خانواده‌ها", "کودکان", "بارسلونا"],
        },
    ]


def insert_sample_items():
    init_db()
    inserted = 0
    skipped = 0

    with db_cursor() as (_, cur):
        for item in sample_items():
            cur.execute(
                """
                SELECT id
                FROM radar_items
                WHERE title = %s AND type = %s
                LIMIT 1
                """,
                (item["title"], item["type"]),
            )
            if cur.fetchone():
                skipped += 1
                continue

            cur.execute(
                """
                INSERT INTO radar_items (
                    title,
                    summary,
                    body,
                    type,
                    category,
                    city,
                    province,
                    country,
                    start_date,
                    end_date,
                    source_url,
                    source_name,
                    urgency,
                    priority_score,
                    audience_tags,
                    is_verified,
                    is_published,
                    published_at,
                    expires_at,
                    content_status,
                    channel_status,
                    ai_summary,
                    ai_reason,
                    ai_tags,
                    ai_priority,
                    original_text,
                    original_language,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s
                )
                """,
                (
                    item["title"],
                    item["summary"],
                    item["body"],
                    item["type"],
                    item["category"],
                    item["city"],
                    item["province"],
                    item["country"],
                    item["start_date"],
                    item["end_date"],
                    item["source_url"],
                    item["source_name"],
                    item["urgency"],
                    item["priority_score"],
                    Json(item["audience_tags"]),
                    item["is_verified"],
                    item["is_published"],
                    item["published_at"],
                    item["expires_at"],
                    item["content_status"],
                    item["channel_status"],
                    item["summary"],
                    item["summary"],
                    Json(item["audience_tags"]),
                    item["priority_score"],
                    item["body"],
                    "fa",
                    item["created_at"],
                    item["updated_at"],
                ),
            )
            inserted += 1

    return inserted, skipped


def main():
    inserted, skipped = insert_sample_items()
    print(f"Radar seed complete. inserted={inserted} skipped={skipped}")


if __name__ == "__main__":
    main()
