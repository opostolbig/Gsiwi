import telebot
from telebot import types
import random
import json
import os
import uuid
import logging
import threading
import time
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Вставьте здесь ваш токен бота
TOKEN = '7795536845:AAGvBiDeTm2UHNpe-SI_QXz0NrdXBb2QB5o'  # **Важно:** Замените на ваш реальный токен и не публикуйте его публично

bot = telebot.TeleBot(TOKEN)

# Файлы для хранения данных
BALANCES_FILE = 'user_balances.json'
GAMES_FILE = 'games.json'
TRANSFERS_FILE = 'transfers.json'
BANK_FILE = 'bank.json'

# Константы игры
INITIAL_BALANCE = 1000
GRID_ROWS = 4
GRID_COLS = 5
TOTAL_MINES = 5
MULTIPLIER = 1.3
COMPENSATION_BALANCE = 109  # Баланс-компенсация при полной потере

# Загрузка данных из JSON-файлов
def load_data(file_path):
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

# Сохранение данных в JSON-файл
def save_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Инициализация данных
user_balances = load_data(BALANCES_FILE)
games = load_data(GAMES_FILE)
transfers = load_data(TRANSFERS_FILE)
bank_data = load_data(BANK_FILE)

# Сохранение данных при изменении
def update_balances(user_id, balance, username=None):
    if str(user_id) not in user_balances:
        user_balances[str(user_id)] = {"balance": balance, "username": username or "Неизвестный"}
    else:
        user_balances[str(user_id)]["balance"] = balance
    save_data(BALANCES_FILE, user_balances)

def update_game(user_id, game_data):
    games[str(user_id)] = game_data
    save_data(GAMES_FILE, games)

def delete_game(user_id):
    if str(user_id) in games:
        del games[str(user_id)]
        save_data(GAMES_FILE, games)

def create_transfer(transfer_id, sender_id, recipient_id, amount):
    transfers[transfer_id] = {
        "sender_id": sender_id,
        "recipient_id": recipient_id,
        "amount": amount
    }
    save_data(TRANSFERS_FILE, transfers)

def delete_transfer(transfer_id):
    if transfer_id in transfers:
        del transfers[transfer_id]
        save_data(TRANSFERS_FILE, transfers)

def update_bank(user_id, bank_info):
    bank_data[str(user_id)] = bank_info
    save_data(BANK_FILE, bank_data)

def delete_bank(user_id):
    if str(user_id) in bank_data:
        del bank_data[str(user_id)]
        save_data(BANK_FILE, bank_data)

# 1. Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_game(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name

    # Инициализируем баланс пользователя, если он не существует
    if str(user_id) not in user_balances:
        user_balances[str(user_id)] = {"balance": INITIAL_BALANCE, "username": username}
        save_data(BALANCES_FILE, user_balances)

    welcome_message = (
        f"👋 Добро пожаловать, <a href='tg://user?id={user_id}'>{username}</a>!\n\n"
        f"Этот бот создан, чтобы ты мог отдохнуть и насладиться классической головоломкой. "
        f"Не беспокойся о поражениях! Если ты проиграешь, мы предоставим тебе компенсацию, "
        f"чтобы ты мог играть столько, сколько захочешь. Наслаждайся процессом! ❤️\n\n"
        f"ℹ️ Нажми кнопку \"Информация\", чтобы узнать обо всех механиках бота и правилах игры."
    )

    # Создаем инлайн-кнопки "Информация" и "Топ"
    main_markup = types.InlineKeyboardMarkup()
    info_button = types.InlineKeyboardButton(text="Информация", callback_data="show_info")
    top_button = types.InlineKeyboardButton(text="Топ", callback_data="show_top")
    main_markup.add(info_button, top_button)

    bot.send_message(chat_id, welcome_message, parse_mode='HTML', reply_markup=main_markup)

# 2. Обработчик инлайн-кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id

    if call.data == "show_info":
        mechanics_message = (
            "🔍 <b>Механики бота:</b>\n\n"
            "• <b>мины {сумма}</b> — начать игру с указанной суммой.\n"
            "• <b>/передать {айди человека} {сумма}</b> — передать деньги другому пользователю. "
            "Вы не сможете ему передать, если он не писал в чате или не отправил /start.\n"
            "• <b>/банк {сумма}</b> — положить деньги на депозит.\n"
            "• <b>/банк баланс</b> — посмотреть баланс в банке.\n"
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=mechanics_message,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)

    elif call.data == "show_top":
        top_users = sorted(user_balances.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        top_message = "🏆 <b>Топ 10 человек по балансу:</b>\n\n"
        if not top_users:
            top_message += "Топ пока пуст."
        else:
            for idx, (uid, info) in enumerate(top_users, start=1):
                username = info["username"]
                balance = info["balance"]
                top_message += f"{idx}. <a href='tg://user?id={uid}'>{username}</a> — <b>{balance}</b> 💰\n"

        # Создаем инлайн-кнопку "<< Назад"
        back_markup = types.InlineKeyboardMarkup()
        back_button = types.InlineKeyboardButton(text="<< Назад", callback_data="back_to_main")
        back_markup.add(back_button)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=top_message,
            parse_mode='HTML',
            reply_markup=back_markup
        )
        bot.answer_callback_query(call.id)

    elif call.data == "back_to_main":
        # Возвращаемся к основному меню
        username = user_balances.get(str(user_id), {}).get("username", "Неизвестный")
        welcome_message = (
            f"👋 Добро пожаловать, <a href='tg://user?id={user_id}'>{username}</a>!\n\n"
            f"Этот бот создан, чтобы ты мог отдохнуть и насладиться классической головоломкой. "
            f"Не беспокойся о поражениях! Если ты проиграешь, мы предоставим тебе компенсацию, "
            f"чтобы ты мог играть столько, сколько захочешь. Наслаждайся процессом! ❤️\n\n"
            f"ℹ️ Нажми кнопку \"Информация\", чтобы узнать обо всех механиках бота и правилах игры."
        )

        # Создаем инлайн-кнопки "Информация" и "Топ"
        main_markup = types.InlineKeyboardMarkup()
        info_button = types.InlineKeyboardButton(text="Информация", callback_data="show_info")
        top_button = types.InlineKeyboardButton(text="Топ", callback_data="show_top")
        main_markup.add(info_button, top_button)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=welcome_message,
            parse_mode='HTML',
            reply_markup=main_markup
        )
        bot.answer_callback_query(call.id)

    elif call.data.startswith("cell:"):
        handle_cell_click(call)

    elif call.data == "collect":
        handle_collect(call)

    elif call.data.startswith("transfer_confirm:"):
        handle_transfer_confirm(call)

    elif call.data == "terminate_game":
        handle_terminate_game(call)

    elif call.data == "retry":
        handle_retry(call)

    elif call.data == "withdraw_bank":
        handle_withdraw_bank(call)

    else:
        bot.answer_callback_query(call.id, "❌ Неизвестная команда.", show_alert=True)

# 3. Обработчик команды игры "Мины"
@bot.message_handler(regexp=r"^мины (\d+)$")
def mines_game(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        bet = int(message.text.split()[1])  # Извлечение ставки из текста сообщения
    except (IndexError, ValueError):
        bot.send_message(chat_id, "❌ Неверный формат команды. Используйте: 'мины <сумма>'.")
        return

    # Проверяем, что ставка положительная
    if bet <= 0:
        bot.send_message(chat_id, "❌ Ставка должна быть положительным числом.")
        return

    # Проверяем, достаточно ли средств на балансе для ставки
    current_balance = user_balances.get(str(user_id), {}).get("balance", INITIAL_BALANCE)
    if bet > current_balance:
        bot.send_message(chat_id, f"❌ Недостаточно средств для ставки. Ваш текущий баланс: {current_balance}")
        return

    # Проверка, не участвует ли пользователь уже в игре
    if str(user_id) in games:
        # Создание инлайн-кнопки "❌ Завершить"
        terminate_markup = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton(text="❌ Завершить", callback_data="terminate_game")
        )
        bot.send_message(chat_id, "❌ Вы уже участвуете в игре. Завершите текущую игру перед началом новой.", reply_markup=terminate_markup)
        return

    bombs_indexes = random.sample(range(GRID_ROWS * GRID_COLS), TOTAL_MINES)  # Выбор случайных позиций для бомб

    # Сохранение состояния игры
    games[str(user_id)] = {
        "bet": bet,
        "bombs": bombs_indexes,
        "revealed": [False] * (GRID_ROWS * GRID_COLS),
        "game_message_id": None,
        "chat_id": chat_id
    }
    save_data(GAMES_FILE, games)

    # Создание кнопок
    markup = generate_markup(user_id)

    game_message = (
        f"🎮 <b>Игра начата!</b>\n\n"
        f"💰 <b>Ставка:</b> {bet}\n"
        f"💵 <b>Баланс:</b> {current_balance}\n"
        f"💣 <b>Мины:</b> {TOTAL_MINES}\n"
        f"💎 <b>Найдите алмазы, чтобы увеличить ставку!</b>"
    )
    sent_message = bot.send_message(
        chat_id,
        text=game_message,
        parse_mode='HTML',
        reply_markup=markup
    )
    games[str(user_id)]["game_message_id"] = sent_message.message_id
    save_data(GAMES_FILE, games)

# 4. Функция генерации инлайн-кнопок для игры
def generate_markup(user_id):
    markup = types.InlineKeyboardMarkup()
    game = games[str(user_id)]
    for i in range(GRID_ROWS):
        row = []
        for j in range(GRID_COLS):
            index = i * GRID_COLS + j
            if not game["revealed"][index]:
                button_text = '?'
            else:
                if index in game["bombs"]:
                    button_text = '💣'
                else:
                    button_text = '💎'
            # Используем префикс 'cell:' для идентификации кнопок ячеек
            callback_data = f"cell:{index}"
            row.append(types.InlineKeyboardButton(text=button_text, callback_data=callback_data))
        markup.add(*row)
    # Добавление кнопки "Забрать выигрыш"
    markup.add(types.InlineKeyboardButton(text="🏆 Забрать выигрыш", callback_data="collect"))
    return markup

# 5. Обработка нажатия на ячейку
def handle_cell_click(call):
    user_id = call.from_user.id
    if str(user_id) not in games:
        bot.answer_callback_query(call.id, "❌ У вас нет активной игры.", show_alert=True)
        return

    game = games[str(user_id)]
    data = call.data

    try:
        index = int(data.split(":")[1])
    except (IndexError, ValueError):
        bot.answer_callback_query(call.id, "❌ Неверное действие.", show_alert=True)
        return

    if game["revealed"][index]:
        bot.answer_callback_query(call.id, "❌ Эта ячейка уже раскрыта.", show_alert=True)
        return

    game["revealed"][index] = True
    update_game(user_id, game)  # Сохранение состояния игры

    if index in game["bombs"]:
        # Пользователь попал на мину
        bet = game["bet"]
        current_balance = user_balances.get(str(user_id), {}).get("balance", INITIAL_BALANCE)

        # Проверяем, станет ли баланс пользователя <= 0 после проигрыша
        if current_balance - bet <= 0:
            new_balance = COMPENSATION_BALANCE
        else:
            new_balance = current_balance - bet

        user_balances[str(user_id)]["balance"] = new_balance
        update_balances(user_id, new_balance)

        losing_message = (
            f"💥 <b>Вы попали на мину!</b>\n\n"
            f"💰 <b>Вы потеряли ставку:</b> {bet}\n"
            f"💵 <b>Ваш баланс после проигрыша:</b> {new_balance}\n"
        )

        if current_balance - bet <= 0:
            losing_message += (
                f"⚠️ Ваш баланс был полностью потерян. В качестве компенсации вы получили {COMPENSATION_BALANCE}.\n"
                f"Попробуйте снова! 🚀"
            )
        else:
            losing_message += "Попробуйте снова! 🚀"

        # Создание кнопки "Играть снова"
        retry_markup = types.InlineKeyboardMarkup()
        retry_markup.add(types.InlineKeyboardButton(text="🎮 Играть снова", callback_data="retry"))

        bot.edit_message_text(
            text=losing_message,
            chat_id=game["chat_id"],
            message_id=game["game_message_id"],
            parse_mode='HTML',
            reply_markup=retry_markup
        )
        delete_game(user_id)
    else:
        # Пользователь нашел алмаз
        game["bet"] = round(game["bet"] * MULTIPLIER)
        update_game(user_id, game)  # Сохранение состояния игры

        remaining_revealed = sum(game["revealed"])
        # Осталось безопасных ячеек
        remaining_safe_cells = (GRID_ROWS * GRID_COLS) - TOTAL_MINES - (
            remaining_revealed - len([b for b in game["bombs"] if game["revealed"][b]])
        )

        if remaining_safe_cells <= 0:
            # Автоматическое завершение игры, если осталось мало безопасных ячеек
            bet = game["bet"]
            current_balance = user_balances.get(str(user_id), {}).get("balance", INITIAL_BALANCE)
            new_balance = current_balance + bet
            user_balances[str(user_id)]["balance"] = new_balance
            update_balances(user_id, new_balance)

            success_message = (
                f"🎉 <b>Вы успешно завершили игру!</b>\n\n"
                f"💰 <b>Ваш выигрыш:</b> {bet}\n"
                f"💵 <b>Текущий баланс:</b> {new_balance}\n"
                f"Спасибо за игру! 🚀"
            )

            # Создание кнопки "Играть снова"
            retry_markup = types.InlineKeyboardMarkup()
            retry_markup.add(types.InlineKeyboardButton(text="🎮 Играть снова", callback_data="retry"))

            bot.edit_message_text(
                text=success_message,
                chat_id=game["chat_id"],
                message_id=game["game_message_id"],
                parse_mode='HTML',
                reply_markup=retry_markup
            )
            delete_game(user_id)
        else:
            # Продолжаем игру
            markup = generate_markup(user_id)
            current_balance = user_balances.get(str(user_id), {}).get("balance", INITIAL_BALANCE)
            continued_message = (
                f"🎮 <b>Игра продолжается!</b>\n\n"
                f"💎 <b>Вы нашли алмаз!</b>\n"
                f"💰 <b>Ваша ставка увеличена на {MULTIPLIER}x:</b> {game['bet']}\n"
                f"💵 <b>Текущий баланс:</b> {current_balance}\n"
                f"Играйте дальше или заберите выигрыш. 🏆"
            )
            bot.edit_message_text(
                text=continued_message,
                chat_id=game["chat_id"],
                message_id=game["game_message_id"],
                parse_mode='HTML',
                reply_markup=markup
            )

# 6. Обработка забора выигрыша
def handle_collect(call):
    user_id = call.from_user.id
    if str(user_id) not in games:
        bot.answer_callback_query(call.id, "❌ У вас нет активной игры.", show_alert=True)
        return

    game = games[str(user_id)]
    bet = game["bet"]
    current_balance = user_balances.get(str(user_id), {}).get("balance", INITIAL_BALANCE)
    new_balance = current_balance + bet  # Увеличиваем баланс на сумму ставки
    user_balances[str(user_id)]["balance"] = new_balance
    update_balances(user_id, new_balance)

    success_message = (
        f"🎉 <b>Игра завершена!</b>\n\n"
        f"💰 <b>Ваш выигрыш:</b> {bet}\n"
        f"💵 <b>Текущий баланс:</b> {new_balance}\n"
        f"Спасибо за игру! 🚀"
    )

    # Создание кнопки "Играть снова"
    retry_markup = types.InlineKeyboardMarkup()
    retry_markup.add(types.InlineKeyboardButton(text="🎮 Играть снова", callback_data="retry"))

    bot.edit_message_text(
        text=success_message,
        chat_id=game["chat_id"],
        message_id=game["game_message_id"],
        parse_mode='HTML',
        reply_markup=retry_markup
    )
    delete_game(user_id)
    bot.answer_callback_query(call.id)  # Скрытие "часиков"

# 7. Обработчик подтверждения или отмены передачи денег
def handle_transfer_confirm(call):
    # Формат: transfer_confirm:{transfer_id}:{action}
    try:
        _, transfer_id, action = call.data.split(":")
    except ValueError:
        bot.answer_callback_query(call.id, "❌ Неверное действие.", show_alert=True)
        return

    if transfer_id not in transfers:
        bot.answer_callback_query(call.id, "❌ Трансфер не найден или уже обработан.", show_alert=True)
        return

    transfer = transfers[transfer_id]
    sender_id = transfer["sender_id"]
    recipient_id = transfer["recipient_id"]
    amount = transfer["amount"]

    if action == "transfer":
        # Проверяем, что отправитель все еще имеет достаточный баланс
        sender_balance = user_balances.get(str(sender_id), {}).get("balance", INITIAL_BALANCE)
        if amount > sender_balance:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств для передачи.", show_alert=True)
            delete_transfer(transfer_id)
            return

        # Списываем средства с отправителя и зачисляем получателю
        user_balances[str(sender_id)]["balance"] = sender_balance - amount
        user_balances[str(recipient_id)]["balance"] = user_balances.get(str(recipient_id), {}).get("balance", 0) + amount
        update_balances(sender_id, user_balances[str(sender_id)]["balance"])
        update_balances(recipient_id, user_balances[str(recipient_id)]["balance"])

        # Создание инлайн-кнопки с ссылкой на отправителя
        sender_link_markup = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton(
                text="🔗 Перейти к отправителю",
                url=f"tg://user?id={sender_id}"
            )
        )

        # Отправляем уведомление получателю с кнопкой
        try:
            bot.send_message(
                recipient_id,
                f"✅ Вы получили {amount} от пользователя с ID {sender_id}.",
                reply_markup=sender_link_markup
            )
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"Не удалось отправить сообщение получателю: {e}")
            bot.answer_callback_query(call.id, "❌ Не удалось уведомить получателя о передаче.", show_alert=True)
            return

        # Отправляем уведомление отправителю
        try:
            bot.send_message(sender_id, f"✅ Вы успешно передали {amount} пользователю с ID {recipient_id}.")
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"Не удалось отправить сообщение отправителю: {e}")

        # Отправляем обновлённое сообщение подтверждения в чат отправителя
        bot.edit_message_text(
            text=(
                f"✅ <b>Передача успешно выполнена!</b>\n\n"
                f"💰 <b>Сумма:</b> {amount}\n"
                f"👤 <b>Отправитель ID:</b> {sender_id}\n"
                f"👥 <b>Получатель ID:</b> {recipient_id}\n"
            ),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )
        # Удаляем запись о трансфере
        delete_transfer(transfer_id)
    elif action == "cancel":
        # Отменяем передачу
        bot.edit_message_text(
            text=(
                f"❌ <b>Передача отменена.</b>\n\n"
                f"💰 <b>Сумма:</b> {amount}\n"
                f"👤 <b>Отправитель ID:</b> {sender_id}\n"
                f"👥 <b>Получатель ID:</b> {recipient_id}\n"
            ),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )
        try:
            bot.send_message(sender_id, f"❌ Вы отменили передачу {amount} пользователю с ID {recipient_id}.")
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"Не удалось отправить сообщение отправителю об отмене: {e}")

        # Сбрасываем текущую игру пользователя, если она активна
        if str(sender_id) in games:
            delete_game(sender_id)
            bot.send_message(sender_id, "✅ Ваша текущая игра была завершена.")
        
        # Удаляем запись о трансфере
        delete_transfer(transfer_id)
    else:
        bot.answer_callback_query(call.id, "❌ Неверное действие.", show_alert=True)
        return

    bot.answer_callback_query(call.id)  # Скрытие "часиков"

# 8. Обработчик кнопки "❌ Завершить"
def handle_terminate_game(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if str(user_id) in games:
        delete_game(user_id)
        bot.edit_message_text(
            text="✅ Ваша игра была завершена.",
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id, "Ваша игра была завершена.", show_alert=True)
    else:
        bot.send_message(chat_id, "❌ У вас нет активных игр.")
        bot.answer_callback_query(call.id)  # Скрытие "часиков"

# 9. Обработчик кнопки "Играть снова"
def handle_retry(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    # Инициализируем новую игру
    if str(user_id) in games:
        bot.answer_callback_query(call.id, "❌ Вы уже участвуете в игре.", show_alert=True)
        return

    # Получаем текущий баланс
    current_balance = user_balances.get(str(user_id), {}).get("balance", INITIAL_BALANCE)

    if current_balance <= 0:
        # Если баланс равен или меньше 0, устанавливаем компенсационный баланс
        user_balances[str(user_id)]["balance"] = COMPENSATION_BALANCE
        update_balances(user_id, COMPENSATION_BALANCE, user_balances[str(user_id)].get("username"))
        bot.send_message(chat_id, f"⚠️ Ваш баланс был восстановлен до {COMPENSATION_BALANCE} в качестве компенсации.")
        return

    # Устанавливаем ставку как весь текущий баланс
    bet = current_balance

    # Проверяем, достаточно ли средств на балансе для ставки
    if bet > current_balance:
        bot.send_message(chat_id, f"❌ Недостаточно средств для ставки. Ваш текущий баланс: {current_balance}")
        return

    bombs_indexes = random.sample(range(GRID_ROWS * GRID_COLS), TOTAL_MINES)  # Выбор случайных позиций для бомб

    # Сохранение состояния игры
    games[str(user_id)] = {
        "bet": bet,
        "bombs": bombs_indexes,
        "revealed": [False] * (GRID_ROWS * GRID_COLS),
        "game_message_id": call.message.message_id,
        "chat_id": chat_id
    }
    save_data(GAMES_FILE, games)

    # Создание кнопок
    markup = generate_markup(user_id)

    new_game_message = (
        f"🎮 <b>Новая игра начата!</b>\n\n"
        f"💰 <b>Ставка:</b> {bet}\n"
        f"💵 <b>Баланс:</b> {current_balance}\n"
        f"💣 <b>Мины:</b> {TOTAL_MINES}\n"
        f"💎 <b>Найдите алмазы, чтобы увеличить ставку!</b>"
    )

    bot.edit_message_text(
        text=new_game_message,
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)  # Скрытие "часиков"

# 10. Обработчик команды передачи денег /передать
@bot.message_handler(commands=['передать'])
def transfer_money(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    parts = message.text.split()

    if len(parts) != 3:
        bot.send_message(chat_id, "❌ Неверный формат команды. Используйте: '/передать {айди} {сумма}'.")
        return

    _, recipient_id_str, amount_str = parts

    try:
        recipient_id = int(recipient_id_str)
        amount = int(amount_str)
    except ValueError:
        bot.send_message(chat_id, "❌ Айди и сумма должны быть числами.")
        return

    if recipient_id == user_id:
        bot.send_message(chat_id, "❌ Вы не можете передать деньги самому себе.")
        return

    if amount <= 0:
        bot.send_message(chat_id, "❌ Сумма должна быть положительным числом.")
        return

    sender_balance = user_balances.get(str(user_id), {}).get("balance", INITIAL_BALANCE)
    if amount > sender_balance:
        bot.send_message(chat_id, f"❌ Недостаточно средств для передачи. Ваш текущий баланс: {sender_balance}")
        return

    # Проверяем, существует ли получатель и начал ли он взаимодействие с ботом
    if str(recipient_id) not in user_balances:
        bot.send_message(chat_id, "❌ Получатель не зарегистрирован или не начал взаимодействие с ботом. Попросите его отправить /start.")
        return

    # Создаем уникальный ID для передачи
    transfer_id = str(uuid.uuid4())

    # Сохраняем передачу
    create_transfer(transfer_id, user_id, recipient_id, amount)

    # Отправляем подтверждающее сообщение
    confirmation_message = (
        f"📤 <b>Подтверждение передачи:</b>\n\n"
        f"💰 <b>Сумма:</b> {amount}\n"
        f"👤 <b>Отправитель ID:</b> {user_id}\n"
        f"👥 <b>Получатель ID:</b> {recipient_id}\n\n"
        f"Вы уверены, что хотите передать эти деньги?"
    )

    # Создаем инлайн-кнопки "✅ Передать" и "❌ Отменить"
    confirm_markup = types.InlineKeyboardMarkup()
    confirm_markup.row(
        types.InlineKeyboardButton(text="✅ Передать", callback_data=f"transfer_confirm:{transfer_id}:transfer"),
        types.InlineKeyboardButton(text="❌ Отменить", callback_data=f"transfer_confirm:{transfer_id}:cancel")
    )

    bot.send_message(chat_id, confirmation_message, parse_mode='HTML', reply_markup=confirm_markup)

# 11. Команды банка
@bot.message_handler(commands=['банк'])
def bank_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    parts = message.text.split()

    if len(parts) == 1:
        bot.send_message(chat_id, "❌ Неверный формат команды. Используйте '/банк {сумма}' или '/банк баланс'.")
        return

    if parts[1].lower() == "баланс":
        handle_bank_balance(message)
    else:
        # Попытка положить деньги в банк
        try:
            amount = int(parts[1])
        except ValueError:
            bot.send_message(chat_id, "❌ Сумма должна быть числом.")
            return

        if amount <= 0:
            bot.send_message(chat_id, "❌ Сумма должна быть положительным числом.")
            return

        current_balance = user_balances.get(str(user_id), {}).get("balance", INITIAL_BALANCE)
        if amount > current_balance:
            bot.send_message(chat_id, f"❌ Недостаточно средств для депозита. Ваш текущий баланс: {current_balance}")
            return

        # Списание средств с баланса пользователя
        user_balances[str(user_id)]["balance"] = current_balance - amount
        update_balances(user_id, user_balances[str(user_id)]["balance"], user_balances[str(user_id)].get("username"))

        # Добавление средств в банк
        if str(user_id) not in bank_data:
            bank_data[str(user_id)] = {
                "balance": amount,
                "deposit_time": datetime.utcnow().isoformat()
            }
        else:
            bank_data[str(user_id)]["balance"] += amount
        update_bank(user_id, bank_data[str(user_id)])

        bot.send_message(chat_id, f"💎 Вы успешно положили {amount} в банк.\n\n"
                                  f"• Каждые час вся сумма в банке умножается на 1.3x.\n"
                                  f"• Напишите '/банк баланс', чтобы узнать баланс в банке.")

        # Запуск таймера для умножения суммы через час
        threading.Thread(target=bank_multiplier, args=(user_id,)).start()

def handle_bank_balance(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if str(user_id) not in bank_data:
        bot.send_message(chat_id, "💰 У вас нет средств в банке.")
        return

    bank_info = bank_data[str(user_id)]
    balance = bank_info["balance"]
    deposit_time = datetime.fromisoformat(bank_info["deposit_time"])
    elapsed_time = datetime.utcnow() - deposit_time
    next_multiplier = deposit_time + timedelta(hours=1)

    # Рассчитываем время до следующего умножения
    time_remaining = next_multiplier - datetime.utcnow()
    if time_remaining.total_seconds() < 0:
        time_remaining = timedelta(seconds=0)

    time_remaining_str = str(time_remaining).split(".")[0]  # Форматирование времени

    balance_message = (
        f"💰 <b>Сумма в банке:</b> {balance}\n"
        f"⏳ <b>Умножиться через:</b> {time_remaining_str}\n"
        f"🕒 <b>Времени в банке:</b> {int(elapsed_time.total_seconds() // 3600)} часов\n"
    )

    # Создание инлайн-кнопки "Снять"
    withdraw_markup = types.InlineKeyboardMarkup()
    withdraw_button = types.InlineKeyboardButton(text="💸 Снять", callback_data="withdraw_bank")
    withdraw_markup.add(withdraw_button)

    bot.send_message(chat_id, balance_message, parse_mode='HTML', reply_markup=withdraw_markup)

def handle_withdraw_bank(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if str(user_id) not in bank_data:
        bot.answer_callback_query(call.id, "❌ У вас нет средств в банке.", show_alert=True)
        return

    bank_info = bank_data[str(user_id)]
    balance = bank_info["balance"]

    if balance <= 0:
        bot.answer_callback_query(call.id, "❌ У вас нет средств в банке.", show_alert=True)
        return

    # Добавление средств обратно на баланс пользователя
    current_balance = user_balances.get(str(user_id), {}).get("balance", INITIAL_BALANCE)
    user_balances[str(user_id)]["balance"] = current_balance + balance
    update_balances(user_id, user_balances[str(user_id)]["balance"], user_balances[str(user_id)].get("username"))

    # Очистка данных банка
    delete_bank(user_id)

    bot.edit_message_text(
        text=f"💸 Вы сняли {balance} с банка.",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id, "✅ Вы успешно сняли средства с банка.", show_alert=True)

# 12. Функция умножения суммы в банке на 1.3x через час
def bank_multiplier(user_id):
    time.sleep(3600)  # Ждем час
    if str(user_id) not in bank_data:
        return

    bank_info = bank_data[str(user_id)]
    bank_info["balance"] = round(bank_info["balance"] * MULTIPLIER)
    bank_info["deposit_time"] = datetime.utcnow().isoformat()
    update_bank(user_id, bank_info)

    try:
        bot.send_message(user_id, f"💰 Ваш депозит в банке был умножен на {MULTIPLIER}x и составляет теперь {bank_info['balance']}!")
        # Рекурсивный вызов для следующего умножения
        threading.Thread(target=bank_multiplier, args=(user_id,)).start()
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

# 13. Обработка неизвестных команд
@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def handle_unknown(message):
    bot.send_message(message.chat.id, "❓ Я не понимаю эту команду. Напишите /start, чтобы начать игру.")

# 14. Запуск бота
if __name__ == "__main__":
    try:
        logger.info("Бот запущен...")
        bot.polling(non_stop=True)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
