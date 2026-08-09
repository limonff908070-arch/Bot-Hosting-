from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)


# ─── Reply Keyboards (মোবাইলের নিচে স্থায়ী বাটন) ───────────────────────────

def main_reply_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Main persistent keyboard.
    When is_admin=True an extra '🛡 Admin Panel' row is appended.
    """
    rows = [
        [
            KeyboardButton(text="➕ Upload New Bot"),
            KeyboardButton(text="🤖 My Bots"),
        ]
    ]
    if is_admin:
        rows.append([KeyboardButton(text="🛡 Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        persistent=True,
        input_field_placeholder="Menu থেকে বেছে নাও...",
    )


def upload_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Upload Done"),
                KeyboardButton(text="❌ Cancel Upload"),
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="ZIP ফাইল পাঠাও...",
    )


def replace_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Cancel Replace")]
        ],
        resize_keyboard=True,
        input_field_placeholder="নতুন file পাঠাও...",
    )


# ─── Inline Keyboards (Dynamic Content) ──────────────────────────────────────

def mybots_keyboard(bots: list) -> InlineKeyboardMarkup:
    """
    bots: list of dicts from process_manager.get_user_procs()
          Each dict has: {name, pid, folder, alive}
    """
    buttons = []
    for bot in bots:
        name  = bot["name"]
        alive = bot.get("alive", False)
        emoji = "🟢" if alive else "🔴"
        label = "Running" if alive else "Stopped"
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {name} [{label}]",
                callback_data=f"bot_info_{name}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def bot_action_keyboard(bot_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 View Logs",  callback_data=f"view_logs_{bot_name}")],
        [InlineKeyboardButton(text="📁 View Files", callback_data=f"view_files_{bot_name}")],
        [InlineKeyboardButton(text="🗑 Delete Bot", callback_data=f"stop_bot_{bot_name}")],
        [InlineKeyboardButton(text="⬅️ Back to List", callback_data="back_bots")],
    ])


def files_keyboard(bot_name: str, filenames: list) -> InlineKeyboardMarkup:
    buttons = []
    for fname in filenames:
        cb = f"fi_{bot_name}|{fname}"
        if len(cb.encode()) <= 64:
            buttons.append([
                InlineKeyboardButton(text=f"📄 {fname}", callback_data=cb)
            ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data=f"bot_info_{bot_name}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def file_action_keyboard(bot_name: str, filename: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Download",           callback_data=f"dl_{bot_name}|{filename}")],
        [InlineKeyboardButton(text="➕ Upload/Replace File", callback_data=f"rp_{bot_name}|{filename}")],
        [InlineKeyboardButton(text="⬅️ Back to Files",      callback_data=f"view_files_{bot_name}")],
    ])
