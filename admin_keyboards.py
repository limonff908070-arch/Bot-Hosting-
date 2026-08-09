from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)


# ─── Admin Panel — Persistent Reply Keyboard (মোবাইলের নিচে স্থায়ী বাটন) ───

def admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Shown at the bottom of the screen whenever the admin is in the Admin Panel.
    Replaces the main user keyboard while the admin is operating admin features.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 System Stats"),   KeyboardButton(text="📢 Broadcast")],
            [KeyboardButton(text="👥 User Manager"),   KeyboardButton(text="🤖 Active Bots")],
            [KeyboardButton(text="🔄 System Restart"), KeyboardButton(text="📦 Install Package")],
            [KeyboardButton(text="🔙 Back to User Menu")],
        ],
        resize_keyboard=True,
        persistent=True,
        input_field_placeholder="Admin Panel — অপশন বেছে নাও...",
    )


# ─── User Info — Block / Unblock Toggle (Inline) ─────────────────────────────

def admin_user_info_keyboard(user_id: int, blocked: bool) -> InlineKeyboardMarkup:
    if blocked:
        toggle_text = "✅ Unblock User"
        toggle_cb   = f"admin_unblock_{user_id}"
    else:
        toggle_text = "🚫 Block User"
        toggle_cb   = f"admin_block_{user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb)],
    ])


# ─── FSM Reply Keyboards (Admin FSM state-এ থাকার সময়) ───────────────────────

def broadcast_cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Cancel Broadcast")]],
        resize_keyboard=True,
        input_field_placeholder="যে Message broadcast করতে চাও সেটা পাঠাও...",
    )


def user_lookup_cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Cancel Lookup")]],
        resize_keyboard=True,
        input_field_placeholder="User ID (সংখ্যা) লিখো...",
    )


def install_cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Cancel Install")]],
        resize_keyboard=True,
        input_field_placeholder="Package name লিখো (যেমন: requests)...",
    )
