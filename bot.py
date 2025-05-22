import telebot
import json
from telebot import types
import re
from datetime import datetime

# Initialize bot
with open('config.json', 'r') as f:
    config = json.load(f)
bot = telebot.TeleBot(config["telegram"]["token"])

# Session states
user_states = {}

# Custom function to escape Markdown characters
def escape_markdown(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(['\\' + char if char in escape_chars else char for char in text])

# Decorators
def authorized(fn):
    def wrapper(message):
        if message.from_user.id in config["telegram"]["allowed_user_ids"]:
            return fn(message)
        bot.reply_to(message, "⛔ Unauthorized")
    return wrapper

def create_keyboard(items, columns=2):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i in range(0, len(items), columns):
        keyboard.row(*items[i:i+columns])
    return keyboard

# Helper function for file operations
def update_config(new_config):
    with open('config.json', 'w') as f:
        json.dump(new_config, f, indent=2)

# Main menu
main_menu = create_keyboard(["📊 Status", "⚙ Settings", "📈 Symbols", "🔧 Trading Settings", "🆘 Help"])

@bot.message_handler(commands=["start", "help"])
@authorized
def send_welcome(message):
    welcome_msg = """
    🤖 *Trading Bot Controller*

    *Main Functions:*
    - 📊 Status: Show current settings
    - ⚙ Settings: Configure bot parameters
    - 📈 Symbols: Manage trading symbols
    - 🔧 Trading Settings: Configure trading parameters
    - 🆘 Help: Show instructions

    Use the buttons below to navigate!
    """
    bot.send_message(message.chat.id, welcome_msg, 
                     parse_mode="Markdown", 
                     reply_markup=main_menu)

@bot.message_handler(func=lambda msg: msg.text == "📊 Status")
@authorized
def show_status(message):
    config = json.load(open('config.json'))
    trading = config["trading"]
    status_msg = f"""⚡ *Bot Status*

*General:*
🤖 Bot: {'✅ Enabled' if config['telegram']['bot_enabled'] else '❌ Disabled'}
🔁 Counter Trade: {'✅ On' if trading['counter_trade_enabled'] else '❌ Off'}
🕯 Min Candle Size: {escape_markdown(str(trading['min_candle_size_points']))} points
📏 M: {escape_markdown(str(trading['M']))}
🕒 Trading Hours: {escape_markdown(str(trading['start_time']))} - {escape_markdown(str(trading['end_time']))}
📊 Trade Mode: {escape_markdown(str(trading['trade_mode']))}

*Symbols ({len(trading['symbols'])}):*
"""
    for sym in trading["symbols"]:
        s = trading.get(sym, {})
        status_msg += f"""
🔸 *{escape_markdown(sym)}*
- Volume: {escape_markdown(str(s.get('volume', trading['volume'])))}
- TP/SL: {escape_markdown(str(s.get('tp', trading['D_tp'])))}.{escape_markdown(str(s.get('sl', trading['D_sl'])))}
- Counter: {escape_markdown(str(s.get('counter', trading['D_counter'])))}
- TP Counter: {escape_markdown(str(s.get('tp_counter', trading['D_tp_counter'])))}
- SL Counter: {escape_markdown(str(s.get('sl_counter', trading['D_sl_counter'])))}
"""
    bot.send_message(message.chat.id, status_msg, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "⚙ Settings")
@authorized
def settings_menu(message):
    config = json.load(open('config.json'))
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            text=f"🤖 Bot: {'✅' if config['telegram']['bot_enabled'] else '❌'}",
            callback_data="toggle_bot"
        ),
        types.InlineKeyboardButton(
            text=f"🔁 Counter: {'✅' if config['trading']['counter_trade_enabled'] else '❌'}",
            callback_data="toggle_counter"
        )
    )
    bot.send_message(message.chat.id, "⚙ *Bot Settings*", 
                     parse_mode="Markdown", 
                     reply_markup=keyboard)

@bot.message_handler(func=lambda msg: msg.text == "📈 Symbols")
@authorized
def symbols_menu(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ Add Symbol", "✏ Edit Symbol")
    keyboard.add("🗑 Remove Symbol", "🏠 Main Menu")
    bot.send_message(message.chat.id, "📈 *Symbol Management*", 
                     parse_mode="Markdown", 
                     reply_markup=keyboard)

# Add symbol flow
@bot.message_handler(func=lambda msg: msg.text == "➕ Add Symbol")
@authorized
def start_add_symbol(message):
    msg = bot.send_message(message.chat.id, "📥 Enter symbol name (e.g., EURUSD):")
    bot.register_next_step_handler(msg, process_symbol_name)

def process_symbol_name(message):
    if not re.match(r'^[A-Z0-9]+$', message.text.upper()):
        bot.send_message(message.chat.id, "❌ Invalid symbol! Use uppercase letters and numbers (e.g., EURUSD)")
        bot.register_next_step_handler(message, process_symbol_name)
        return
    user_states[message.chat.id] = {"action": "add", "symbol": message.text.upper()}
    msg = bot.send_message(message.chat.id, "💹 Enter trade volume:")
    bot.register_next_step_handler(msg, process_symbol_volume)

def process_symbol_volume(message):
    try:
        volume = float(message.text)
        if volume <= 0:
            raise ValueError("Volume must be positive")
        user_states[message.chat.id]["volume"] = volume
        msg = bot.send_message(message.chat.id, "🎯 Enter Take Profit:")
        bot.register_next_step_handler(msg, process_symbol_tp)
    except ValueError as e:
        bot.send_message(message.chat.id, f"❌ Invalid volume: {str(e)}. Please enter a valid number:")
        bot.register_next_step_handler(message, process_symbol_volume)

def process_symbol_tp(message):
    try:
        tp = float(message.text)
        if tp <= 0:
            raise ValueError("Take Profit must be positive")
        user_states[message.chat.id]["tp"] = tp
        msg = bot.send_message(message.chat.id, "🛑 Enter Stop Loss:")
        bot.register_next_step_handler(msg, process_symbol_sl)
    except ValueError as e:
        bot.send_message(message.chat.id, f"❌ Invalid Take Profit: {str(e)}. Please enter a valid number:")
        bot.register_next_step_handler(message, process_symbol_tp)

def process_symbol_sl(message):
    try:
        sl = float(message.text)
        if sl <= 0:
            raise ValueError("Stop Loss must be positive")
        state = user_states[message.chat.id]
        symbol = state["symbol"]
        config = json.load(open('config.json'))
        if symbol in config["trading"]["symbols"]:
            bot.send_message(message.chat.id, "❌ Symbol already exists!", reply_markup=main_menu)
            return
        config["trading"]["symbols"].append(symbol)
        config["trading"][symbol] = {
            "volume": state["volume"],
            "tp": state["tp"],
            "sl": sl,
            "counter": config["trading"]["D_counter"],
            "tp_counter": config["trading"]["D_tp_counter"],
            "sl_counter": config["trading"]["D_sl_counter"]
        }
        update_config(config)
        bot.send_message(message.chat.id, "✅ Symbol added successfully", reply_markup=main_menu)
    except ValueError as e:
        bot.send_message(message.chat.id, f"❌ scrolled Stop Loss: {str(e)}. Please enter a valid number:")
        bot.register_next_step_handler(message, process_symbol_sl)

@bot.message_handler(func=lambda msg: msg.text == "🗑 Remove Symbol")
@authorized
def start_remove_symbol(message):
    config = json.load(open('config.json'))
    if not config["trading"]["symbols"]:
        bot.send_message(message.chat.id, "ℹ No symbols to remove", reply_markup=main_menu)
        return
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for sym in config["trading"]["symbols"]:
        keyboard.add(sym)
    keyboard.add("🏠 Main Menu")
    msg = bot.send_message(message.chat.id, "🗑 Select symbol to remove:", reply_markup=keyboard)
    bot.register_next_step_handler(msg, process_remove_symbol)

def process_remove_symbol(message):
    config = json.load(open('config.json'))
    if message.text == "🏠 Main Menu":
        send_welcome(message)
        return
    if message.text not in config["trading"]["symbols"]:
        bot.send_message(message.chat.id, "❌ Symbol not found!", reply_markup=main_menu)
        return
    symbol = message.text
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("Yes", callback_data=f"remove_{symbol}"),
        types.InlineKeyboardButton("No", callback_data="cancel_remove")
    )
    bot.send_message(message.chat.id, f"Are you sure you want to remove {symbol}?", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_") or call.data == "cancel_remove")
def handle_remove_confirmation(call):
    config = json.load(open('config.json'))
    if call.data == "cancel_remove":
        bot.answer_callback_query(call.id, "Cancelled")
        bot.edit_message_text("Removal cancelled", call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, "📈 *Symbol Management*", parse_mode="Markdown", reply_markup=main_menu)
    else:
        symbol = call.data.split("_")[1]
        if symbol in config["trading"]["symbols"]:
            config["trading"]["symbols"].remove(symbol)
            if symbol in config["trading"]:
                del config["trading"][symbol]
            update_config(config)
            bot.answer_callback_query(call.id, f"{symbol} removed")
            bot.edit_message_text(f"{symbol} has been removed", call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, "Done", reply_markup=main_menu)
        else:
            bot.answer_callback_query(call.id, "Symbol not found")

@bot.message_handler(func=lambda msg: msg.text == "✏ Edit Symbol")
@authorized
def start_edit_symbol(message):
    config = json.load(open('config.json'))
    if not config["trading"]["symbols"]:
        bot.send_message(message.chat.id, "ℹ No symbols available to edit", reply_markup=main_menu)
        return
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for sym in config["trading"]["symbols"]:
        keyboard.add(sym)
    keyboard.add("🏠 Main Menu")
    msg = bot.send_message(message.chat.id, "📝 Select symbol to edit:", reply_markup=keyboard)
    bot.register_next_step_handler(msg, process_edit_symbol)

def process_edit_symbol(message):
    config = json.load(open('config.json'))
    if message.text == "🏠 Main Menu":
        send_welcome(message)
        return
    if message.text not in config["trading"]["symbols"]:
        bot.send_message(message.chat.id, "❌ Symbol not found!", reply_markup=main_menu)
        return
    user_states[message.chat.id] = {"action": "edit", "symbol": message.text}
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Volume", "Take Profit", "Stop Loss")
    keyboard.add("Counter", "TP Counter", "SL Counter")
    keyboard.add("🏠 Main Menu")
    msg = bot.send_message(message.chat.id, f"✏ Editing {message.text}\nSelect parameter:", reply_markup=keyboard)
    bot.register_next_step_handler(msg, process_edit_parameter)

def process_edit_parameter(message):
    valid_params = ["volume", "take profit", "stop loss", "counter", "tp counter", "sl counter"]
    param = message.text.lower()
    if message.text == "🏠 Main Menu":
        send_welcome(message)
        return
    if param not in valid_params:
        bot.send_message(message.chat.id, "❌ Invalid parameter!", reply_markup=main_menu)
        return
    param_map = {
        "volume": "volume",
        "take profit": "tp",
        "stop loss": "sl",
        "counter": "counter",
        "tp counter": "tp_counter",
        "sl counter": "sl_counter"
    }
    user_states[message.chat.id]["param"] = param_map[param]
    msg = bot.send_message(message.chat.id, f"🆕 Enter new value for {message.text}:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, save_parameter_change)

def save_parameter_change(message):
    try:
        value = float(message.text)
        if value <= 0:
            raise ValueError("Value must be positive")
        state = user_states[message.chat.id]
        config = json.load(open('config.json'))
        if state["symbol"] not in config["trading"]:
            config["trading"][state["symbol"]] = {
                "volume": config["trading"]["volume"],
                "tp": config["trading"]["D_tp"],
                "sl": config["trading"]["D_sl"],
                "counter": config["trading"]["D_counter"],
                "tp_counter": config["trading"]["D_tp_counter"],
                "sl_counter": config["trading"]["D_sl_counter"]
            }
        config["trading"][state["symbol"]][state["param"]] = value
        update_config(config)
        bot.send_message(message.chat.id, "✅ Parameter updated successfully", reply_markup=main_menu)
    except ValueError as e:
        bot.send_message(message.chat.id, f"❌ Invalid value: {str(e)}. Please enter a valid number:")
        bot.register_next_step_handler(message, save_parameter_change)

@bot.message_handler(func=lambda msg: msg.text == "🔧 Trading Settings")
@authorized
def trading_settings_menu(message):
    config = json.load(open('config.json'))
    trading = config["trading"]
    settings_msg = f"""🔧 *Trading Settings*

🕯 Min Candle Size: {escape_markdown(str(trading['min_candle_size_points']))} points
📏 M: {escape_markdown(str(trading['M']))}
🕒 Start Time: {escape_markdown(str(trading['start_time']))}
🕒 End Time: {escape_markdown(str(trading['end_time']))}
📊 Trade Mode: {escape_markdown(str(trading['trade_mode']))}
"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🕯 Edit Min Candle Size", callback_data="edit_trading_param_min_candle_size_points")
    )
    keyboard.add(
        types.InlineKeyboardButton("📏 Edit M", callback_data="edit_trading_param_M"),
        types.InlineKeyboardButton("🕒 Edit Start Time", callback_data="edit_trading_param_start_time")
    )
    keyboard.add(
        types.InlineKeyboardButton("🕒 Edit End Time", callback_data="edit_trading_param_end_time"),
        types.InlineKeyboardButton("📊 Edit Trade Mode", callback_data="edit_trading_param_trade_mode")
    )
    bot.send_message(message.chat.id, settings_msg, parse_mode="Markdown", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_trading_param_"))
def start_edit_trading_param(call):
    param = call.data.replace("edit_trading_param_", "", 1)
    prompt = {
        "min_candle_size_points": "🕯 Enter new min candle size (positive integer):",
        "M": "📏 Enter new M value (positive float):",
        "start_time": "🕒 Enter new start time (HH:MM):",
        "end_time": "🕒 Enter new end time (HH:MM):",
        "trade_mode": "📊 Enter new trade mode (both, buy_only, or sell_only):"
    }
    if param not in prompt:
        bot.send_message(call.message.chat.id, "Invalid parameter")
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, prompt[param])
    user_states[call.message.chat.id] = {"action": "edit_trading_param", "param": param}
    bot.register_next_step_handler(msg, process_new_trading_param)

def process_new_trading_param(message):
    state = user_states.get(message.chat.id)
    if not state or state["action"] != "edit_trading_param":
        return
    param = state["param"]
    new_value = message.text
    try:
        if param == "min_candle_size_points":
            new_value = int(new_value)
            if new_value <= 0:
                raise ValueError("Must be a positive integer")
        elif param == "M":
            new_value = float(new_value)
            if new_value <= 0:
                raise ValueError("Must be a positive float")
        elif param in ["start_time", "end_time"]:
            time_obj = datetime.strptime(new_value, "%H:%M")
            new_value = time_obj.strftime("%H:%M")
            config = json.load(open('config.json'))
            if param == "start_time":
                end_time = datetime.strptime(config["trading"]["end_time"], "%H:%M")
                start_time = time_obj
                if start_time >= end_time:
                    raise ValueError("Start time must be before end time")
            elif param == "end_time":
                start_time = datetime.strptime(config["trading"]["start_time"], "%H:%M")
                end_time = time_obj
                if end_time <= start_time:
                    raise ValueError("End time must be after start time")
        elif param == "trade_mode":
            if new_value not in ["both", "buy_only", "sell_only"]:
                raise ValueError("Must be 'both', 'buy_only', or 'sell_only'")
        config = json.load(open('config.json'))
        config["trading"][param] = new_value
        update_config(config)
        bot.send_message(message.chat.id, "✅ Updated successfully", reply_markup=main_menu)
        del user_states[message.chat.id]
    except ValueError as e:
        bot.send_message(message.chat.id, f"❌ {str(e)}")
        bot.register_next_step_handler(message, process_new_trading_param)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}", reply_markup=main_menu)

@bot.callback_query_handler(func=lambda call: call.data in ["toggle_bot", "toggle_counter"])
def handle_callbacks(call):
    config = json.load(open('config.json'))
    if call.data == "toggle_bot":
        config["telegram"]["bot_enabled"] = not config["telegram"]["bot_enabled"]
        update_config(config)
        bot.answer_callback_query(call.id, f"Bot {'enabled' if config['telegram']['bot_enabled'] else 'disabled'}")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=call.message.reply_markup)
    elif call.data == "toggle_counter":
        config["trading"]["counter_trade_enabled"] = not config["trading"]["counter_trade_enabled"]
        update_config(config)
        bot.answer_callback_query(call.id, f"Counter trade {'enabled' if config['trading']['counter_trade_enabled'] else 'disabled'}")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=call.message.reply_markup)

@bot.message_handler(func=lambda msg: True)
@authorized
def handle_unknown(message):
    bot.send_message(message.chat.id, "❓ Unrecognized command. Please use the menu:", reply_markup=main_menu)

print("✅ Bot is running...")
bot.polling(non_stop=True)