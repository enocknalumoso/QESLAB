"""
QES Telegram Bot — Production
Inline keyboard, daily briefing, stream control, signal delivery.
"""
import asyncio
from datetime import datetime, timezone
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from loguru import logger
from configs.settings import settings
from core.health_monitor import health_monitor
from core.pocket_manager import pocket_manager
from core.stream_controller import stream_controller
from signals.formatter import format_forex, format_binary
from signals.operator_feedback import operator_feedback


class QESTelegramBot:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.allowed_user_ids = [
            int(x.strip()) for x in settings.TELEGRAM_ALLOWED_USER_IDS.split(",")
            if x.strip().isdigit()
        ]
        self.app = ApplicationBuilder().token(self.token).build()
        self._add_handlers()
        self._setup_commands()
        logger.info(f"Telegram bot init | allowed users: {self.allowed_user_ids}")

    def _add_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("health", self.health))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("streams", self.streams))
        self.app.add_handler(CommandHandler("briefing", self.briefing))
        self.app.add_handler(CommandHandler("performance", self.performance))
        self.app.add_handler(CommandHandler("dd", self.dd))
        self.app.add_handler(CallbackQueryHandler(self.callback_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo))

    def _setup_commands(self):
        commands = [
            BotCommand("start", "Start bot"),
            BotCommand("health", "System health"),
            BotCommand("status", "Account status"),
            BotCommand("streams", "Toggle streams"),
            BotCommand("briefing", "Daily briefing"),
            BotCommand("performance", "Today's stats"),
            BotCommand("dd", "Drawdown status"),
        ]
        

    # ── AUTH ──────────────────────────────────────────────────────
    def _is_allowed(self, user_id: int) -> bool:
        return user_id in self.allowed_user_ids

    # ── COMMANDS ──────────────────────────────────────────────────
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("Unauthorized.")
            return
        await update.message.reply_text(
            "✅ QES Signal Lab active.\n"
            "Commands:\n"
            "/health — System status\n"
            "/status — Account balances\n"
            "/streams — Toggle signal streams\n"
            "/briefing — Daily briefing\n"
            "/performance — Today's stats\n"
            "/dd — Drawdown status"
        )

    async def health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        health = health_monitor.get_system_health()
        msg = (
            f"🖥️ System Health: {health.get('status', 'UNKNOWN')}\n"
            f"CPU: {health.get('cpu', 0)}%\n"
            f"RAM: {health.get('ram', 0)}%\n"
            f"Disk: {health.get('disk', 0)}%\n"
            f"Uptime: {health.get('uptime', '?')}"
        )
        await update.message.reply_text(msg)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        f_state = pocket_manager.get_state("FOREX")
        b_state = pocket_manager.get_state("BINARY")
        msg = (
            f"📊 Account Status\n"
            f"Forex: ${f_state.get('balance', 0):.0f} | DD: {f_state.get('daily_dd', 0)*100:.1f}%\n"
            f"Binary: ${b_state.get('balance', 0):.0f} | DD: {b_state.get('daily_dd', 0)*100:.1f}%\n"
            f"Heat: {f_state.get('heat', 0)*100:.1f}% | {b_state.get('heat', 0)*100:.1f}%"
        )
        await update.message.reply_text(msg)

    async def streams(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        keyboard = [
            [
                InlineKeyboardButton(
                    f"Forex {'🟢 ON' if stream_controller.forex_enabled else '🔴 OFF'}",
                    callback_data="toggle_FOREX"
                ),
                InlineKeyboardButton(
                    f"Binary {'🟢 ON' if stream_controller.binary_enabled else '🔴 OFF'}",
                    callback_data="toggle_BINARY"
                ),
            ],
            [
                InlineKeyboardButton(
                    f"Day {'🟢 ON' if stream_controller.day_enabled else '🔴 OFF'}",
                    callback_data="toggle_DAY"
                ),
                InlineKeyboardButton(
                    f"Swing {'🟢 ON' if stream_controller.swing_enabled else '🔴 OFF'}",
                    callback_data="toggle_SWING"
                ),
            ],
            [
                InlineKeyboardButton(
                    f"5M {'🟢 ON' if stream_controller.binary_5m_enabled else '🔴 OFF'}",
                    callback_data="toggle_BINARY_5M"
                ),
                InlineKeyboardButton(
                    f"10M {'🟢 ON' if stream_controller.binary_10m_enabled else '🔴 OFF'}",
                    callback_data="toggle_BINARY_10M"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚙️ Stream Control\nTap to toggle:",
            reply_markup=reply_markup
        )

    async def briefing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        briefing = pocket_manager.generate_daily_briefing()
        await update.message.reply_text(briefing)

    async def performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        # Placeholder — later integrate performance_attr.py
        await update.message.reply_text("📈 Today's stats:\nWIP")

    async def dd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        f_state = pocket_manager.get_state("FOREX")
        b_state = pocket_manager.get_state("BINARY")
        msg = (
            f"📉 Drawdown Status\n"
            f"Forex daily: {f_state.get('daily_dd', 0)*100:.1f}% / {settings.FOREX_DAILY_LOSS_HALT*100:.1f}%\n"
            f"Binary daily: {b_state.get('daily_dd', 0)*100:.1f}% / {settings.BINARY_DAILY_LOSS_HALT*100:.1f}%\n"
            f"Circuit breaker: {'🔴' if f_state.get('breaker_active') or b_state.get('breaker_active') else '🟢'}"
        )
        await update.message.reply_text(msg)

    # ── CALLBACK HANDLER ──────────────────────────────────────────
    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        if not self._is_allowed(user_id):
            await query.edit_message_text("Unauthorized.")
            return

        data = query.data

        # Stream toggles
        if data.startswith("toggle_"):
            stream = data.split("_")[1]
            # TODO: integrate with stream_controller.toggle_stream(stream)
            await query.edit_message_text(f"Toggled {stream} — WIP")
            return

        # Signal feedback (WIN/LOSS/BE/SKIP)
        if data.startswith("signal_"):
            parts = data.split("_")
            if len(parts) != 3:
                return
            outcome, signal_id, stream = parts
            operator_feedback.feedback(signal_id, outcome.upper(), stream)
            await query.edit_message_text(f"✅ Recorded {outcome.upper()} for {signal_id}")
            return

        # Unknown callback
        await query.edit_message_text("Unknown action.")

    # ── SIGNAL SENDING ────────────────────────────────────────────
    async def send_signal(self, signal: dict):
        """Send formatted signal to allowed users."""
        if signal.get("stream") == "FOREX":
            text = format_forex(signal)
        else:
            text = format_binary(signal)

        keyboard = [
            [
                InlineKeyboardButton("✅ WIN", callback_data=f"signal_WIN_{signal['signal_id']}_{signal['stream']}"),
                InlineKeyboardButton("❌ LOSS", callback_data=f"signal_LOSS_{signal['signal_id']}_{signal['stream']}"),
            ],
            [
                InlineKeyboardButton("➡️ BE", callback_data=f"signal_BE_{signal['signal_id']}_{signal['stream']}"),
                InlineKeyboardButton("⏭ SKIP", callback_data=f"signal_SKIP_{signal['signal_id']}_{signal['stream']}"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        for uid in self.allowed_user_ids:
            try:
                await self.app.bot.send_message(
                    chat_id=uid,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to send signal to {uid}: {e}")

    async def send_presignal_warning(self, pair: str, stream: str):
        """T-30s warning."""
        for uid in self.allowed_user_ids:
            try:
                await self.app.bot.send_message(
                    chat_id=uid,
                    text=f"⚠️ [{pair}] signal incoming. Open platform now.",
                )
            except Exception as e:
                logger.error(f"Failed to send presignal to {uid}: {e}")

    # ── ECHO ──────────────────────────────────────────────────────
    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        await update.message.reply_text("Use /commands")

    # ── RUN ───────────────────────────────────────────────────────
    def run(self):
        logger.info("Starting Telegram bot polling...")
        self.app.run_polling(drop_pending_updates=True)


bot = QESTelegramBot()
