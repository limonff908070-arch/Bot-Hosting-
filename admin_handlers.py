import html
import os
import subprocess

import psutil

from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config import ADMIN_ID, PYTHON_PATH
from keyboards import main_reply_keyboard
from admin_keyboards import (
    admin_reply_keyboard,
    admin_user_info_keyboard,
    broadcast_cancel_reply_keyboard,
    user_lookup_cancel_reply_keyboard,
    install_cancel_reply_keyboard,
)
from user_db import get_all_users, get_user, block_user, unblock_user
import process_manager as pm

admin_router = Router()

# ─── Button Text Constants ────────────────────────────────────────────────────
BTN_ADMIN_PANEL      = "🛡 Admin Panel"
BTN_STATS            = "📊 System Stats"
BTN_BROADCAST        = "📢 Broadcast"
BTN_USERS            = "👥 User Manager"
BTN_BOTS             = "🤖 Active Bots"
BTN_RESTART          = "🔄 System Restart"
BTN_BACK_USER_MENU   = "🔙 Back to User Menu"
BTN_CANCEL_BROADCAST = "❌ Cancel Broadcast"
BTN_CANCEL_LOOKUP    = "❌ Cancel Lookup"
BTN_INSTALL          = "📦 Install Package"
BTN_CANCEL_INSTALL   = "❌ Cancel Install"


# ─── Admin FSM States ─────────────────────────────────────────────────────────

class AdminStates(StatesGroup):
    waiting_for_broadcast    = State()
    waiting_for_user_id      = State()
    waiting_for_package_name = State()


# ─── Guard helpers ────────────────────────────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def _admin_only_msg(message: Message) -> bool:
    if not _is_admin(message.from_user.id):
        await message.answer("❌ শুধু Admin এই কাজ করতে পারবে!")
        return False
    return True


async def _admin_only_cb(callback: CallbackQuery) -> bool:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ শুধু Admin!", show_alert=True)
        return False
    return True


# ─── Restore admin panel keyboard ────────────────────────────────────────────

async def _restore_admin_kb(target: Message, text: str) -> None:
    await target.answer(
        text,
        reply_markup=admin_reply_keyboard(),
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════════════════════
# 🛡 Admin Panel — Entry
# ════════════════════════════════════════════════════════════════════════════════

@admin_router.message(StateFilter("*"), F.text == BTN_ADMIN_PANEL)
async def btn_admin_panel(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return
    await state.clear()
    await message.answer(
        "🛡 <b>Admin Panel</b>\n\nনিচের বাটন থেকে অপশন বেছে নাও:",
        reply_markup=admin_reply_keyboard(),
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════════════════════
# 🔙 Back to User Menu
# ════════════════════════════════════════════════════════════════════════════════

@admin_router.message(StateFilter("*"), F.text == BTN_BACK_USER_MENU)
async def btn_back_user_menu(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return
    await state.clear()
    await message.answer(
        "🤖 <b>Master Bot Manager V2</b>\n\nনিচের Menu থেকে বেছে নাও:",
        reply_markup=main_reply_keyboard(is_admin=True),
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════════════════════
# 📊 System Stats
# ════════════════════════════════════════════════════════════════════════════════

@admin_router.message(StateFilter("*"), F.text == BTN_STATS)
async def btn_admin_stats(message: Message):
    if not await _admin_only_msg(message):
        return
    try:
        cpu_pct = psutil.cpu_percent(interval=1)
        ram     = psutil.virtual_memory()
        disk    = psutil.disk_usage(os.path.abspath("/"))

        ram_used   = ram.used  / (1024 ** 3)
        ram_total  = ram.total / (1024 ** 3)
        disk_used  = disk.used  / (1024 ** 3)
        disk_total = disk.total / (1024 ** 3)
        disk_free  = disk.free  / (1024 ** 3)

        text = (
            "📊 <b>System Stats (Real-time)</b>\n\n"
            f"🖥  <b>CPU Usage:</b>  {cpu_pct:.1f}%\n\n"
            f"🧠 <b>RAM:</b>\n"
            f"   • Used:  {ram_used:.2f} GB\n"
            f"   • Total: {ram_total:.2f} GB\n"
            f"   • Usage: {ram.percent:.1f}%\n\n"
            f"💾 <b>Disk:</b>\n"
            f"   • Used:  {disk_used:.2f} GB\n"
            f"   • Free:  {disk_free:.2f} GB\n"
            f"   • Total: {disk_total:.2f} GB\n"
            f"   • Usage: {disk.percent:.1f}%"
        )
    except Exception as e:
        text = f"❌ Stats fetch করতে পারিনি:\n<code>{html.escape(str(e))}</code>"

    await message.answer(text, parse_mode="HTML")


# ════════════════════════════════════════════════════════════════════════════════
# 📢 Broadcast — FSM
# ════════════════════════════════════════════════════════════════════════════════

@admin_router.message(StateFilter("*"), F.text == BTN_BROADCAST)
async def btn_admin_broadcast(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return
    await state.set_state(AdminStates.waiting_for_broadcast)
    await message.answer(
        "📢 <b>Broadcast Message</b>\n\n"
        "যে Message সবাইকে পাঠাতে চাও সেটা এখন Send করো।\n"
        "Text, Photo, Video, যেকোনো কিছু চলবে।",
        reply_markup=broadcast_cancel_reply_keyboard(),
        parse_mode="HTML",
    )


@admin_router.message(AdminStates.waiting_for_broadcast, F.text == BTN_CANCEL_BROADCAST)
async def btn_cancel_broadcast(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return
    await state.clear()
    await _restore_admin_kb(message, "❌ Broadcast বাতিল হয়েছে।")


@admin_router.message(AdminStates.waiting_for_broadcast)
async def handle_broadcast_message(message: Message, state: FSMContext, bot: Bot):
    if not await _admin_only_msg(message):
        return

    await state.clear()
    users   = get_all_users()
    uids    = list(users.keys())
    total   = len(uids)
    success = 0
    failed  = 0

    status_msg = await message.answer(
        f"⏳ Broadcast শুরু হচ্ছে... ({total} জন User)",
        reply_markup=admin_reply_keyboard(),
    )

    for uid in uids:
        try:
            await bot.copy_message(
                chat_id=int(uid),
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            success += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"📢 <b>Broadcast সম্পন্ন!</b>\n\n"
        f"✅ সফল:  {success}\n"
        f"❌ ব্যর্থ: {failed}\n"
        f"👥 মোট:  {total}",
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════════════════════
# 👥 User Manager — FSM
# ════════════════════════════════════════════════════════════════════════════════

@admin_router.message(StateFilter("*"), F.text == BTN_USERS)
async def btn_admin_users(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return

    users   = get_all_users()
    total   = len(users)
    blocked = sum(1 for u in users.values() if u.get("is_blocked"))

    await state.set_state(AdminStates.waiting_for_user_id)
    await message.answer(
        f"👥 <b>User Manager</b>\n\n"
        f"📋 Registered: <b>{total}</b>\n"
        f"🚫 Blocked:    <b>{blocked}</b>\n\n"
        f"দেখতে / Block করতে User ID টাইপ করো:",
        reply_markup=user_lookup_cancel_reply_keyboard(),
        parse_mode="HTML",
    )


@admin_router.message(AdminStates.waiting_for_user_id, F.text == BTN_CANCEL_LOOKUP)
async def btn_cancel_lookup(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return
    await state.clear()
    await _restore_admin_kb(message, "❌ Lookup বাতিল হয়েছে।")


@admin_router.message(AdminStates.waiting_for_user_id, F.text)
async def handle_user_id_input(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return

    raw = message.text.strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("❌ শুধু সংখ্যায় User ID লিখো।")
        return

    target_id = int(raw)
    user_data = get_user(target_id)
    if not user_data:
        await message.answer(
            f"❌ <code>{target_id}</code> — এই User Database-এ নেই।",
            parse_mode="HTML",
        )
        return

    await state.clear()

    username   = user_data.get("username") or "—"
    blocked    = user_data.get("is_blocked", False)
    reg_at     = user_data.get("registered_at", "—")
    status_txt = "🚫 Blocked" if blocked else "✅ Active"

    await message.answer(
        f"👤 <b>User Info</b>\n\n"
        f"🆔 ID:         <code>{target_id}</code>\n"
        f"📛 Username:   @{html.escape(username)}\n"
        f"📌 Status:     {status_txt}\n"
        f"📅 Registered: {reg_at[:19].replace('T', ' ')}",
        reply_markup=admin_user_info_keyboard(target_id, blocked),
        parse_mode="HTML",
    )
    await _restore_admin_kb(message, "🛡 Admin Panel:")


# ─── Block / Unblock Inline Callbacks ────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("admin_block_"))
async def callback_block_user(callback: CallbackQuery):
    if not await _admin_only_cb(callback):
        return
    target_id = int(callback.data[len("admin_block_"):])

    if target_id == ADMIN_ID:
        await callback.answer("❌ Admin-কে Block করা যাবে না!", show_alert=True)
        return

    ok = block_user(target_id)
    if not ok:
        await callback.answer("❌ User পাওয়া যায়নি।", show_alert=True)
        return

    await callback.message.edit_reply_markup(
        reply_markup=admin_user_info_keyboard(target_id, blocked=True)
    )
    await callback.answer(f"✅ {target_id} Block করা হয়েছে।")


@admin_router.callback_query(F.data.startswith("admin_unblock_"))
async def callback_unblock_user(callback: CallbackQuery):
    if not await _admin_only_cb(callback):
        return
    target_id = int(callback.data[len("admin_unblock_"):])

    ok = unblock_user(target_id)
    if not ok:
        await callback.answer("❌ User পাওয়া যায়নি।", show_alert=True)
        return

    await callback.message.edit_reply_markup(
        reply_markup=admin_user_info_keyboard(target_id, blocked=False)
    )
    await callback.answer(f"✅ {target_id} Unblock করা হয়েছে।")


# ════════════════════════════════════════════════════════════════════════════════
# 🤖 Active Bots Summary — reads active_processes.json via process_manager
# ════════════════════════════════════════════════════════════════════════════════

@admin_router.message(StateFilter("*"), F.text == BTN_BOTS)
async def btn_admin_bots(message: Message):
    if not await _admin_only_msg(message):
        return

    all_procs = pm.get_all_procs()

    if not all_procs:
        await message.answer(
            "🤖 <b>Active Bots Summary</b>\n\n<i>কোনো managed bot নেই।</i>",
            parse_mode="HTML",
        )
        return

    running = sum(1 for p in all_procs if p["alive"])
    stopped = len(all_procs) - running

    # Group by user_id
    user_map: dict[str, list[str]] = {}
    for p in all_procs:
        emoji = "🟢" if p["alive"] else "🔴"
        label = "Running" if p["alive"] else "Stopped"
        uid   = p["user_id"]
        entry = f"{emoji} {p['name']} [PID:{p['pid']}] [{label}]"
        user_map.setdefault(uid, []).append(entry)

    lines = [
        "🤖 <b>Active Bots Summary</b>\n",
        f"📦 Total Tracked: <b>{len(all_procs)}</b>",
        f"🟢 Running:       <b>{running}</b>",
        f"🔴 Stopped:       <b>{stopped}</b>",
        "\n<b>── Per-User Breakdown ──</b>",
    ]
    for uid, bot_list in user_map.items():
        lines.append(f"\n👤 User <code>{uid}</code>:")
        for entry in bot_list:
            lines.append(f"   {entry}")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ════════════════════════════════════════════════════════════════════════════════
# 🔄 System Restart — kill all tracked PIDs and respawn via Popen
# ════════════════════════════════════════════════════════════════════════════════

@admin_router.message(StateFilter("*"), F.text == BTN_RESTART)
async def btn_admin_restart(message: Message):
    if not await _admin_only_msg(message):
        return

    all_procs = pm.get_all_procs()

    if not all_procs:
        await message.answer(
            "ℹ️ কোনো tracked bot নেই। Restart করার কিছু নেই।",
            parse_mode="HTML",
        )
        return

    status_msg = await message.answer(
        f"⏳ {len(all_procs)}টি Bot restart হচ্ছে...",
        parse_mode="HTML",
    )

    ok_count    = 0
    fail_count  = 0
    result_lines: list[str] = []

    for proc_info in all_procs:
        bot_name   = proc_info["name"]
        old_pid    = proc_info["pid"]
        bot_folder = proc_info["folder"]

        # ── Kill existing process ──────────────────────────────────────────────
        if proc_info["alive"]:
            try:
                old_proc = psutil.Process(old_pid)
                old_proc.terminate()
                try:
                    old_proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    old_proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass  # Already gone — fine

        # ── Validate folder still exists ──────────────────────────────────────
        if not bot_folder or not os.path.exists(bot_folder):
            result_lines.append(f"❌ {html.escape(bot_name)}: folder নেই, skip।")
            fail_count += 1
            pm.unregister(bot_name)
            continue

        # ── Spawn fresh process ───────────────────────────────────────────────
        try:
            log_path = os.path.join(bot_folder, "bot.log")
            log_file = open(log_path, "a", encoding="utf-8", errors="replace")

            # Force UTF-8 in the child so emoji print() never crashes on cp1252
            env = os.environ.copy()
            env["PYTHONUTF8"]       = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            flags = 0
            if os.name == "nt":
                flags = subprocess.CREATE_NEW_CONSOLE

            new_proc = subprocess.Popen(
                [PYTHON_PATH, "main.py"],
                cwd=bot_folder,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=flags,
            )
            pm.update_pid(bot_name, new_proc.pid)
            result_lines.append(
                f"✅ {html.escape(bot_name)}: PID {old_pid} → {new_proc.pid}"
            )
            ok_count += 1
        except Exception as e:
            result_lines.append(f"❌ {html.escape(bot_name)}: {html.escape(str(e))}")
            fail_count += 1

    summary = (
        f"🔄 <b>System Restart সম্পন্ন!</b>\n\n"
        f"✅ সফল:  {ok_count}\n"
        f"❌ ব্যর্থ: {fail_count}\n\n"
        + "\n".join(result_lines)
    )
    await status_msg.edit_text(summary, parse_mode="HTML")


# ════════════════════════════════════════════════════════════════════════════════
# 📦 Install Package — FSM
# ════════════════════════════════════════════════════════════════════════════════

@admin_router.message(StateFilter("*"), F.text == BTN_INSTALL)
async def btn_admin_install(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return
    await state.set_state(AdminStates.waiting_for_package_name)
    await message.answer(
        "📦 <b>Install Package</b>\n\n"
        "যে Python package install করতে চাও তার নাম লিখো।\n"
        "Example: <code>requests</code>, <code>flask</code>, <code>pillow</code>",
        reply_markup=install_cancel_reply_keyboard(),
        parse_mode="HTML",
    )


@admin_router.message(AdminStates.waiting_for_package_name, F.text == BTN_CANCEL_INSTALL)
async def btn_cancel_install(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return
    await state.clear()
    await _restore_admin_kb(message, "❌ Installation বাতিল হয়েছে।")


@admin_router.message(AdminStates.waiting_for_package_name, F.text)
async def handle_package_install(message: Message, state: FSMContext):
    if not await _admin_only_msg(message):
        return

    package_name = message.text.strip()

    forbidden = (";", "&", "|", ">", "<", "`", "$", "\n", "\r")
    if any(ch in package_name for ch in forbidden) or not package_name:
        await message.answer(
            "❌ Invalid package name। শুধু সঠিক package নাম লিখো।",
            parse_mode="HTML",
        )
        return

    await state.clear()

    status_msg = await message.answer(
        f"⏳ <code>{html.escape(package_name)}</code> install হচ্ছে...",
        reply_markup=admin_reply_keyboard(),
        parse_mode="HTML",
    )

    try:
        result = subprocess.run(
            [PYTHON_PATH, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120,
        )

        raw_output = (result.stdout + result.stderr).strip()
        trimmed    = raw_output[-3000:] if len(raw_output) > 3000 else raw_output

        if result.returncode == 0:
            header = (
                f"✅ <b>Package Installed Successfully!</b>\n\n"
                f"📦 <code>{html.escape(package_name)}</code>\n\n"
            )
        else:
            header = (
                f"❌ <b>Installation Failed!</b>\n\n"
                f"📦 <code>{html.escape(package_name)}</code>\n\n"
            )

        output_block = (
            f"<pre><code>{html.escape(trimmed)}</code></pre>"
            if trimmed else "<i>(No output)</i>"
        )
        await status_msg.edit_text(header + output_block, parse_mode="HTML")

    except subprocess.TimeoutExpired:
        await status_msg.edit_text(
            f"❌ <b>Timeout!</b> Installation 120 সেকেন্ডের বেশি সময় নিচ্ছে।\n"
            f"📦 Package: <code>{html.escape(package_name)}</code>",
            parse_mode="HTML",
        )
    except FileNotFoundError:
        await status_msg.edit_text(
            "❌ Python interpreter পাওয়া যাচ্ছে না।\n"
            "<code>PYTHON_PATH</code> config চেক করো।",
            parse_mode="HTML",
        )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Unexpected Error:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )
