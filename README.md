# 🎯 E-commerce Price Monitor

A powerful, **zero-configuration** Python tool that automatically monitors e-commerce websites for products below your specified price threshold. Features intelligent HTML auto-detection, parallel scanning, and instant Telegram notifications.

## ✨ Key Features

- **🚀 Interactive Setup** - No manual configuration files needed! Just run and answer simple questions
- **🤖 Auto-Detection** - Automatically finds and parses products, categories, and prices from any e-commerce site  
- **⚡ Lightning Fast** - Parallel scanning with configurable worker threads
- **📱 Telegram Alerts** - Instant notifications when cheap products are found
- **🎯 Smart Filtering** - Automatically excludes gift cards, vouchers, and non-product pages
- **🌍 International Support** - Handles multiple price formats (European, US, various currencies)
- **🔄 Continuous Monitoring** - Runs continuously with customizable check intervals
- **💾 Persistent Tracking** - Remembers products to avoid duplicate notifications

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Monitor

Simply run the script - it will guide you through setup:

```bash
python price_monitor.py
```

You'll be asked for website URL, price threshold, check interval, and optional Telegram settings. Configuration is saved to `config.json` and reused automatically.

**Reconfigure anytime:**
```bash
python price_monitor.py --reset
```

## ⚙️ Configuration

All settings stored in `config.json` (auto-generated during first run):

- `base_url` - Target e-commerce website
- `max_price` - Price threshold for alerts
- `check_interval` - Seconds between scans
- `parallel_workers` - Number of threads (1-5)
- `telegram_*` - Notification settings
- `excluded_url_patterns` - URL patterns to skip

## 📱 Telegram Setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → Copy token
2. Message [@userinfobot](https://t.me/userinfobot) → Copy chat ID
3. Enter credentials during interactive setup

## 🧠 How It Works

- **Auto-Detection**: Tries 9 category selectors, 8 product selectors, 7 title selectors, 5 price selectors
- **Smart Parsing**: Handles European (1.999,00) and US (1,999.00) formats, multiple currencies
- **Intelligent Filtering**: Auto-excludes checkout/cart/account pages, discount percentages
- **Performance**: Parallel scanning, price-sorted requests, smart throttling
- **No Spam**: Only notifies for new products and critical errors

## 📊 Example Output

```
Found 57 categories to monitor
Starting parallel scan with 3 threads...
🎯 FOUND: Cool Jacket - 8.99 - https://example.com/product/123

Iteration #1 Summary:
  - Products checked: 842
  - Products found (<= 10.0): 3
  - Execution time: 23.5 seconds
```

## 🔧 Troubleshooting

**No products found?**
- Increase `max_price` threshold
- Check `monitor.log` for warnings
- Review exclusion patterns

**HTTP errors?**
- Reduce `parallel_workers`
- Increase `request_delay` in config

## 📄 License

MIT License - See LICENSE file

---

**⭐ Star this repo if you find it useful!**
