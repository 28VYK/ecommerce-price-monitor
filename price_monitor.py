"""
Generic E-commerce Price Monitor with Interactive Setup
Automatically detects HTML structure and monitors products below a price threshold
Sends Telegram notifications when cheap products are found
"""

import requests
from bs4 import BeautifulSoup
import time
import logging
import json
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
import re
import os
import sys

# Configuration file path
CONFIG_FILE = "config.json"

# Default configuration template
DEFAULT_CONFIG = {
    "base_url": "",
    "site_name": "",
    "max_price": 10.0,
    "check_interval": 60,
    "parallel_workers": 3,
    "telegram_enabled": False,
    "telegram_token": "",
    "telegram_chat_id": "",
    "excluded_url_patterns": ["gift-card", "voucher", "gift-certificate"],
    "request_delay": 0.4,
    "max_products_per_category": 50
}

# Global config - initialized at startup
config = DEFAULT_CONFIG.copy()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration from file or create new if doesn't exist"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return None
    return None


def save_config(config_data: dict):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        logger.info(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error saving config: {e}")


def interactive_setup() -> dict:
    """Interactive setup wizard for first-time configuration"""
    print("\n" + "="*70)
    print("🎯 E-COMMERCE PRICE MONITOR - INTERACTIVE SETUP")
    print("="*70)
    print("\nWelcome! Let's configure your price monitor.\n")
    
    config_data = DEFAULT_CONFIG.copy()
    
    # Website configuration
    print("📌 WEBSITE CONFIGURATION")
    print("-" * 70)
    
    while True:
        url_input = input("Enter the e-commerce website URL (e.g., https://example.com): ").strip()
        # Auto-add https:// if missing
        if not url_input.startswith(('http://', 'https://')):
            url_input = 'https://' + url_input
        
        # Basic URL validation
        try:
            parsed = urlparse(url_input)
            if parsed.scheme and parsed.netloc:
                config_data["base_url"] = url_input
                break
            else:
                print("❌ Invalid URL. Please try again.")
        except:
            print("❌ Invalid URL. Please try again.")
    
    config_data["site_name"] = input("Enter a name for this site (for logging): ").strip()
    
    # Monitoring parameters
    print("\n⚙️  MONITORING PARAMETERS")
    print("-" * 70)
    
    while True:
        try:
            max_price = input(f"Maximum price threshold for alerts (default: {DEFAULT_CONFIG['max_price']}): ").strip()
            config_data["max_price"] = float(max_price) if max_price else DEFAULT_CONFIG['max_price']
            break
        except ValueError:
            print("❌ Invalid number. Please enter a valid price.")
    
    while True:
        try:
            interval = input(f"Check interval in seconds (default: {DEFAULT_CONFIG['check_interval']}): ").strip()
            config_data["check_interval"] = int(interval) if interval else DEFAULT_CONFIG['check_interval']
            break
        except ValueError:
            print("❌ Invalid number. Please enter a valid interval.")
    
    while True:
        try:
            workers = input(f"Parallel workers (1-5, default: {DEFAULT_CONFIG['parallel_workers']}): ").strip()
            if workers:
                workers_int = int(workers)
                if 1 <= workers_int <= 5:
                    config_data["parallel_workers"] = workers_int
                    break
                else:
                    print("❌ Please enter a number between 1 and 5.")
            else:
                config_data["parallel_workers"] = DEFAULT_CONFIG['parallel_workers']
                break
        except ValueError:
            print("❌ Invalid number. Please enter a valid number.")
    
    # Telegram configuration
    print("\n📱 TELEGRAM NOTIFICATIONS")
    print("-" * 70)
    telegram_choice = input("Enable Telegram notifications? (y/n, default: n): ").strip().lower()
    
    if telegram_choice == 'y':
        config_data["telegram_enabled"] = True
        print("\nTo get your Telegram credentials:")
        print("  1. Bot Token: Message @BotFather on Telegram and create a new bot")
        print("  2. Chat ID: Message @userinfobot on Telegram to get your chat ID\n")
        
        config_data["telegram_token"] = input("Enter your Telegram Bot Token: ").strip()
        config_data["telegram_chat_id"] = input("Enter your Telegram Chat ID: ").strip()
    else:
        config_data["telegram_enabled"] = False
    
    # Exclusions
    print("\n🚫 PRODUCT EXCLUSIONS")
    print("-" * 70)
    print(f"Current exclusions: {', '.join(DEFAULT_CONFIG['excluded_url_patterns'])}")
    add_exclusions = input("Add more URL patterns to exclude? (comma-separated, or press Enter to skip): ").strip()
    
    if add_exclusions:
        new_patterns = [p.strip() for p in add_exclusions.split(',')]
        config_data["excluded_url_patterns"].extend(new_patterns)
    
    # Summary
    print("\n" + "="*70)
    print("📋 CONFIGURATION SUMMARY")
    print("="*70)
    print(f"Website: {config_data['site_name']} ({config_data['base_url']})")
    print(f"Max Price: {config_data['max_price']}")
    print(f"Check Interval: {config_data['check_interval']} seconds ({config_data['check_interval']//60} minutes)")
    print(f"Parallel Workers: {config_data['parallel_workers']}")
    print(f"Telegram: {'Enabled' if config_data['telegram_enabled'] else 'Disabled'}")
    print(f"Exclusions: {len(config_data['excluded_url_patterns'])} patterns")
    print("="*70)
    
    confirm = input("\n✅ Save this configuration? (y/n): ").strip().lower()
    
    if confirm == 'y':
        save_config(config_data)
        print("\n✅ Configuration saved successfully!\n")
        return config_data
    else:
        print("\n❌ Setup cancelled. Run the script again to reconfigure.\n")
        sys.exit(0)


# Seen products tracking
seen_products = set()

def load_seen_products():
    """Load previously seen products from file"""
    global seen_products
    if os.path.exists('seen_products.json'):
        try:
            with open('seen_products.json', 'r', encoding='utf-8') as f:
                seen_products = set(json.load(f))
        except:
            seen_products = set()

def save_seen_products():
    """Save seen products to file"""
    try:
        with open('seen_products.json', 'w', encoding='utf-8') as f:
            json.dump(list(seen_products), f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save seen products: {e}")


def parse_price(price_text: str) -> float:
    """Parse price from text, handling multiple formats"""
    if not price_text:
        return float('inf')
    
    # Skip discount percentages
    if '%' in price_text:
        return float('inf')
    
    # Remove common currency symbols and text
    price_text = re.sub(r'[A-Za-z\s€$£RON]', '', price_text)
    
    # Handle different number formats
    # European format: 1.999,00 or 1999,00
    # US format: 1,999.00 or 1999.00
    
    # Count dots and commas
    dot_count = price_text.count('.')
    comma_count = price_text.count(',')
    
    try:
        if comma_count > 0 and dot_count > 0:
            # Both present - determine which is thousands separator
            if price_text.rfind(',') > price_text.rfind('.'):
                # Comma comes after dot -> European (1.999,00)
                price_text = price_text.replace('.', '').replace(',', '.')
            else:
                # Dot comes after comma -> US (1,999.00)
                price_text = price_text.replace(',', '')
        elif comma_count > 0:
            # Only comma - could be European decimal (999,99) or US thousands (1,999)
            if comma_count == 1 and price_text.index(',') > len(price_text) - 4:
                # Single comma near the end -> European decimal
                price_text = price_text.replace(',', '.')
            else:
                # Multiple commas or comma far from end -> US thousands
                price_text = price_text.replace(',', '')
        elif dot_count > 1:
            # Multiple dots -> European thousands (1.999)
            price_text = price_text.replace('.', '')
        
        price = float(price_text)
        
        # Sanity check - price should be reasonable
        if price <= 0 or price > 999999:
            return float('inf')
        
        return price
    except (ValueError, AttributeError):
        return float('inf')


def make_request(url: str, max_retries: int = 3) -> Optional[requests.Response]:
    """Make HTTP request with retry logic"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            time.sleep(config.get("request_delay", 0.4))
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to fetch {url} after {max_retries} attempts: {e}")
                return None
            time.sleep(2 ** attempt)
    
    return None


def get_all_categories(base_url: str) -> List[str]:
    """Get all product category URLs from the website using auto-detection"""
    logger.info("Collecting all categories...")
    
    response = make_request(base_url)
    if not response:
        return []
    
    soup = BeautifulSoup(response.content, 'lxml')
    categories = set()
    
    # Common selectors for navigation menus across different e-commerce platforms
    menu_selectors = [
        'nav a',
        '.navigation a',
        '.menu a',
        '.nav-menu a',
        'header nav a',
        '.category-menu a',
        '.main-nav a',
        '#menu a',
        'ul.menu a'
    ]
    
    for selector in menu_selectors:
        links = soup.select(selector)
        if links:
            logger.debug(f"Found {len(links)} links with selector: {selector}")
            
            for link in links:
                href = link.get('href', '')
                if not href or href in ['#', '/', '']:
                    continue
                
                # Convert relative URLs to absolute
                full_url = urljoin(base_url, href)
                
                # Only keep URLs from the same domain
                if not full_url.startswith(base_url):
                    continue
                
                # Filter out non-category pages (keeping deal sections like best-buy)
                # Add keywords in your website's language as needed
                excluded_keywords = [
                    'account', 'cart', 'checkout', 'login', 'register', 'signup',
                    'forgot', 'password', 'orders', 'order', 'return', 'returns',
                    'blog', 'testimonials', 'contact', 'about', 'terms', 'conditions',
                    'policy', 'privacy', 'delivery', 'shipping', 'payment', 'payments',
                    'map', 'search', 'wishlist', 'wish-list', 'favorites', 'favourites',
                    'newsletter', 'subscribe', 'cookies', 'how-to-buy', 'faq',
                    'price-guarantee', 'loyalty', 'rewards', 'points',
                    'size-guide', 'size-chart', 'info', 'information'
                ]
                
                url_lower = full_url.lower()
                if any(keyword in url_lower for keyword in excluded_keywords):
                    continue
                
                # Apply custom exclusion patterns from configuration
                if any(pattern in url_lower for pattern in config.get("excluded_url_patterns", [])):
                    continue
                
                categories.add(full_url)
    
    categories = list(categories)
    logger.info(f"Found {len(categories)} categories to monitor")
    return categories


def get_all_pages(category_url: str) -> List[str]:
    """Get all pagination URLs for a category with proper pagination detection"""
    pages = []
    
    # Sort by price ascending to find cheap products faster
    separator = '&' if '?' in category_url else '?'
    sorted_url = f"{category_url}{separator}sort_by=price_asc"
    pages.append(sorted_url)
    
    try:
        response = make_request(sorted_url)
        if not response:
            return pages
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Look for pagination using common selector patterns
        pagination_selectors = [
            '.pagination a',
            '.pager a', 
            'a[rel="next"]',
            '.page-numbers a',
            'nav.pagination a',
            'ul.pagination a'
        ]
        
        for selector in pagination_selectors:
            pagination_links = soup.select(selector)
            if pagination_links:
                for link in pagination_links:
                    href = link.get('href', '')
                    if href and href not in ['#', 'javascript:void(0)']:
                        full_url = urljoin(category_url, href)
                        if full_url not in pages:
                            pages.append(full_url)
                break  # Stop once we've found pagination
        
    except Exception as e:
        logger.debug(f"Could not extract pagination for {category_url}: {e}")
    
    logger.debug(f"Found {len(pages)} page(s) for {category_url}")
    return pages


def parse_products(url: str) -> List[Dict[str, any]]:
    """Parse products from a page using intelligent auto-detection"""
    response = make_request(url)
    if not response:
        return []
    
    soup = BeautifulSoup(response.content, 'lxml')
    products = []
    
    logger.debug(f"Parsing {url}")
    
    # Primary detection: find product containers using common CSS patterns
    container_selectors = [
        '.product',
        '.product-item',
        '.product-card',
        'article.product',
        '.item-product',
        '[data-product-id]',
        '.grid-item',
        '.product-listing-item',
        '[class*="product"]',  # Any class containing "product"
        'article[class*="item"]',
        'div[class*="grid"]'
    ]
    
    product_containers = []
    used_selector = None
    
    for selector in container_selectors:
        containers = soup.select(selector)
        if len(containers) >= 3:  # Need at least 3 to confirm we found the right pattern
            product_containers = containers
            used_selector = selector
            logger.info(f"Using selector '{selector}' - found {len(product_containers)} containers")
            break
    
    # Fallback detection: scan for links with price-like text nearby
    if not product_containers:
        logger.debug("No product containers found, using alternative detection...")
        # Find elements containing both links and price-like text
        all_links = soup.find_all('a', href=True)
        potential_products = []
        
        for link in all_links:
            # Skip non-product links
            if any(skip in link.get('href', '').lower() for skip in ['#', 'javascript:', 'mailto:']):
                continue
            
            # Check parent element for price indicators
            parent = link.find_parent(['div', 'article', 'li', 'section'])
            if parent:
                text = parent.get_text()
                # Look for currency symbols and numbers together
                if any(char in text for char in ['lei', 'ron', '$', '€', '£', ',', '.']):
                    if any(char.isdigit() for char in text):
                        potential_products.append(parent)
        
        # Remove duplicates
        product_containers = list(set(potential_products))
        if product_containers:
            logger.debug(f"Found {len(product_containers)} potential products using fallback detection")
    
    if not product_containers:
        logger.warning(f"No product containers found on {url}")
        return []
    
    for container in product_containers:
        try:
            logger.debug(f"=== Processing container ===")
            
            # Extract product title using common e-commerce patterns
            title_elem = None
            title = None
            
            # Common selectors for product titles
            title_selectors = [
                'h2 a', 'h3 a', 'h4 a', 'h2', 'h3', 'h4',
                '.product-title', '.product-name', '.title',
                'a.product-link', 'a[title]', '.name'
            ]
            
            for selector in title_selectors:
                elem = container.select_one(selector)
                if elem:
                    # Use title attribute when available (often more complete)
                    title = elem.get('title', '').strip()
                    if not title:
                        title = elem.get_text(strip=True)
                    if title and len(title) > 5:  # Sanity check
                        title_elem = elem
                        break
            
            # Last resort: use the longest link text
            if not title:
                links = container.find_all('a', href=True)
                for link in links:
                    text = link.get_text(strip=True)
                    if len(text) > 10:
                        title = text
                        title_elem = link
                        break
            
            if not title:
                logger.debug("Skipping - no title found")
                continue
            
            # Extract product URL
            link_elem = None
            product_url = None
            
            # Use the title element if it's already a link
            if title_elem and title_elem.name == 'a':
                link_elem = title_elem
            else:
                # Search for the main product link in container
                link_candidates = container.find_all('a', href=True)
                # Filter out icon/anchor links (product links usually have longer hrefs)
                link_candidates = [l for l in link_candidates if len(l.get('href', '')) > 5]
                # Find first valid product link
                for link in link_candidates:
                    href = link.get('href', '')
                    if not any(skip in href.lower() for skip in ['#', 'javascript:', 'mailto:', 'tel:']):
                        link_elem = link
                        break
            
            if not link_elem:
                logger.debug("Skipping - no link found")
                continue
            
            product_url = urljoin(config.get("base_url", ""), link_elem.get('href', ''))
            
            # Extract price using common selector patterns
            price_elem = None
            price = float('inf')
            
            # Common price selectors across e-commerce platforms
            price_selectors = [
                '.product__info--price-gross',  # Common e-commerce pattern
                '.price',
                '.product-price',
                'span.price',
                '.price-current',
                '[data-price]',
                '[class*="price"]',
                'span[class*="price"]'
            ]
            
            for selector in price_selectors:
                elems = container.select(selector)
                for elem in elems:
                    text = elem.get_text(strip=True)
                    # Ignore discount badges and eco-tax labels
                    if (text and '%' not in text and 'discount' not in text.lower() and 
                        'save' not in text.lower() and 'eco' not in text.lower()):
                        # Parse numeric price value
                        test_price = parse_price(text)
                        if test_price != float('inf') and test_price > 0:
                            price_elem = elem
                            price = test_price
                            logger.debug(f"Found price {price} with selector '{selector}'")
                            break
                if price_elem:
                    break
            
            # Fallback: scan all text for price-like patterns
            if not price_elem:
                # Search text nodes for numbers with currency indicators
                all_text = container.find_all(string=True)
                for text_node in all_text:
                    text = text_node.strip()
                    # Look for digits + currency symbols together
                    if (any(c.isdigit() for c in text) and 
                        any(curr in text.lower() for curr in ['lei', 'ron', '$', '€', '£', ','])):
                        # Filter out discount percentages
                        if '%' not in text and 'discount' not in text.lower():
                            test_price = parse_price(text)
                            if test_price != float('inf') and test_price > 0:
                                price = test_price
                                break
            
            if price == float('inf'):
                logger.info(f"Skipping product - no valid price found for {title[:30]}")
                continue
            
            # Validate price is reasonable
            if price <= 0 or price > 999999:
                logger.debug(f"Skipping product - price out of range: {price}")
                continue
            
            # Apply exclusion patterns
            if any(pattern in product_url.lower() for pattern in config.get("excluded_url_patterns", [])):
                logger.debug(f"Skipping excluded product: {product_url}")
                continue
            
            # Collect all valid products (price filtering happens at scan level)
            logger.debug(f"Found product: {title[:30]}... - {price} lei")
            products.append({
                'title': title,
                'price': price,
                'url': product_url
            })
        
        except Exception as e:
            logger.info(f"Error parsing product container: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    logger.info(f"Parsed {len(products)} products from {len(product_containers)} containers")
    return products


def send_telegram_alert(message: str, parse_mode: str = None) -> bool:
    """Send alert via Telegram"""
    if not config.get("telegram_enabled", False):
        return False
    
    try:
        url = f"https://api.telegram.org/bot{config['telegram_token']}/sendMessage"
        payload = {
            'chat_id': config['telegram_chat_id'],
            'text': message
        }
        if parse_mode:
            payload['parse_mode'] = parse_mode
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return False


def scan_category(category_url: str) -> Tuple[int, int, bool]:
    """Scan a single category for products below threshold"""
    category_name = category_url.split('/')[-1] or 'unknown'
    logger.info(f"Scanning: {category_name}")
    
    products_checked = 0
    products_found = 0
    had_errors = False
    
    try:
        pages = get_all_pages(category_url)
        
        for page_url in pages:
            products = parse_products(page_url)
            
            # Keep only products within the price threshold
            max_price = config.get("max_price", 10.0)
            filtered_products = [p for p in products if p['price'] <= max_price]
            
            products_checked += len(filtered_products)
            logger.debug(f"Found {len(products)} products, {len(filtered_products)} match price threshold")
            
            for product in filtered_products:
                product_id = f"{product['url']}_{product['price']}"
                
                if product_id not in seen_products:
                    seen_products.add(product_id)
                    products_found += 1
                    
                    # Log discovered product
                    logger.warning(f"🎯 FOUND: {product['title']} - {product['price']} - {product['url']}")
                    
                    # Notify via Telegram
                    msg = f"🎯 *CHEAP PRODUCT FOUND!*\n\n"
                    msg += f"*Title:* {product['title']}\n"
                    msg += f"*Price:* {product['price']}\n"
                    msg += f"*URL:* {product['url']}"
                    send_telegram_alert(msg, parse_mode='Markdown')
        
        return products_checked, products_found, had_errors
    
    except Exception as e:
        logger.error(f"Error scanning category {category_name}: {e}")
        return products_checked, products_found, True


def scan_website() -> Tuple[int, int, int]:
    """Scan entire website for products below threshold"""
    categories = get_all_categories(config.get("base_url", ""))
    
    if not categories:
        logger.error("No categories found!")
        return 0, 0, 0
    
    logger.info(f"Starting parallel scan of {len(categories)} categories with {config.get('parallel_workers', 3)} threads...")
    
    total_checked = 0
    total_found = 0
    categories_with_errors = 0
    
    with ThreadPoolExecutor(max_workers=config.get("parallel_workers", 3)) as executor:
        future_to_category = {executor.submit(scan_category, cat): cat for cat in categories}
        
        completed = 0
        for future in as_completed(future_to_category):
            completed += 1
            try:
                checked, found, had_errors = future.result()
                total_checked += checked
                total_found += found
                if had_errors:
                    categories_with_errors += 1
                
                # Log progress periodically
                if completed % 5 == 0:
                    logger.info(f"Progress: {completed}/{len(categories)} categories ({total_checked} products checked)")
            
            except Exception as e:
                categories_with_errors += 1
                logger.error(f"Thread execution error: {e}")
        
        # Final progress
        logger.info(f"Progress: {completed}/{len(categories)} categories ({total_checked} products checked)")
    
    return total_checked, total_found, categories_with_errors


def main_loop():
    """Main monitoring loop"""
    logger.info("=" * 70)
    logger.info(f"Starting {config.get('site_name', 'Price')} Monitor")
    logger.info(f"Check interval: {config.get('check_interval', 60)} seconds ({config.get('check_interval', 60) // 60} minutes)")
    logger.info(f"Max price alert: {config.get('max_price', 10.0)}")
    logger.info(f"Parallel threads: {config.get('parallel_workers', 3)}")
    logger.info("=" * 70)
    
    load_seen_products()
    iteration = 0
    
    try:
        while True:
            iteration += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"Iteration #{iteration} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 70)
            
            start_time = time.time()
            total_checked, total_found, categories_with_errors = scan_website()
            execution_time = time.time() - start_time
            
            save_seen_products()
            
            logger.info(f"\nIteration #{iteration} Summary:")
            logger.info(f"  - Products checked: {total_checked}")
            logger.info(f"  - Products found (<= {config.get('max_price', 10.0)}): {total_found}")
            logger.info(f"  - Categories with errors: {categories_with_errors}")
            logger.info(f"  - Execution time: {execution_time:.2f} seconds")
            
            # Send Telegram summary only if products found OR errors occurred
            if total_found > 0 or categories_with_errors > 0:
                summary_msg = f"🔍 Scan #{iteration} Complete\n\n"
                summary_msg += f"✅ Products checked: {total_checked}\n"
                summary_msg += f"🎯 Found (<= {config.get('max_price', 10.0)}): {total_found}\n"
                if categories_with_errors > 0:
                    summary_msg += f"⚠️ Categories with errors: {categories_with_errors}\n"
                summary_msg += f"⏱️ Time: {execution_time:.1f}s"
                send_telegram_alert(summary_msg)
            
            # Wait for next iteration
            wait_time = config.get("check_interval", 60)
            logger.info(f"\nWaiting {wait_time} seconds until next check...\n")
            time.sleep(wait_time)
            
    except KeyboardInterrupt:
        raise


if __name__ == "__main__":
    # Check for reset flag
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            logger.info(f"Configuration reset. {CONFIG_FILE} deleted.")
        else:
            logger.info("No configuration file found.")
        sys.exit(0)
    
    # Load or create configuration
    loaded_config = load_config()
    
    if loaded_config is None:
        # First time setup
        config.update(interactive_setup())
    else:
        # Configuration exists
        config.update(loaded_config)
        logger.info(f"Loaded configuration from {CONFIG_FILE}")
        logger.info(f"Monitoring: {config.get('site_name', 'Unknown')} ({config.get('base_url', 'Unknown')})")
        
        # Ask if user wants to reconfigure
        print("\nConfiguration loaded. Press Enter to start monitoring...")
        print("(Run with --reset flag to reconfigure)\n")
        
        try:
            input()
        except KeyboardInterrupt:
            print("\nMonitoring cancelled.")
            sys.exit(0)
    
    # Start monitoring
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("\n\nMonitor stopped by user (Ctrl+C)")
        logger.info("Goodbye!")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
