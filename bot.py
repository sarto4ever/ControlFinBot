import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)

CONFIG_FILE = 'config.json'

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()
TOKEN = config["token"]
AUTHORIZED_USERS = config["authorized_users"]

# === Состояния ===
ADDING_EXPENSE, ADDING_INCOME, ADDING_BUTTON_LABEL, ADDING_BUTTON_AMOUNT, ADDING_CUSTOM_CURRENCY = range(5)
DATA_FILE = 'data.json'
temp_button = {}

def get_currency():
    data = load_data()
    return data.get("currency", "₽")


# === Работа с JSON ===
def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# === Главное меню ===

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Проверим, откуда вызывать возврат
    current_state = context.user_data.get('state')

    if current_state == "adding_button":
        # Вернёмся в меню управления кнопками
        await button_handler(update, context)  # повторно вызовем с тем же callback_data
        return ConversationHandler.END

    # По умолчанию — в главное меню
    await start(query, context, is_edit=True)
    return ConversationHandler.END


async def start(source, context: ContextTypes.DEFAULT_TYPE, is_edit=False):
    if hasattr(source, 'from_user'):
        user = source.from_user
        chat_id = source.message.chat_id if hasattr(source, 'message') else source.message.chat.id
    else:
        user = source.effective_user
        chat_id = source.effective_chat.id

    if user.id not in AUTHORIZED_USERS:
        await context.bot.send_message(chat_id=chat_id, text="⛔️ У вас нет доступа.")
        return

    data = load_data()
    buttons = data.get("expense_buttons", [])
    quick_buttons = [
        InlineKeyboardButton(f"{item['label']} ({item['amount']}{get_currency()})", callback_data=f"quick_expense:{item['amount']}")
        for item in buttons
    ]
    rows = [quick_buttons[i:i + 2] for i in range(0, len(quick_buttons), 2)]

    keyboard = [
        [InlineKeyboardButton("➕ Ввести вручную", callback_data='add_expense')],
        *rows,
        [InlineKeyboardButton("💰 Добавить деньги", callback_data='add_income')],
        [InlineKeyboardButton("📊 Баланс", callback_data='view_balance')],
        [InlineKeyboardButton("🕘 История", callback_data='history')],
        [InlineKeyboardButton("⚙️ Управление кнопками", callback_data='manage_buttons')],
        [InlineKeyboardButton("⚠️ Администрирование", callback_data='admin_menu')]
    ]

    # Главное: всегда редактируем сообщение, если можно
    if hasattr(source, 'edit_message_text'):
        await source.edit_message_text("Выберите действие:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id=chat_id, text="Выберите действие:", reply_markup=InlineKeyboardMarkup(keyboard))


# === Обработка всех кнопок ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if user.id not in AUTHORIZED_USERS:
        await query.edit_message_text("⛔️ Нет доступа.")
        return

    match query.data:
        case 'add_expense':
            await query.edit_message_text("Введите сумму траты:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ]))
            return ADDING_EXPENSE

        case 'add_income':
            await query.edit_message_text("Введите сумму пополнения:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ]))
            return ADDING_INCOME

        case 'view_balance':
            balance = load_data()['balance']
            await query.edit_message_text(f"📊 Баланс: {balance}{get_currency()}", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ]))
            return ConversationHandler.END

        case data if data.startswith("quick_expense:"):
            amount = float(data.split(":")[1])
            db = load_data()
            db['balance'] -= amount
            db['transactions'].append({
                "type": "expense",
                "amount": amount,
                "user_id": user.id,
                "user_name": user.first_name,
                "timestamp": datetime.now().isoformat()
            })
            save_data(db)
            await query.edit_message_text(f"✅ Трата {amount}{get_currency()} добавлена. Баланс: {db['balance']}{get_currency()}", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ]))
            return ConversationHandler.END

        case 'history':
            keyboard = [
                [InlineKeyboardButton("5", callback_data="history_limit:5"),
                 InlineKeyboardButton("10", callback_data="history_limit:10"),
                 InlineKeyboardButton("20", callback_data="history_limit:20"),
                 InlineKeyboardButton("50", callback_data="history_limit:50")],
                [InlineKeyboardButton("📄 Все транзакции", callback_data="all_transactions")],
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ]
            await query.edit_message_text("Сколько транзакций показать?", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

        case data if data.startswith("history_limit:"):
            limit = int(data.split(":")[1])
            context.user_data['history_limit'] = limit
            context.user_data['history_page'] = 0
            return await show_history_page(query, context)

        case 'history_next':
            context.user_data['history_page'] += 1
            return await show_history_page(query, context)

        case 'history_prev':
            context.user_data['history_page'] -= 1
            return await show_history_page(query, context)

        case 'manage_buttons':
            db = load_data()
            keyboard = [
                [InlineKeyboardButton(f"❌ Удалить: {b['label']}", callback_data=f"delete_button:{i}")]
                for i, b in enumerate(db.get("expense_buttons", []))
            ]
            keyboard.append([InlineKeyboardButton("➕ Добавить", callback_data='add_button')])
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back')])
            await query.edit_message_text("⚙️ Кнопки трат:", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

        case data if data.startswith("delete_button:"):
            index = int(data.split(":")[1])
            db = load_data()
            if 0 <= index < len(db["expense_buttons"]):
                removed = db["expense_buttons"].pop(index)
                save_data(db)
                await query.edit_message_text(f"Удалено: {removed['label']}", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data='manage_buttons')]
                ]))
            return ConversationHandler.END

        case 'add_button':
            context.user_data['state'] = 'adding_button'
            await query.edit_message_text("Введите название кнопки:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ]))
            return ADDING_BUTTON_LABEL


        case 'admin_menu':
            keyboard = [
                [InlineKeyboardButton("🗑 Очистить историю", callback_data="clear_history_confirm")],
                [InlineKeyboardButton("🔄 Сбросить баланс", callback_data="reset_balance_confirm")],
                [InlineKeyboardButton("💱 Изменить валюту", callback_data="change_currency")],
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ]
            await query.edit_message_text("⚠️ Администрирование:", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

        case 'clear_history_confirm':
            db = load_data()
            db["transactions"] = []
            save_data(db)
            await query.edit_message_text("🗑 История очищена.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ]))
            return ConversationHandler.END

        case 'reset_balance_confirm':
            db = load_data()
            db["balance"] = 0
            save_data(db)
            await query.edit_message_text(f"🔄 Баланс сброшен до 0{get_currency()}.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ]))
            return ConversationHandler.END

        case 'back':
            await start(query, context, is_edit=True)
            return ConversationHandler.END

        case 'all_transactions':
            data = load_data()
            transactions = data.get("transactions", [])

            if not transactions:
                await query.edit_message_text("История пуста.", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data='back')]
                ]))
                return ConversationHandler.END

            lines = []
            for tx in reversed(transactions):
                dt = datetime.fromisoformat(tx["timestamp"]).strftime("%d.%m %H:%M")
                icon = "➕" if tx["type"] == "income" else "➖"
                name = tx.get("user_name", "❓")
                lines.append(f"{icon} {tx['amount']}{get_currency()} — {dt} ({name})")

            # Если строк много — разбить на части
            chunk_size = 40
            if len(lines) > chunk_size:
                chunks = [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]
                for chunk in chunks:
                    await query.message.reply_text("\n".join(chunk))
                await query.edit_message_text(f"📄 Показано {len(lines)} транзакций.", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data='back')]
                ]))
            else:
                await query.edit_message_text("📄 Все транзакции:\n" + "\n".join(lines), reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data='back')]
                ]))
            return ConversationHandler.END

        case 'change_currency':
            keyboard = [
                [InlineKeyboardButton("₽", callback_data='currency:₽'),
                 InlineKeyboardButton("$", callback_data='currency:$'),
                 InlineKeyboardButton("€", callback_data='currency:€')],
                [InlineKeyboardButton("₸", callback_data='currency:₸'),
                 InlineKeyboardButton("£", callback_data='currency:£')],
                [InlineKeyboardButton("₺", callback_data='currency:₺'),
                 InlineKeyboardButton("₦", callback_data='currency:₦'),
                 InlineKeyboardButton("K", callback_data='currency:K')],
                [InlineKeyboardButton("➕ Своя", callback_data='currency_custom')],
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_menu')]
            ]
            await query.edit_message_text("Выберите валюту:", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

        case data if data.startswith('currency:'):
            symbol = data.split(":")[1]
            db = load_data()
            db["currency"] = symbol
            save_data(db)
            await query.edit_message_text(f"✅ Валюта изменена на: {symbol}", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_menu')]
            ]))
            return ConversationHandler.END
        
        case 'currency_custom':
            await query.edit_message_text("Введите свой символ или код валюты (например: USDT, 💎, ¥):", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='change_currency')]
            ]))
            return ADDING_CUSTOM_CURRENCY

    return ConversationHandler.END

# === История с постраничным просмотром ===
async def show_history_page(query, context):
    db = load_data()
    txs = db.get("transactions", [])
    limit = context.user_data.get("history_limit", 10)
    page = context.user_data.get("history_page", 0)

    total = len(txs)
    pages = max(1, (total + limit - 1) // limit)
    page = max(0, min(page, pages - 1))
    context.user_data["history_page"] = page

    start, end = page * limit, (page + 1) * limit
    lines = []

    for tx in txs[::-1][start:end]:
        dt = datetime.fromisoformat(tx["timestamp"]).strftime("%d.%m %H:%M")
        name = tx.get("user_name", "❓")
        icon = "➕" if tx["type"] == "income" else "➖"
        lines.append(f"{icon} {tx['amount']}{get_currency()} — {dt} ({name})")

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data="history_prev"))
    if end < total:
        nav.append(InlineKeyboardButton("➡️", callback_data="history_next"))

    keyboard = [nav] if nav else []
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back')])

    await query.edit_message_text(
        f"🕘 История (стр. {page+1} из {pages}):\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# === Ручной ввод трат и доходов ===
async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
    except:
        await update.message.reply_text("Неверная сумма.")
        return ADDING_EXPENSE
    db = load_data()
    db["balance"] -= amount
    db["transactions"].append({
        "type": "expense",
        "amount": amount,
        "user_id": update.effective_user.id,
        "user_name": update.effective_user.first_name,
        "timestamp": datetime.now().isoformat()
    })
    save_data(db)
    await update.message.reply_text(f"✅ Трата {amount}{get_currency()} добавлена. Баланс: {db['balance']}{get_currency()}", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data='back')]
    ]))
    return ConversationHandler.END

async def handle_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
    except:
        await update.message.reply_text("Неверная сумма.")
        return ADDING_INCOME
    db = load_data()
    db["balance"] += amount
    db["transactions"].append({
        "type": "income",
        "amount": amount,
        "user_id": update.effective_user.id,
        "user_name": update.effective_user.first_name,
        "timestamp": datetime.now().isoformat()
    })
    save_data(db)
    await update.message.reply_text(f"✅ Пополнение {amount}{get_currency()} добавлено. Баланс: {db['balance']}{get_currency()}", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data='back')]
    ]))
    return ConversationHandler.END

async def handle_button_label(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp_button['label'] = update.message.text
    await update.message.reply_text("Введите сумму:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data='back')]
    ]))

    return ADDING_BUTTON_AMOUNT

async def handle_button_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
    except:
        await update.message.reply_text("Неверная сумма.")
        return ADDING_BUTTON_AMOUNT
    db = load_data()
    db["expense_buttons"].append({
        "label": temp_button['label'],
        "amount": amount
    })
    save_data(db)
    await update.message.reply_text(f"✅ Добавлена кнопка: {temp_button['label']} {amount}{get_currency()}", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data='back')]
    ]))
    temp_button.clear()
    return ConversationHandler.END

async def handle_custom_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    custom_symbol = update.message.text.strip()
    if len(custom_symbol) > 10:
        await update.message.reply_text("Слишком длинный символ. Введите до 10 символов.")
        return ADDING_CUSTOM_CURRENCY

    db = load_data()
    db["currency"] = custom_symbol
    save_data(db)
    await update.message.reply_text(f"✅ Валюта установлена: {custom_symbol}", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_menu')]
    ]))
    return ConversationHandler.END


# === Запуск ===
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            ADDING_EXPENSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_expense)],
            ADDING_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_income)],
            ADDING_BUTTON_LABEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_label),
                CallbackQueryHandler(handle_back, pattern="^back$")
            ],
            ADDING_BUTTON_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_amount),
                CallbackQueryHandler(handle_back, pattern="^back$")
            ],
            ADDING_CUSTOM_CURRENCY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_currency),
                CallbackQueryHandler(handle_back, pattern="^back$")
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_back, pattern="^back$")
        ]
    )


    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    print("✅ Бот запущен.")
    app.run_polling()

if __name__ == '__main__':
    main()
