from __future__ import annotations

import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from database.db import db_cursor


logger = logging.getLogger(__name__)
LEVEL_PATTERN = re.compile(r"^[a-z0-9_-]{1,16}$")
MAX_FEEDBACK_LENGTH = 1000


def _validate