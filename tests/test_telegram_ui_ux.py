import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TelegramUIUXTests(unittest.TestCase):
    def test_main_menu_uses_persistent_reply_keyboard_navigation(self):
        start_text = (ROOT / "handlers" / "start.py").read_text(encoding="utf-8")
        config_text = (ROOT / "config_v2.py").read_text(encoding="utf-8")
        for constant, label in (
            ("HOME_BUTTON", "🏠 صفحه اصلی"),
            ("MENU_RADAR", "📡 رادار"),
            ("MENU_CREATE_VITRIN", "➕ ثبت آگهی"),
            ("MENU_CREATE_HAYAT", "💬 پیام ناشناس"),
            ("MENU_PROFILE", "👤 پروفایل"),
            ("MENU_VIP", "⭐ اشتراک VIP"),
            ("MENU_SETTINGS", "⚙️ تنظیمات"),
            ("MENU_HELP", "ℹ️ راهنما"),
        ):
            self.assertIn(f'{constant} = "{label}"', config_text)
            self.assertIn(f"KeyboardButton({constant})", start_text)
        self.assertIn("MAIN_MENU = ReplyKeyboardMarkup(", start_text)
        self.assertIn("is_persistent=True", start_text)

    def test_radar_categories_use_registered_radar_callbacks(self):
        text = (ROOT / "handlers" / "radar.py").read_text(encoding="utf-8")
        for callback in ("job", "discount", "event", "all", "alert"):
            self.assertIn(f'callback_data="radar:type:{callback}"', text)
        self.assertIn('callback_data="radar:home"', text)
        self.assertIn("در حال حاضر محتوایی در این بخش موجود نیست.", text)

    def test_admin_panel_uses_inline_callbacks_and_keeps_auth_check(self):
        text = (ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        for callback in ("radar", "vitrin", "hayat", "users", "comments", "reports", "home"):
            self.assertIn(f'callback_data="admin:panel:{callback}"', text)
        self.assertIn("if not is_admin(update.effective_user.id):", text)
        self.assertIn("ReplyKeyboardRemove()", text)

    def test_dashboard_has_dates_times_currency_fallback_and_no_demo_counts(self):
        text = (ROOT / "handlers" / "start.py").read_text(encoding="utf-8")
        for expected in (
            "📅 تاریخ میلادی:", "🗓 تاریخ شمسی:", "🇪🇸 ساعت اسپانیا:",
            "🇮🇷 ساعت ایران:", 'euro_text = "موقتاً در دسترس نیست"',
            'dollar_text = "موقتاً در دسترس نیست"', 'ZoneInfo("Asia/Tehran")',
        ):
            self.assertIn(expected, text)
        self.assertNotIn("DEMO_DASHBOARD_COUNTS", text)

    def test_lightweight_jalali_conversion_matches_nowruz(self):
        source = (ROOT / "handlers" / "start.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "gregorian_to_jalali")
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "start.py", "exec"), namespace)
        self.assertEqual(namespace["gregorian_to_jalali"](2024, 3, 20), (1403, 1, 1))

    def test_bot_registers_every_callback_prefix_used_by_new_ui(self):
        text = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn('pattern=r"^home:"', text)
        self.assertIn('pattern=r"^radar:"', text)
        self.assertIn('pattern=r"^admin:"', text)


if __name__ == "__main__":
    unittest.main()
