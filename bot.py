import telebot
import json
from telebot import types
import re

# Initialize bot
config = json.load(open('config.json'))
bot = telebot.TeleBot(config["telegram"]["token"])

# Session states
user_states = {}

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

# Main menu with new Trading Settings option
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
⏱ Timeframe: {trading['timeframe']}
🕯 Min Candle Size: {trading['min_candle_size_points']} points
📏 M: {trading['M']}
🕒 Trading Hours: {trading['start_time']} - {trading['end_time']}
📊 Trade Mode: {trading['trade_mode']}

*Symbols ({len(trading['symbols'])}):*
"""
    for sym in trading["symbols"]:
        s = trading["settings"][sym]
        status_msg += f"""
🔸 *{sym}*
- Volume: {s['volume']}
- TP/SL: {s['tp']}/{s['sl']}
- Counter: {s['counter']}
- TP Counter: {s['tp_counter']}
- SL Counter: {s['sl_counter']}
"""
    bot.send_message(message.chat.id, status_msg, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "⚙ Settings")
@authorized
def settings_menu(message):
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
    if not message.text.isalpha():
        bot.send_message(message.chat.id, "❌ Invalid symbol! Use only letters (e.g., EURUSD)")
        return
    user_states[message.chat.id] = {"action": "add", "symbol": message.text.upper()}
    msg = bot.send_message(message.chat.id, "💹 Enter trade volume:")
    bot.register_next_step_handler(msg, process_symbol_volume)

def process_symbol_volume(message):
    try:
        volume = float(message.text)
        user_states[message.chat.id]["volume"] = volume
        msg = bot.send_message(message.chat.id, "🎯 Enter Take Profit:")
        bot.register_next_step_handler(msg, process_symbol_tp)
    except:
        bot.send_message(message.chat.id, "❌ Invalid number! Please enter a valid volume:")

def process_symbol_tp(message):
    try:
        tp = float(message.text)
        user_states[message.chat.id]["tp"] = tp
        msg = bot.send_message(message.chat.id, "🛑 Enter Stop Loss:")
        bot.register_next_step_handler(msg, process_symbol_sl)
    except:
        bot.send_message(message.chat.id, "❌ Invalid number! Please enter valid TP:")

def process_symbol_sl(message):
    try:
        sl = float(message.text)
        user_states[message.chat.id]["sl"] = sl
        config = json.load(open('config.json'))
        sym = user_states[message.chat.id]["symbol"]
        
        config["trading"]["symbols"].append(sym)
        config["trading"]["settings"][sym] = {
            "volume": user_states[message.chat.id]["volume"],
            "tp": user_states[message.chat.id]["tp"],
            "sl": sl,
            "counter": 5.0,
            "tp_counter": 0.01,
            "sl_counter": 600.0
        }
        
        json.dump(config, open('config.json', 'w'), indent=2)
        bot.send_message(message.chat.id, "Done", reply_markup=main_menu)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "🗑 Remove Symbol")
@authorized
def start_remove_symbol(message):
    with open('config.json', 'r') as f:
        config = json.load(f)
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
    with open('config.json', 'r') as f:
        config = json.load(f)
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
    with open('config.json', 'r') as f:
        config = json.load(f)
    if call.data == "cancel_remove":
        bot.answer_callback_query(call.id, "Cancelled")
        bot.edit_message_text("Removal cancelled", call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, "📈 *Symbol Management*", parse_mode="Markdown", reply_markup=main_menu)
    else:
        symbol = call.data.split("_")[1]
        if symbol in config["trading"]["symbols"]:
            config["trading"]["symbols"].remove(symbol)
            del config["trading"]["settings"][symbol]
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            bot.answer_callback_query(call.id, f"{symbol} removed")
            bot.edit_message_text(f"{symbol} has been removed", call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, "Done", reply_markup=main_menu)
        else:
            bot.answer_callback_query(call.id, "Symbol not found")

# Edit symbol flow
@bot.message_handler(func=lambda msg: msg.text == "✏ Edit Symbol")
@authorized
def start_edit_symbol(message):
    config = json.load(open('config.json'))
    if not config["trading"]["symbols"]:
        bot.send_message(message.chat.id, "ℹ No symbols available to edit")
        return
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for sym in config["trading"]["symbols"]:
        keyboard.add(sym)
    keyboard.add("🏠 Main Menu")
    
    msg = bot.send_message(message.chat.id, "📝 Select symbol to edit:", 
                         reply_markup=keyboard)
    bot.register_next_step_handler(msg, process_edit_symbol)

def process_edit_symbol(message):
    config = json.load(open('config.json'))
    if message.text not in config["trading"]["symbols"]:
        bot.send_message(message.chat.id, "❌ Symbol not found!")
        return
    
    user_states[message.chat.id] = {"action": "edit", "symbol": message.text}
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Volume", "Take Profit", "Stop Loss")
    keyboard.add("Counter", "TP Counter", "SL Counter")
    keyboard.add("🏠 Main Menu")
    
    msg = bot.send_message(message.chat.id, f"✏ Editing {message.text}\nSelect parameter:",
                         reply_markup=keyboard)
    bot.register_next_step_handler(msg, process_edit_parameter)

def process_edit_parameter(message):
    valid_params = ["volume", "take profit", "stop loss", "counter", "tp counter", "sl counter"]
    param = message.text.lower()
    
    if param not in valid_params:
        bot.send_message(message.chat.id, "❌ Invalid parameter!")
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
    msg = bot.send_message(message.chat.id, f"🆕 Enter new value for {message.text}:",
                         reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, save_parameter_change)

def save_parameter_change(message):
    try:
        config = json.load(open('config.json'))
        state = user_states[message.chat.id]
        value = float(message.text)
        
        config["trading"]["settings"][state["symbol"]][state["param"]] = value
        json.dump(config, open('config.json', 'w'), indent=2)
        
        bot.send_message(message.chat.id, "Done", reply_markup=main_menu)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

# New Trading Settings handlers
@bot.message_handler(func=lambda msg: msg.text == "🔧 Trading Settings")
@authorized
def trading_settings_menu(message):
    config = json.load(open('config.json'))
    trading = config["trading"]
    settings_msg = f"""🔧 *Trading Settings*

⏱ Timeframe: {trading['timeframe']}
🕯 Min Candle Size: {trading['min_candle_size_points']} points
📏 M: {trading['M']}
🕒 Start Time: {trading['start_time']}
🕒 End Time: {trading['end_time']}
📊 Trade Mode: {trading['trade_mode']}
"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("⏱ Edit Timeframe", callback_data="edit_trading_param_timeframe"),
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
    # Extract the full parameter name by removing the prefix
    param = call.data.replace("edit_trading_param_", "", 1)
    
    # Define the prompt dictionary
    prompt = {
        "timeframe": "⏱ Enter new timeframe (e.g., M1, M5, H1):",
        "min_candle_size_points": "🕯 Enter new min candle size (positive integer):",
        "M": "📏 Enter new M value (positive float):",
        "start_time": "🕒 Enter new start time (HH:MM):",
        "end_time": "🕒 Enter new end time (HH:MM):",
        "trade_mode": "📊 Enter new trade mode (both, buy_only, or sell_only):"
    }
    

    
    # Check if the parameter is valid to prevent KeyError
    if param not in prompt:
        bot.send_message(call.message.chat.id, "Invalid parameter")
        return
    
    # Proceed with sending the prompt
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
        if param == "timeframe":
            if not re.match(r'^[A-Z]\d+$', new_value):
                raise ValueError("Invalid timeframe format! Use e.g., M1, M5, H1")
        elif param == "min_candle_size_points":
            new_value = int(new_value)
            if new_value <= 0:
                raise ValueError("Must be a positive integer")
        elif param == "M":
            new_value = float(new_value)
            if new_value <= 0:
                raise ValueError("Must be a positive float")
        elif param in ["start_time", "end_time"]:
            if not re.match(r'^\d{2}:\d{2}$', new_value):
                raise ValueError("Invalid time format! Use HH:MM")
        elif param == "trade_mode":
            if new_value not in ["both", "buy_only", "sell_only"]:
                raise ValueError("Must be 'both', 'buy_only', or 'sell_only'")
        
        config = json.load(open('config.json'))
        config["trading"][param] = new_value
        json.dump(config, open('config.json', 'w'), indent=2)
        bot.send_message(message.chat.id, "✅ Updated successfully", reply_markup=main_menu)
        del user_states[message.chat.id]
    except ValueError as e:
        bot.send_message(message.chat.id, f"❌ {str(e)}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

# Existing callback handlers
@bot.callback_query_handler(func=lambda call: call.data in ["toggle_bot", "toggle_counter"])
def handle_callbacks(call):
    config = json.load(open('config.json'))
    if call.data == "toggle_bot":
        config["telegram"]["bot_enabled"] = not config["telegram"]["bot_enabled"]
        json.dump(config, open('config.json', 'w'), indent=2)
        bot.answer_callback_query(call.id, f"Bot {'enabled' if config['telegram']['bot_enabled'] else 'disabled'}")
    elif call.data == "toggle_counter":
        config["trading"]["counter_trade_enabled"] = not config["trading"]["counter_trade_enabled"]
        json.dump(config, open('config.json', 'w'), indent=2)
        bot.answer_callback_query(call.id, f"Counter trade {'enabled' if config['trading']['counter_trade_enabled'] else 'disabled'}")

print("✅ Bot is running...")
bot.polling()