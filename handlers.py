import os
import zipfile
import shutil
import subprocess
import html
import time
import tempfile

import psutil

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_ID, BOTS_BASE_DIR, PYTHON_PATH
from keyboards import (
    main_reply_keyboard, upload_reply_keyboard, replace_reply_keyboard,
    mybots_keyboard, bot_action_keyboard, files_keyboard, file_action_keyboard,
)
import process_manager as pm

router = Router()

# ─── Button Text Constants ─────────────────────────────────────────────────────
BTN_UPLOAD   = "➕ Upload New Bot"
BTN_MYBOTS   = "🤖 My Bots"
BTN_DONE     = "✅ Upload Done"
BTN_CANCEL   = "❌ Cancel Upload"
BTN_CANCEL_R = "❌ Cancel Replace"

# ─── Cross-platform Temporary Directory ───────────────────────────────────────
# tempfile.gettempdir() returns:
#   Windows → C:\Users\<user>\AppData\Local\Temp
#   Linux   → /tmp
TMP_DIR = os.path.join(tempfile.gettempdir(), "master_bot_tmp")


# ─── FSM States ──────────────────────────────────────────────────────────────

class BotStates(StatesGroup):
    waiting_for_zip          = State()
    waiting_for_replace_file = State()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def get_user_bots(user_id: int) -> list[dict]:
    """
    Return tracked bots for this user from active_processes.json.
    Each dict: {name, pid, folder, alive}
    """
    return pm.get_user_procs(user_id)


def bot_folder_from_name(bot_name: str) -> str:
    """
    bot_name format: bot_<uid>_<timestamp>
    folder  format: <uid>_<timestamp>  inside BOTS_BASE_DIR
    """
    parts = bot_name.split("_", 2)   # ["bot", "<uid>", "<ts>"]
    if len(parts) == 3:
        return os.path.join(BOTS_BASE_DIR, f"{parts[1]}_{parts[2]}")
    return ""


def install_requirements(bot_folder: str) -> tuple[bool, str]:
    req_file = os.path.join(bot_folder, "requirements.txt")
    if not os.path.exists(req_file):
        return True, ""
    try:
        result = subprocess.run(
            [PYTHON_PATH, "-m", "pip", "install", "-r", req_file, "--quiet"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return False, result.stderr[:1200]
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "pip install timeout হয়েছে (120s)।"
    except Exception as e:
        return False, str(e)


def list_bot_files(bot_folder: str) -> list[str]:
    try:
        return sorted(
            f for f in os.listdir(bot_folder)
            if os.path.isfile(os.path.join(bot_folder, f))
        )
    except Exception:
        return []


def spawn_bot(bot_folder: str) -> subprocess.Popen:
    """
    Launch a sub-bot in its own console window so it runs independently.
    stdout/stderr are redirected to bot.log for Telegram log viewing.

    On Windows: CREATE_NEW_CONSOLE opens a visible terminal window per bot.
    The file handle redirect (via STARTF_USESTDHANDLES inside Popen) takes
    precedence, so all print() / logging output lands in bot.log as well.

    PYTHONUTF8=1 and PYTHONIOENCODING=utf-8 are injected so that any emoji
    inside the sub-bot's own print() / logging calls never raises
    UnicodeEncodeError on a cp1252 Windows system — without touching the
    sub-bot's source code at all.
    """
    log_path = os.path.join(bot_folder, "bot.log")
    log_file = open(log_path, "a", encoding="utf-8", errors="replace")

    # Build a UTF-8-safe environment for the child process
    env = os.environ.copy()
    env["PYTHONUTF8"]        = "1"       # PEP 540: force UTF-8 mode globally
    env["PYTHONIOENCODING"]  = "utf-8"   # legacy fallback for older Pythons

    flags = 0
    # CREATE_NEW_CONSOLE is only valid on Windows; skip on Linux/Replit preview
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_CONSOLE

    proc = subprocess.Popen(
        [PYTHON_PATH, "main.py"],
        cwd=bot_folder,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=flags,
    )
    return proc


async def _restore_main_menu(target: Message, text: str) -> None:
    is_admin_user = target.from_user.id == ADMIN_ID
    await target.answer(text, reply_markup=main_reply_keyboard(is_admin=is_admin_user), parse_mode="HTML")


# ════════════════════════════════════════════════════════════════════════════════
# /start
# ════════════════════════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    is_admin_user = message.from_user.id == ADMIN_ID
    await message.answer(
        "🤖 <b>Master Bot Manager V2</b>\n\nনিচের Menu থেকে বেছে নাও:",
        reply_markup=main_reply_keyboard(is_admin=is_admin_user),
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════════════════════
# Main Menu Reply Keyboard Buttons
# ════════════════════════════════════════════════════════════════════════════════

@router.message(StateFilter("*"), F.text == BTN_UPLOAD)
async def btn_upload_new(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.waiting_for_zip)
    await message.answer(
        "📦 <b>ZIP ফাইল Send করো।</b>\n\n"
        "ভেতরে <code>main.py</code> থাকতে হবে।\n"
        "পাঠানোর পর <b>✅ Upload Done</b> চাপো।",
        reply_markup=upload_reply_keyboard(),
        parse_mode="HTML",
    )


@router.message(StateFilter("*"), F.text == BTN_MYBOTS)
async def btn_my_bots(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is not None:
        await state.clear()
        await _restore_main_menu(message, "⚠️ আগের কাজ বাতিল হয়েছে।")

    user_bots = get_user_bots(message.from_user.id)
    if not user_bots:
        await message.answer(
            "তোমার কোনো Bot চলছে না।\n<b>➕ Upload New Bot</b> চেপে নতুন Bot যোগ করো।",
            parse_mode="HTML",
        )
        return
    await message.answer(
        f"🤖 <b>তোমার Bot List ({len(user_bots)}):</b>\nএকটিতে ট্যাপ করো:",
        reply_markup=mybots_keyboard(user_bots),
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════════════════════
# Upload Flow  (waiting_for_zip state)
# ════════════════════════════════════════════════════════════════════════════════

@router.message(BotStates.waiting_for_zip, F.text == BTN_CANCEL)
async def btn_cancel_upload(message: Message, state: FSMContext):
    data = await state.get_data()
    zip_path = data.get("zip_path")
    if zip_path:
        try:
            os.remove(zip_path)
        except OSError:
            pass
    await state.clear()
    await _restore_main_menu(message, "❌ Upload বাতিল হয়েছে।")


@router.message(BotStates.waiting_for_zip, F.document)
async def handle_zip_upload(message: Message, state: FSMContext, bot: Bot):
    document = message.document
    if not document.file_name.lower().endswith(".zip"):
        await message.answer(
            "❌ শুধু <b>.zip</b> ফাইল Allow।",
            parse_mode="HTML",
        )
        return

    try:
        os.makedirs(TMP_DIR, exist_ok=True)
    except Exception as e:
        await message.answer(
            f"❌ Temp folder তৈরি করতে পারিনি:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )
        return

    tmp_path = os.path.join(TMP_DIR, f"{message.from_user.id}.zip")

    try:
        file_info   = await bot.get_file(document.file_id)
        destination = open(tmp_path, "wb")
        try:
            await bot.download_file(file_info.file_path, destination=destination)
        finally:
            destination.flush()
            destination.close()
    except Exception as e:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        await message.answer(f"❌ File Download Error:\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")
        return

    await state.update_data(zip_path=tmp_path)
    await message.answer(
        "📦 File পাওয়া গেছে ✅\n\nএখন <b>✅ Upload Done</b> বাটন চাপো।",
        parse_mode="HTML",
    )


@router.message(BotStates.waiting_for_zip, F.text == BTN_DONE)
async def btn_upload_done(message: Message, state: FSMContext):
    data     = await state.get_data()
    zip_path = data.get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        await message.answer("❌ আগে ZIP ফাইল পাঠাও!")
        return

    user_id    = message.from_user.id
    timestamp  = int(time.time())
    bot_name   = f"bot_{user_id}_{timestamp}"
    bot_folder = os.path.join(BOTS_BASE_DIR, f"{user_id}_{timestamp}")

    status_msg = await message.answer("⏳ Processing... একটু অপেক্ষা করো।")

    # ── 1. Create bot folder ───────────────────────────────────────────────────
    try:
        os.makedirs(bot_folder, exist_ok=True)
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Folder তৈরি করতে পারিনি:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )
        await state.clear()
        await _restore_main_menu(message, "❌ ব্যর্থ হয়েছে।")
        return

    # ── 2. Extract ZIP ─────────────────────────────────────────────────────────
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(bot_folder)
    except zipfile.BadZipFile:
        shutil.rmtree(bot_folder, ignore_errors=True)
        await status_msg.edit_text("❌ ZIP File Corrupt বা Invalid।")
        await state.clear()
        await _restore_main_menu(message, "❌ ব্যর্থ হয়েছে।")
        return
    except Exception as e:
        shutil.rmtree(bot_folder, ignore_errors=True)
        await status_msg.edit_text(
            f"❌ Extract Error:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )
        await state.clear()
        await _restore_main_menu(message, "❌ ব্যর্থ হয়েছে।")
        return

    # ── 3. Validate main.py presence ──────────────────────────────────────────
    if not os.path.exists(os.path.join(bot_folder, "main.py")):
        shutil.rmtree(bot_folder, ignore_errors=True)
        await status_msg.edit_text("❌ ZIP এ <code>main.py</code> নেই!", parse_mode="HTML")
        await state.clear()
        await _restore_main_menu(message, "❌ ব্যর্থ হয়েছে।")
        return

    # ── 4. Install requirements ────────────────────────────────────────────────
    await status_msg.edit_text("⏳ Dependencies install হচ্ছে...")
    ok, err = install_requirements(bot_folder)
    if not ok:
        shutil.rmtree(bot_folder, ignore_errors=True)
        await status_msg.edit_text(
            f"❌ pip install failed:\n<code>{html.escape(str(err))}</code>",
            parse_mode="HTML",
        )
        await state.clear()
        await _restore_main_menu(message, "❌ ব্যর্থ হয়েছে।")
        return

    # ── 5. Spawn the sub-bot with subprocess.Popen ────────────────────────────
    await status_msg.edit_text("⏳ Bot শুরু হচ্ছে...")
    try:
        proc = spawn_bot(bot_folder)
    except Exception as e:
        shutil.rmtree(bot_folder, ignore_errors=True)
        await status_msg.edit_text(
            f"❌ Bot start error:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )
        await state.clear()
        await _restore_main_menu(message, "❌ ব্যর্থ হয়েছে।")
        return

    # ── 6. Register PID in active_processes.json ──────────────────────────────
    pm.register(bot_name, proc.pid, bot_folder, user_id)

    await state.clear()
    try:
        os.remove(zip_path)
    except OSError:
        pass

    await status_msg.edit_text(
        f"🚀 <b>Bot চালু হয়েছে!</b>\n\n"
        f"🤖 Name:   <code>{bot_name}</code>\n"
        f"🔢 PID:    <code>{proc.pid}</code>\n"
        f"📂 Folder: <code>{html.escape(bot_folder)}</code>\n"
        f"📋 Logs:   <code>bot.log</code> (View Logs বাটনে দেখো)\n"
        f"✅ Running",
        parse_mode="HTML",
    )
    await message.answer(
        "Bot manage করতে নিচে ট্যাপ করো:",
        reply_markup=main_reply_keyboard(is_admin=is_admin(user_id)),
    )


@router.message(BotStates.waiting_for_zip, ~F.document)
async def handle_wrong_zip_input(message: Message):
    if message.text and (message.text.startswith("/") or message.text in (BTN_UPLOAD, BTN_MYBOTS, BTN_DONE, BTN_CANCEL)):
        return
    await message.answer("❌ শুধু <b>.zip</b> ফাইল পাঠাও।", parse_mode="HTML")


# ════════════════════════════════════════════════════════════════════════════════
# Inline Callbacks — Bot List & Navigation
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "back_bots")
async def callback_back_bots(callback: CallbackQuery):
    user_bots = get_user_bots(callback.from_user.id)
    if not user_bots:
        await callback.message.edit_text("তোমার কোনো Bot চলছে না।")
        await callback.answer()
        return
    await callback.message.edit_text(
        f"🤖 <b>তোমার Bot List ({len(user_bots)}):</b>",
        reply_markup=mybots_keyboard(user_bots),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bot_info_"))
async def callback_bot_info(callback: CallbackQuery):
    bot_name = callback.data[len("bot_info_"):]
    user_id  = str(callback.from_user.id)
    if not bot_name.startswith(f"bot_{user_id}_"):
        await callback.answer("❌ এটা তোমার Bot না!", show_alert=True)
        return

    # Live status via psutil
    procs = pm.get_user_procs(callback.from_user.id)
    entry = next((p for p in procs if p["name"] == bot_name), None)
    if entry:
        status = "🟢 Running" if entry["alive"] else "🔴 Stopped"
        pid_txt = str(entry["pid"])
    else:
        status  = "❓ Unknown"
        pid_txt = "—"

    await callback.message.edit_text(
        f"🤖 <b>{html.escape(bot_name)}</b>\n\n"
        f"📌 Status: {status}\n"
        f"🔢 PID:    <code>{pid_txt}</code>\n\n"
        f"কী করতে চাও?",
        reply_markup=bot_action_keyboard(bot_name),
        parse_mode="HTML",
    )
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# View Logs — reads bot.log from the bot's folder
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("view_logs_"))
async def callback_view_logs(callback: CallbackQuery):
    bot_name = callback.data[len("view_logs_"):]
    user_id  = str(callback.from_user.id)
    if not bot_name.startswith(f"bot_{user_id}_"):
        await callback.answer("❌ এটা তোমার Bot না!", show_alert=True)
        return

    await callback.answer("⏳ Logs লোড হচ্ছে...")

    bot_folder = bot_folder_from_name(bot_name)
    log_path   = os.path.join(bot_folder, "bot.log")

    if not bot_folder or not os.path.exists(bot_folder):
        await callback.message.answer("❌ Bot folder পাওয়া যাচ্ছে না!")
        return

    if not os.path.exists(log_path):
        await callback.message.answer(
            f"📋 <b>Logs — {html.escape(bot_name)}:</b>\n\n"
            "<i>⚠️ bot.log এখনো তৈরি হয়নি। Bot হয়তো এইমাত্র শুরু হয়েছে।</i>",
            parse_mode="HTML",
            reply_markup=bot_action_keyboard(bot_name),
        )
        return

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Show last 3500 chars so it fits in a Telegram message
        if not content.strip():
            display = "<i>⚠️ Log ফাইল এখনো খালি।</i>"
        else:
            tail    = content[-3500:]
            display = f"<pre>{html.escape(tail)}</pre>"

        await callback.message.answer(
            f"📋 <b>Logs — {html.escape(bot_name)}:</b>\n\n{display}",
            parse_mode="HTML",
            reply_markup=bot_action_keyboard(bot_name),
        )
    except Exception as e:
        await callback.message.answer(
            f"❌ Log পড়তে পারিনি:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )


# ════════════════════════════════════════════════════════════════════════════════
# View Files
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("view_files_"))
async def callback_view_files(callback: CallbackQuery):
    bot_name   = callback.data[len("view_files_"):]
    user_id    = str(callback.from_user.id)
    if not bot_name.startswith(f"bot_{user_id}_"):
        await callback.answer("❌ এটা তোমার Bot না!", show_alert=True)
        return
    bot_folder = bot_folder_from_name(bot_name)
    if not bot_folder or not os.path.exists(bot_folder):
        await callback.answer("❌ Bot folder পাওয়া যাচ্ছে না!", show_alert=True)
        return
    files = list_bot_files(bot_folder)
    if not files:
        await callback.answer("❌ Folder খালি!", show_alert=True)
        return
    await callback.message.edit_text(
        f"📁 <b>{html.escape(bot_name)}</b>\nFiles ({len(files)}) — একটিতে ট্যাপ করো:",
        reply_markup=files_keyboard(bot_name, files),
        parse_mode="HTML",
    )
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# File Actions (Download / Replace)
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("fi_"))
async def callback_file_info(callback: CallbackQuery):
    raw = callback.data[3:]
    if "|" not in raw:
        await callback.answer("❌ Invalid data.", show_alert=True)
        return
    bot_name, filename = raw.split("|", 1)
    user_id = str(callback.from_user.id)
    if not bot_name.startswith(f"bot_{user_id}_"):
        await callback.answer("❌ এটা তোমার Bot না!", show_alert=True)
        return
    await callback.message.edit_text(
        f"📄 <b>{html.escape(filename)}</b>\n\nকী করতে চাও?",
        reply_markup=file_action_keyboard(bot_name, filename),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dl_"))
async def callback_download_file(callback: CallbackQuery, bot: Bot):
    raw = callback.data[3:]
    if "|" not in raw:
        await callback.answer("❌ Invalid data.", show_alert=True)
        return
    bot_name, filename = raw.split("|", 1)
    user_id = str(callback.from_user.id)
    if not bot_name.startswith(f"bot_{user_id}_"):
        await callback.answer("❌ এটা তোমার Bot না!", show_alert=True)
        return
    bot_folder = bot_folder_from_name(bot_name)
    file_path  = os.path.join(bot_folder, filename)
    if not os.path.abspath(file_path).startswith(os.path.abspath(bot_folder)):
        await callback.answer("❌ Invalid path.", show_alert=True)
        return
    if not os.path.exists(file_path):
        await callback.answer("❌ File পাওয়া যাচ্ছে না!", show_alert=True)
        return
    await callback.answer("⏳ File পাঠানো হচ্ছে...")
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        await bot.send_document(
            chat_id=callback.from_user.id,
            document=BufferedInputFile(data, filename=filename),
            caption=f"📄 <b>{html.escape(filename)}</b>\n📂 {html.escape(bot_name)}",
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.answer(
            f"❌ File পাঠাতে পারিনি:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("rp_"))
async def callback_replace_trigger(callback: CallbackQuery, state: FSMContext):
    raw = callback.data[3:]
    if "|" not in raw:
        await callback.answer("❌ Invalid data.", show_alert=True)
        return
    bot_name, filename = raw.split("|", 1)
    user_id = str(callback.from_user.id)
    if not bot_name.startswith(f"bot_{user_id}_"):
        await callback.answer("❌ এটা তোমার Bot না!", show_alert=True)
        return
    bot_folder = bot_folder_from_name(bot_name)
    await state.set_state(BotStates.waiting_for_replace_file)
    await state.update_data(
        replace_bot_name=bot_name,
        replace_filename=filename,
        replace_folder=bot_folder,
    )
    await callback.message.answer(
        f"📤 <b>{html.escape(filename)}</b> replace করতে নতুন ফাইলটি পাঠাও:",
        reply_markup=replace_reply_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# Replace File — FSM (waiting_for_replace_file)
# ════════════════════════════════════════════════════════════════════════════════

@router.message(BotStates.waiting_for_replace_file, F.text == BTN_CANCEL_R)
async def btn_cancel_replace(message: Message, state: FSMContext):
    await state.clear()
    await _restore_main_menu(message, "❌ Replace বাতিল হয়েছে।")


@router.message(BotStates.waiting_for_replace_file, F.document)
async def handle_replace_file(message: Message, state: FSMContext, bot: Bot):
    data       = await state.get_data()
    bot_name   = data.get("replace_bot_name")
    filename   = data.get("replace_filename")
    bot_folder = data.get("replace_folder")

    if not all([bot_name, filename, bot_folder]):
        await message.answer("❌ Session data হারিয়ে গেছে। আবার চেষ্টা করো।")
        await state.clear()
        await _restore_main_menu(message, "❌ ব্যর্থ হয়েছে।")
        return

    if not os.path.exists(bot_folder):
        await message.answer("❌ Bot folder পাওয়া যাচ্ছে না!")
        await state.clear()
        await _restore_main_menu(message, "❌ ব্যর্থ হয়েছে।")
        return

    dest_path = os.path.join(bot_folder, filename)
    if not os.path.abspath(dest_path).startswith(os.path.abspath(bot_folder)):
        await message.answer("❌ Invalid file path।")
        await state.clear()
        await _restore_main_menu(message, "❌ ব্যর্থ হয়েছে।")
        return

    try:
        os.makedirs(TMP_DIR, exist_ok=True)
    except Exception as e:
        await message.answer(
            f"❌ Temp folder তৈরি করতে পারিনি:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )
        return

    tmp_path = os.path.join(TMP_DIR, f"replace_{message.from_user.id}_{int(time.time())}")

    try:
        file_info   = await bot.get_file(message.document.file_id)
        destination = open(tmp_path, "wb")
        try:
            await bot.download_file(file_info.file_path, destination=destination)
        finally:
            destination.flush()
            destination.close()
    except Exception as e:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        await message.answer(
            f"❌ Download Error:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )
        return

    try:
        shutil.move(tmp_path, dest_path)
    except Exception as e:
        await message.answer(
            f"❌ File save করতে পারিনি:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return

    await state.clear()
    await message.answer(
        f"✅ <b>{html.escape(filename)}</b> সফলভাবে Replace হয়েছে!\n\n"
        f"♻️ পরিবর্তন কার্যকর করতে Bot restart করো।",
        reply_markup=main_reply_keyboard(is_admin=is_admin(message.from_user.id)),
        parse_mode="HTML",
    )


@router.message(BotStates.waiting_for_replace_file, ~F.document)
async def handle_wrong_replace_input(message: Message):
    if message.text and (message.text.startswith("/") or message.text in (BTN_UPLOAD, BTN_MYBOTS, BTN_CANCEL_R)):
        return
    await message.answer("❌ শুধু একটি <b>File</b> পাঠাও।", parse_mode="HTML")


# ════════════════════════════════════════════════════════════════════════════════
# Delete Bot — kill PID + unregister + delete folder
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("stop_bot_"))
async def callback_stop_bot(callback: CallbackQuery):
    bot_name = callback.data[len("stop_bot_"):]
    user_id  = str(callback.from_user.id)
    if not bot_name.startswith(f"bot_{user_id}_"):
        await callback.answer("❌ এটা তোমার Bot না!", show_alert=True)
        return

    errors: list[str] = []

    # ── 1. Kill the process if alive ──────────────────────────────────────────
    procs = pm.get_user_procs(callback.from_user.id)
    entry = next((p for p in procs if p["name"] == bot_name), None)
    if entry and entry["alive"]:
        try:
            proc = psutil.Process(entry["pid"])
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            errors.append(f"kill: {e}")

    # ── 2. Remove from tracking JSON ──────────────────────────────────────────
    pm.unregister(bot_name)

    # ── 3. Delete bot folder from disk ────────────────────────────────────────
    bot_folder = bot_folder_from_name(bot_name)
    if bot_folder and os.path.exists(bot_folder):
        try:
            shutil.rmtree(bot_folder)
        except Exception as e:
            errors.append(f"rmtree: {e}")

    if errors:
        result_text = (
            f"⚠️ Partially Deleted <code>{html.escape(bot_name)}</code>\n"
            + "\n".join(f"• {html.escape(str(e))}" for e in errors)
        )
    else:
        result_text = f"🗑 Deleted ✅ <code>{html.escape(bot_name)}</code>"

    await callback.message.edit_text(result_text, parse_mode="HTML")
    await callback.message.answer(
        "🏠 Main Menu:",
        reply_markup=main_reply_keyboard(is_admin=is_admin(callback.from_user.id)),
    )
    await callback.answer()
