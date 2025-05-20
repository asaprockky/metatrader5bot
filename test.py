import MetaTrader5 as mt5
import time
import json
import os
from datetime import datetime, timedelta, timezone, time as dt_time
from filelock import FileLock

timeframe_map = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1
}

timeframe_duration = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60
}

# Function to read configuration with file locking
def read_config():
    print("Attempting to read m.json")
    lock = FileLock("m.json.lock")
    try:
        with lock:
            with open('m.json', 'r') as f:
                config = json.load(f)
                print("Successfully read m.json")
                return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading config: {e}")
        return None

def get_next_run_time(duration_minutes):
    now = datetime.now(timezone.utc)
    minutes = now.minute
    remainder = minutes % duration_minutes
    if remainder == 0 and now.second == 0 and now.microsecond == 0:
        return now
    else:
        if remainder == 0:
            next_time = now + timedelta(minutes=duration_minutes)
        else:
            minutes_to_add = duration_minutes - remainder
            next_time = now + timedelta(minutes=minutes_to_add)
        next_time = next_time.replace(second=0, microsecond=0)
        return next_time

# Function to check if symbol is available
def check_symbol(symbol):
    print(f"[{symbol}] Checking symbol availability")
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None or not symbol_info.visible:
        print(f"[{symbol}] Symbol is not available or not visible in MT5")
        return False
    return True

# Function to get the previous completed candle for the given timeframe
def get_previous_candle(symbol, timeframe, retries=3, delay=5):
    print(f"[{symbol}] Fetching previous candle for timeframe {timeframe}")
    duration_minutes = [v for k, v in timeframe_duration.items() if timeframe_map[k] == timeframe][0]
    for attempt in range(1, retries + 1):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)
        if rates is not None and len(rates) >= 2:
            current_candle = rates[0]
            previous_candle = rates[1]
            open_time = datetime.fromtimestamp(previous_candle['time'], tz=timezone.utc)
            close_time = open_time + timedelta(minutes=duration_minutes)
            current_time = datetime.fromtimestamp(current_candle['time'], tz=timezone.utc)
            if close_time != current_time:
                print(f"[{symbol}] Warning: Expected close_time {close_time}, got {current_time}. Using calculated close_time.")
            if close_time <= open_time or (datetime.now(timezone.utc) - close_time).total_seconds() > duration_minutes * 60 * 2:
                print(f"[{symbol}] Invalid candle timestamps: open_time={open_time}, close_time={close_time}")
                return None
            print(f"[{symbol}] Candle details: Open time={open_time}, Close time={close_time}, Open={previous_candle['open']}, Close={previous_candle['close']}")
            return {
                "open": previous_candle['open'],
                "close": previous_candle['close'],
                "open_time": open_time,
                "close_time": close_time
            }
        error = mt5.last_error()
        print(f"[{symbol}] Attempt {attempt}/{retries} failed to get candle data. MT5 error: {error}")
        if attempt < retries:
            print(f"[{symbol}] Retrying in {delay} seconds...")
            time.sleep(delay)
    print(f"[{symbol}] Failed to fetch candle data after {retries} attempts")
    return None

# Function to open main trade
def open_trade(symbol, trade_type, volume, D_tp, D_sl, magic):
    tp_distance = D_tp 
    sl_distance = D_sl
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if trade_type == mt5.ORDER_TYPE_BUY else tick.bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": trade_type,
        "price": price,
        "deviation": 10,
        "magic": magic,
        "comment": "Main trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[{symbol}] Failed to open trade: retcode={result.retcode}, comment={result.comment}")
        return None
    
    opening_price = result.price
    position_id = result.order
    tp = opening_price + tp_distance if trade_type == mt5.ORDER_TYPE_BUY else opening_price - tp_distance
    sl = opening_price - sl_distance if trade_type == mt5.ORDER_TYPE_BUY else opening_price + sl_distance
    modify_request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": position_id,
        "tp": tp,
        "sl": sl,
    }
    modify_result = mt5.order_send(modify_request)
    if modify_result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[{symbol}] Failed to set TP/SL: retcode={modify_result.retcode}")
    else:
        print(f"[{symbol}] Trade opened: price={opening_price}, tp={tp}, sl={sl}, magic={magic}")
    return result

# Function to place pending counter order
def place_pending_order(symbol, order_type, volume, price, tp, sl_counter, magic):
    print(f"[{symbol}] Placing pending order: type={order_type}, volume={volume}, price={price}, tp={tp}, magic={magic}")
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "tp": tp,
        "sl": sl_counter,
        "deviation": 10,
        "magic": magic,
        "comment": "Counter trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[{symbol}] Failed to place pending order: retcode={result.retcode}, comment={result.comment}")
    else:
        print(f"[{symbol}] Pending order placed successfully: price={price}, magic={magic}")
    return result

# Function to check and reconnect MT5 if necessary
def check_mt5_connection():
    print("Checking MT5 connection")
    if not mt5.terminal_info():
        print("MT5 connection lost, attempting to reconnect...")
        if not mt5.initialize():
            print("Failed to reconnect to MT5")
            return False
        if not mt5.login(account, password, server):
            print("Failed to login to MT5")
            mt5.shutdown()
            return False
        print("Reconnected to MT5")
    else:
        print("MT5 connection is active")
    return True

# Main trading loop
if __name__ == "__main__":
        # Initialize MT5 with the terminal path
    terminal_path = r"C:\Users\Administrator\Desktop\candle\MetaTrader 5 EXNESS\terminal64.exe"
    print(f"Initializing MT5 with terminal path: {terminal_path}")
    if not mt5.initialize(path=terminal_path):
        print("Failed to initialize MT5")
        quit()

    # Login to MT5 account
    account = 108582399
    password = "Faizy@2014$"
    server = "Exness-MT5Real6"
    print(f"Logging into MT5: account={account}, server={server}")
    if not mt5.login(account, password, server):
        print("Failed to login to MT5")
        mt5.shutdown()
        quit()

    print("MT5 Trading Bot Started")

    # Initialize magic counter
    print("Initializing magic counter")
    positions = mt5.positions_get() or []
    orders = mt5.orders_get() or []
    print(f"Found {len(positions)} open positions and {len(orders)} pending orders")
    all_magic = [pos.magic for pos in positions] + [order.magic for order in orders]
    magic_counter = max(all_magic) + 1 if all_magic else 100000
    print(f"Magic counter set to: {magic_counter}")

    while True:
        try:
            # Check MT5 connection
            print("Starting new iteration of main loop")
            if not check_mt5_connection():
                print("MT5 connection check failed, retrying in 60 seconds")
                time.sleep(60)
                continue

            # Load and display configuration
            config = read_config()
            if config is None:
                print("Configuration file is missing or invalid. Please check m.json.")
                time.sleep(60)
                continue

            if not config["telegram"].get("bot_enabled", True):
                print("Bot is disabled in config, skipping trade opening")
                time.sleep(60)
                continue

            # Extract config values
            print("Extracting configuration values")
            timeframe_str = config["trading"]["timeframe"]
            if timeframe_str not in timeframe_map:
                print(f"Invalid timeframe: {timeframe_str}. Supported timeframes: {list(timeframe_map.keys())}")
                time.sleep(60)
                continue
            timeframe = timeframe_map[timeframe_str]
            duration_minutes = timeframe_duration[timeframe_str]
            symbols = config["trading"]["symbols"]
            min_candle_size_points = config["trading"]["min_candle_size_points"]
            M = config["trading"]["M"]
            counter_trade_enabled = config["trading"]["counter_trade_enabled"]
            
            # Extract trading hours and mode
            start_time_str = config["trading"]["start_time"]
            end_time_str = config["trading"]["end_time"]
            trade_mode = config["trading"]["trade_mode"]
            
            # Parse trading hours
            start_hour, start_min = map(int, start_time_str.split(':'))
            end_hour, end_min = map(int, end_time_str.split(':'))
            start_time = dt_time(start_hour, start_min)
            end_time = dt_time(end_hour, end_min)
            
            # Validate trade mode
            if trade_mode not in ["both", "buy_only", "sell_only"]:
                print(f"Invalid trade_mode: {trade_mode}. Must be 'both', 'buy_only', or 'sell_only'.")
                time.sleep(60)
                continue

            # Wait for the next interval based on the selected timeframe
            next_run_time = get_next_run_time(duration_minutes)
            print(f"Current time: {datetime.now(timezone.utc)}, Waiting for next run time: {next_run_time}")
            while datetime.now(timezone.utc) < next_run_time:
                positions = mt5.positions_get() or []
                position_magics = set(pos.magic for pos in positions)
                orders = mt5.orders_get() or []
                for order in orders:
                    if order.magic not in position_magics:
                        print(f"Pending order {order.ticket} (magic={order.magic}) has no matching position, canceling")
                        request = {
                            "action": mt5.TRADE_ACTION_REMOVE,
                            "order": order.ticket
                        }
                        result = mt5.order_send(request)
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            print(f"Canceled pending order {order.ticket} for magic {order.magic}")
                        else:
                            print(f"Failed to cancel pending order {order.ticket}: {result.comment}")
                time.sleep(10)

            # Check if within trading hours
            if not (start_time <= next_run_time.time() <= end_time):
                print(f"Outside trading hours ({start_time} - {end_time}), skipping trade execution")
                continue

            for symbol in symbols:
                print(f"Processing symbol: {symbol}")
                if symbol not in config["trading"]["settings"]:
                    print(f"[{symbol}] Settings not found in config, skipping")
                    continue
                settings = config["trading"]["settings"][symbol]
                volume = settings["volume"]
                D_tp = settings["tp"]
                D_sl = settings["sl"]
                D_counter = settings["counter"]
                D_tp_counter = settings["tp_counter"]
                sl_counter = settings["sl_counter"]
                print(f"[{symbol}] Using volume: {volume}, D_tp: {D_tp}, D_sl: {D_sl}, D_counter: {D_counter}, D_tp_counter: {D_tp_counter}")

                # Check symbol availability
                if not check_symbol(symbol):
                    print(f"[{symbol}] Skipping due to unavailable symbol")
                    continue

                # Get candle data
                candle_data = get_previous_candle(symbol, timeframe)
                if candle_data is None:
                    print(f"[{symbol}] Skipping due to failure in fetching candle data")
                    continue

                # Fetch symbol info for price formatting
                print(f"[{symbol}] Fetching symbol info")
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    print(f"[{symbol}] Failed to get symbol info")
                    continue
                print(f"[{symbol}] Symbol info retrieved: digits={symbol_info.digits}, point={symbol_info.point}")

                # Format prices with symbol-specific decimal places
                digits = symbol_info.digits
                open_price = f"{candle_data['open']:.{digits}f}"
                close_price = f"{candle_data['close']:.{digits}f}"
                print(f"[{symbol}] Previous candle: Open time={candle_data['open_time']}, Close time={candle_data['close_time']}, Open={open_price}, Close={close_price}")

                # Check if candle is neutral
                point = symbol_info.point
                min_candle_size = min_candle_size_points * point
                candle_size = abs(candle_data['close'] - candle_data['open'])
                print(f"[{symbol}] Candle size: {candle_size}, Minimum required size: {min_candle_size}")
                if candle_size < min_candle_size:
                    print(f"[{symbol}] Neutral candle, skipping trade")
                    continue

                # Get current tick data
                print(f"[{symbol}] Fetching tick data")
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    print(f"[{symbol}] Failed to get tick price, market might be closed")
                    continue
                print(f"[{symbol}] Tick data: bid={tick.bid}, ask={tick.ask}")

                magic = magic_counter
                magic_counter += 1
                if candle_data['close'] > candle_data['open'] and (trade_mode == "both" or trade_mode == "buy_only"):
                    trade_type = mt5.ORDER_TYPE_BUY
                    result = open_trade(symbol, trade_type, volume, D_tp, D_sl, magic)
                    if result is None:
                        print(f"[{symbol}] Main trade failed, proceeding to counter trade if enabled")
                    if counter_trade_enabled and trade_mode == "both":
                        price = tick.ask
                        counter_price = price - D_counter
                        counter_tp = counter_price - D_tp_counter
                        sl_counter_val = price + sl_counter
                        place_pending_order(symbol, mt5.ORDER_TYPE_SELL_STOP, volume * M, counter_price, counter_tp, sl_counter_val, magic)
                elif candle_data['close'] < candle_data['open'] and (trade_mode == "both" or trade_mode == "sell_only"):
                    trade_type = mt5.ORDER_TYPE_SELL
                    price = tick.bid
                    result = open_trade(symbol, trade_type, volume, D_tp, D_sl, magic)
                    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                        continue
                    if counter_trade_enabled and trade_mode == "both":
                        counter_price = price + D_counter
                        counter_tp = counter_price + D_tp_counter
                        sl_counter_val = price - sl_counter
                        place_pending_order(symbol, mt5.ORDER_TYPE_BUY_STOP, volume * M, counter_price, counter_tp, sl_counter_val, magic)
                else:
                    print(f"[{symbol}] Trade skipped: No direction or restricted by trade_mode")
        except KeyboardInterrupt:
            print("Bot stopped by user (KeyboardInterrupt)")
            mt5.shutdown()
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(20)