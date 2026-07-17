from __future__ import annotations


CATEGORY_HEADERS = {
    "job": "🟢 آگهی استخدام رایگان",
    "job_seeker": "🔵 آگهی جستجوی کار",
    "grant": "💰 فرصت دریافت کمک‌هزینه",
    "scholarship": "🎓 فرصت بورسیه",
    "rental": "🏠 آگهی اجاره مسکن",
    "property": "🏡 آگهی خرید و فروش ملک",
    "free_course": "📚 دوره آموزشی رایگان",
    "event": "🎉 رویداد",
    "notice": "⚠️ اطلاعیه مهم",
    "urgent_alert": "🚨 هشدار فوری",
    "discount": "🏷️ تخفیف ویژه",
}


def category_header(category: str | None) -> str | None:
    return CATEGORY_HEADERS.get((category or "").strip().casefold())
