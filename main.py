import MetaTrader5 as mt5
import time
import json
import os
from datetime import datetime, timedelta, timezone
from filelock import FileLock

# Function to read configuration with file locking
def read_config():
    lock = FileLock("config.json.lock")
    try:
        with lock:
            with open('config.json', 'r') as f:
                return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading config: {e}")
        return None

# Function to get the most recent completed candle
def get_previous_candle(symbol):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
    if rates is None or len(rates) < 1:
        print(f"[{symbol}] Failed to get candle data")
        return None
    candle = rates[0]  # Most recent completed candle
    open_time = datetime.fromtimestamp(candle['time'], tz=timezone.utc)
    close_time = open_time + timedelta(seconds=59)  # M1 candle duration
    return {
        "open": candle['open'],
        "close": candle['close'],
        "open_time": open_time,
        "close_time": close_time
    }

# Function to open main trade
def open_trade(symbol, trade_type, volume, price, tp, sl, magic):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": trade_type,
        "price": price,
        "tp": tp,
        "sl": sl,
        "deviation": 10,
        "magic": magic,
        "comment": "Main trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(request)
    return result

# Function to place pending counter order
def place_pending_order(symbol, order_type, volume, price, tp, magic):
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "tp": tp,
        "deviation": 10,
        "magic": magic,
        "comment": "Counter trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    return result

# Main trading loop
if __name__ == "__main__":
    # Initialize MT5
    if not mt5.initialize():
        print("Failed to initialize MT5")
        quit()

    # Login to MT5 account
    account = 242828249
    password = "UpworkTest1."
    server = "Exness-MT5Trial"
    if not mt5.login(account, password, server):
        print("Failed to login to MT5")
        mt5.shutdown()
        quit()

    print("MT5 Trading Bot Started")

    # Initialize magic counter
    positions = mt5.positions_get() or []
    orders = mt5.orders_get() or []
    all_magic = [pos.magic for pos in positions] + [order.magic for order in orders]
    magic_counter = max(all_magic) + 1 if all_magic else 100000

    while True:
        # Cancel pending orders if main trade is closed
        positions = mt5.positions_get() or []
        position_magics = set(pos.magic for pos in positions)
        orders = mt5.orders_get() or []
        for order in orders:
            if order.magic not in position_magics:
                request = {
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": order.ticket
                }
                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"Canceled pending order {order.ticket} for magic {order.magic}")
                else:
                    print(f"Failed to cancel pending order {order.ticket}: {result.comment}")

        # Load configuration inside the loop to reflect changes
        config = read_config()
        if config is None:
            time.sleep(5)  # Wait before retrying if config fails
            continue

        symbols = config["symbols"]
        volume = config["volume"]
        D_tp = config["D_tp"]
        D_sl = config["D_sl"]
        D_counter = config["D_counter"]
        M = config["M"]
        D_tp_counter = config["D_tp_counter"]
        counter_trade_enabled = config["counter_trade_enabled"]
        min_candle_size_points = config.get("min_candle_size_points", 0)

        # Wait for the next minute to process the just-closed candle
        current_time = time.time()
        sleep_time = 60 - (current_time % 60)
        time.sleep(sleep_time)

        for symbol in symbols:
            candle_data = get_previous_candle(symbol)
            if candle_data is None:
                continue

            # Fetch symbol info for price formatting
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                print(f"[{symbol}] Failed to get symbol info")
                continue
            
            # Format prices with symbol-specific decimal places
            digits = symbol_info.digits
            open_price = f"{candle_data['open']:.{digits}f}"
            close_price = f"{candle_data['close']:.{digits}f}"
            
            # Log candle times and prices
            print(f"[{symbol}] Previous candle: Open time={candle_data['open_time']}, Close time={candle_data['close_time']}, Open={open_price}, Close={close_price}")

            # Check if candle is neutral
            point = symbol_info.point
            min_candle_size = min_candle_size_points * point
            if abs(candle_data['close'] - candle_data['open']) < min_candle_size:
                print(f"[{symbol}] Neutral candle, skipping")
                continue

            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print(f"[{symbol}] Failed to get tick price")
                continue
            magic = magic_counter
            magic_counter += 1

            if candle_data['close'] > candle_data['open']:
                # Bullish candle, open BUY trade
                trade_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
                tp = price + D_tp
                sl = price - D_sl
                result = open_trade(symbol, trade_type, volume, price, tp, sl, magic)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f"[{symbol}] Failed to open BUY trade: {result.comment}")
                    continue
                print(f"[{symbol}] Opened BUY trade at {price} with magic {magic}")
                if counter_trade_enabled:
                    counter_price = price - D_counter
                    counter_tp = counter_price - D_tp_counter
                    place_pending_order(symbol, mt5.ORDER_TYPE_SELL_STOP, volume * M, counter_price, counter_tp, magic)
                    print(f"[{symbol}] Placed SELL STOP counter trade at {counter_price} with magic {magic}")
            elif candle_data['close'] < candle_data['open']:
                # Bearish candle, open SELL trade
                trade_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
                tp = price - D_tp
                sl = price + D_sl
                result = open_trade(symbol, trade_type, volume, price, tp, sl, magic)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f"[{symbol}] Failed to open SELL trade: {result.comment}")
                    continue
                print(f"[{symbol}] Opened SELL trade at {price} with magic {magic}")
                if counter_trade_enabled:
                    counter_price = price + D_counter
                    counter_tp = counter_price + D_tp_counter
                    place_pending_order(symbol, mt5.ORDER_TYPE_BUY_STOP, volume * M, counter_price, counter_tp, magic)
                    print(f"[{symbol}] Placed BUY STOP counter trade at {counter_price} with magic {magic}")