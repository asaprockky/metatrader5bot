

# MT5 Trading Bot

A Python-based automated trading bot for MetaTrader 5 (MT5), designed to execute trades based on candlestick analysis. The timeframe for the candlestick analysis is configurable via the `config.json` file. This bot is configurable via a JSON file, allowing customization of trading hours, volume, take-profit, stop-loss, and counter-trade strategies. It is optimized for the Exness MT5 platform and includes robust connection handling and error recovery.

## Features
- **Configurable Candlestick Analysis**: Executes trades based on the direction and size of the previous candle, with the timeframe configurable in `config.json`.
- **Customizable Settings**: Supports configurable trading parameters (volume, TP, SL, counter trades) per symbol via `config.json`.
- **Trading Hours**: Operates within a specified time window (e.g., 01:00 to 23:00 local +05 time, adjusted to UTC).
- **Counter Trades**: Places pending counter orders (e.g., SELL_STOP or BUY_STOP) when enabled.
- **Robust Connection**: Includes MT5 reconnection logic and candle data retry mechanism.
- **Symbol Support**: Currently supports XAUUSD, with extensibility for additional symbols.

## Requirements
- Python 3.x
- MetaTrader 5 terminal installed (e.g., Exness MT5)
- Required Python libraries: `MetaTrader5`, `filelock`, `json`

Install dependencies:
```bash
pip install MetaTrader5 filelock
```

## Setup
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/mt5-trading-bot.git
   cd mt5-trading-bot
   ```

2. **Configure MT5**:
   - Ensure the MT5 terminal (e.g., `terminal64.exe`) is installed. The script uses the path `C:\Users\Administrator\Desktop\candle\MetaTrader 5 EXNESS\terminal64.exe`.
   - Update the `terminal_path` variable in the `mt.py` script if your path differs.

3. **Edit `config.json`**:
   - This is the sole configuration file for the bot.
   - Modify the file with your MT5 account details, trading preferences, and Telegram settings (if used).
   - Example `config.json`:
     ```json
     {
       "telegram": {
         "token": "your_telegram_token",
         "allowed_user_ids": [123456789, 987654321],
         "bot_enabled": false
       },
       "trading": {
         "timeframe": "M15",
         "symbols": ["XAUUSD"],
         "min_candle_size_points": 10,
         "M": 5.0,
         "counter_trade_enabled": true,
         "start_time": "01:00",
         "end_time": "23:00",
         "trade_mode": "both",
         "settings": {
           "XAUUSD": {
             "volume": 0.05,
             "tp": 1.0,
             "sl": 6.898,
             "counter": 5.0,
             "tp_counter": 1.786,
             "sl_counter": 1000.0
           }
         }
       }
     }
     ```
   - Note: `start_time` and `end_time` are interpreted as local +05 time and converted to UTC internally.

4. **Update Login Credentials**:
   - Replace `account`, `password`, and `server` in the script with your MT5 login details:
     ```python
     account = your_id
     password = "password"
     server = "yourserver"
     ```
   These credentials should be updated directly in the `mt.py` script.

5. **Run the Bot**:
   ```bash
   python mt.py
   ```

## How It Works
- The `mt.py` script initializes an MT5 connection and logs into your account using the credentials specified in the script.
- It waits for the next interval based on the `timeframe` setting in `config.json` (e.g., if timeframe is M15, it waits for the next 15-minute interval like 07:45 PM +05, or 14:45 UTC on May 20, 2025) to process the previous candle.
- For each symbol specified in `config.json` (e.g., XAUUSD), it:
  - Fetches the previous candle based on the configured `timeframe`.
  - Checks if the candle size exceeds the `min_candle_size_points` threshold from `config.json`.
  - Opens a BUY trade if the candle is bullish, or a SELL trade if bearish, within the configured trading hours.
  - Places a pending counter trade (e.g., SELL_STOP for BUY) if enabled.
- Trades include take-profit (TP) and stop-loss (SL) settings from `config.json`, with magic numbers for tracking.

## Current Status
- **Date and Time**: 07:46 PM +05, Tuesday, May 20, 2025 (14:46 UTC). (This is an example, the bot uses the current system time)
- The bot operates based on the `start_time` and `end_time` specified in `config.json`, interpreted as local +05 time and converted to UTC internally.
- Next execution depends on the `timeframe` in `config.json`. For example, if M15, and current time is 07:46 PM +05, next execution is expected at 08:00 PM +05 (15:00 UTC) for the candle ending at 07:59:59 PM +05.

## Limitations
- The trading hours logic assumes UTC for internal calculations; ensure `start_time` and `end_time` in `config.json` are set according to your local +05 timezone.
- The script supports symbols listed in the `symbols` array in `config.json`.

## Contributing
Feel free to fork this repository, submit issues, or send pull requests to enhance functionality.

---

### Notes
- Replace `yourusername`, `your_telegram_token`, and the license placeholder with your details.
- Ensure your MT5 account credentials in `mt.py` are correct and that `config.json` is properly configured.
