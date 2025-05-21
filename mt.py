import MetaTrader5 as mt5
import time
import json
import os
from datetime import datetime, timedelta, timezone
from filelock import FileLock

# Function to read configuration with file locking
def read_config():
    print("Attempting to read config.json")
    lock = FileLock("config.json.lock")
    try:
        with lock:
            with open('configdemo.json', 'r') as f:
                config = json.load(f)
                print("Successfully read config.json")
                return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading config: {e}")
        return None

# Function to get the next run time (start of the next 15-minute interval)
def get_next_run_time():
    now = datetime.now(timezone.utc)
    print(f"Calculating next run time. Current time: {now}")
    # Find the current 15-minute interval start
    current_interval = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
    # Next interval is 15 minutes later
    next_interval = current_interval + timedelta(minutes=15)
    print(f"Next run time calculated: {next_interval}")
    return next_interval

def get_previous_candle(symbol, run_time=None):
    print(f"[{symbol}] Fetching previous candle")
    if run_time is None:
        run_time = datetime.now(timezone.utc)
        print(f"[{symbol}] No run_time provided, using current time: {run_time}")
    # Align to the start of the current 15-minute interval
    minutes = (run_time.minute // 15) * 15
    current_start = run_time.replace(minute=minutes, second=0, microsecond=0)
    # Adjust end_time to be just before the current interval starts
    end_time = current_start - timedelta(seconds=1)
    # Set start_time to 15 minutes before end_time
    start_time = end_time - timedelta(minutes=15)
    print(f"[{symbol}] Requesting rates from {start_time} to {end_time}")
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start_time, end_time)
    print(f"[{symbol}] Got {len(rates) if rates is not None else 'None'} bars")
    if rates is None or len(rates) < 1:
        error = mt5.last_error()
        print(f"[{symbol}] Failed to get candle data. MT5 error: {error}")
        return None
    # Select the last candle, which should be the previous completed one
    candle = rates[-1]
    open_time = datetime.fromtimestamp(candle['time'], tz=timezone.utc)
    close_time = open_time + timedelta(minutes=15)
    print(f"[{symbol}] Candle details: Open time={open_time}, Close time={close_time}, Open={candle['open']}, Close={candle['close']}")
    return {
        "open": candle['open'],
        "close": candle['close'],
        "open_time": open_time,
        "close_time": close_time
    }

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
def place_pending_order(symbol, order_type, volume, price, tp,sl_counter, magic):
    print(f"[{symbol}] Placing pending order: type={order_type}, volume={volume}, price={price}, tp={tp}, magic={magic}")
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "tp": tp,
        "sl" : sl_counter,
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
        if not mt5.initialize(path=terminal_path):
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
    terminal_path = r"C:\\Users\\Administrator\\Desktop\\candle\\MetaTrader 5 EXNESS - demo\\terminal64.exe"
    print(f"Initializing MT5 with terminal path: {terminal_path}")
    if not mt5.initialize(path=terminal_path):
        print("Failed to initialize MT5")
        quit()

    # Login to MT5 account
    account = 271019083
    password = "Thoufy@1985$"
    server = "Exness-MT5Trial14"
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
        # Check MT5 connection
        print("Starting new iteration of main loop")
        if not check_mt5_connection():
            print("MT5 connection check failed, retrying in 60 seconds")
            time.sleep(60)
            continue

        # Wait for the next 15-minute interval, checking pending orders periodically
        next_run_time = get_next_run_time()
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

        # Load and display configuration
        config = read_config()
        if config is None:
            print("Configuration file is missing or invalid. Please check config.json.")
            continue

        if not config["telegram"].get("bot_enabled", True):
            print("Bot is disabled in config, skipping trade opening")
            continue

        # Extract config values
        print("Extracting configuration values")
        symbols = config["trading"]["symbols"]
        min_candle_size_points = config["trading"]["min_candle_size_points"]
        M = config["trading"]["M"]
        counter_trade_enabled = config["trading"]["counter_trade_enabled"]

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

            # Get candle data
            candle_data = get_previous_candle(symbol, next_run_time)
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
            if candle_data['close'] > candle_data['open']:
                trade_type = mt5.ORDER_TYPE_BUY
                result = open_trade(symbol, trade_type, volume, D_tp, D_sl, magic)
                if result is None:  # Check if trade failed
                    print(f"[{symbol}] Main trade failed, proceeding to counter trade if enabled")
                if counter_trade_enabled:
                    price = tick.ask
                    counter_price = price - D_counter
                    counter_tp = counter_price - D_tp_counter
                    sl_counter = price + sl_counter
                    place_pending_order(symbol, mt5.ORDER_TYPE_SELL_STOP, volume * M, counter_price, counter_tp,sl_counter, magic)
            elif candle_data['close'] < candle_data['open']:
                trade_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
                result = open_trade(symbol, trade_type, volume, D_tp, D_sl, magic)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    continue
                if counter_trade_enabled:
                    counter_price = price + D_counter
                    counter_tp = counter_price + D_tp_counter
                    sl_counter = price - sl_counter
                    place_pending_order(symbol, mt5.ORDER_TYPE_BUY_STOP, volume * M, counter_price, counter_tp,sl_counter, magic)
            else:
                print(f"[{symbol}] Candle has no direction (close == open), skipping trade")