import requests
import base64
import datetime
import json
import os
from requests.auth import HTTPBasicAuth
from decouple import config

class MpesaSTKPush:
    def __init__(self):
        # M-Pesa Daraja API Credentials
        # You need to register on Safaricom Daraja Portal to get these
        self.consumer_key = "zmBmHC7RbNasyYmIm440LLI8LGlXvR7vZadWOKvlreXAl3AD " # Get from Daraja portal
        self.consumer_secret = "ndA7Zfxd3lX6W0rN9zC72y9aeqnfgcqZFtCeiGIhTCw4cZVvGOUMaTA57kyxd4F1" # Get from Daraja portal
        self.passkey = "Vujo6/FY7RKMy5PhQludvjuSP8pqv+Mj4cuSM0soFzqtgj1hWaRtFZTytec3refCn7fsWi+PPtF9gSHukF5qm+Vo7ww1CvGCDuCoVNq/ajOl3heRUvsQeBU1EDJTL7pxAJfKQ0v1ec+9o32HxFs7trLMcJ3ebjodQ9D8yexanfcfPgUzxoerYYrufPHy62frhYj+p/1k6LHy/jqejTtxrag9au2Yp/ZLAbLXOCJ0gNqxwLvnTetSmEsztApdg/Ce9VE/mLUF/lrxhFc1ZXbCLe/sdvYBkzONxL7s32/O1Nwv4M2nqx5qlketqwkLqWMW1AwTHLISYRKNLugjUnHu2A=="  # Get from Daraja portal
        self.shortcode = "1027027"  # Your Paybill number
        self.env = "sandbox"  # sandbox for testing, production for live
        
        # URLs
        if self.env == "sandbox":
            self.auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            self.stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
            self.query_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
            self.callback_url = "https://your-domain.com/api/mpesa-callback/"
        else:
            self.auth_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            self.stk_push_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
            self.query_url = "https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query"
            self.callback_url = "https://your-domain.com/api/mpesa-callback/"
    
    def get_access_token(self):
        """Get OAuth access token from M-Pesa"""
        try:
            response = requests.get(
                self.auth_url,
                auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret)
            )
            response.raise_for_status()
            result = response.json()
            print(f"✅ Access token obtained: {result['access_token'][:20]}...")
            return result['access_token']
        except Exception as e:
            print(f"❌ Error getting access token: {e}")
            return None
    
    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Send STK Push to customer's phone"""
        try:
            # Get access token
            access_token = self.get_access_token()
            if not access_token:
                return {"success": False, "message": "Failed to get access token"}
            
            # Format phone number (remove 0 and +254, add 254)
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif phone_number.startswith('+'):
                phone_number = phone_number[1:]
            
            # Generate timestamp
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Generate password
            password_str = f"{self.shortcode}{self.passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode('utf-8')
            
            # Prepare STK Push request
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'BusinessShortCode': self.shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': int(amount),
                'PartyA': phone_number,
                'PartyB': self.shortcode,
                'PhoneNumber': phone_number,
                'CallBackURL': self.callback_url,
                'AccountReference': account_reference,
                'TransactionDesc': transaction_desc
            }
            
            print(f"📤 Sending STK Push to {phone_number} for KES {amount}")
            
            # Send request
            response = requests.post(
                self.stk_push_url,
                headers=headers,
                json=payload
            )
            
            result = response.json()
            print(f"📥 Response: {result}")
            
            if response.status_code == 200 and result.get('ResponseCode') == '0':
                return {
                    "success": True,
                    "message": "STK Push sent successfully",
                    "checkout_request_id": result.get('CheckoutRequestID'),
                    "response_code": result.get('ResponseCode'),
                    "response_desc": result.get('ResponseDescription')
                }
            else:
                return {
                    "success": False,
                    "message": result.get('errorMessage', 'STK Push failed'),
                    "response_code": result.get('ResponseCode'),
                    "response_desc": result.get('ResponseDescription')
                }
                
        except Exception as e:
            print(f"❌ Error in STK Push: {e}")
            return {"success": False, "message": str(e)}
    
    def query_status(self, checkout_request_id):
        """Query STK Push transaction status"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {"success": False, "message": "Failed to get access token"}
            
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            password_str = f"{self.shortcode}{self.passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode('utf-8')
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'BusinessShortCode': self.shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'CheckoutRequestID': checkout_request_id
            }
            
            response = requests.post(self.query_url, headers=headers, json=payload)
            result = response.json()
            
            return {
                "success": result.get('ResponseCode') == '0',
                "result_code": result.get('ResultCode'),
                "result_desc": result.get('ResultDesc')
            }
            
        except Exception as e:
            print(f"❌ Error querying status: {e}")
            return {"success": False, "message": str(e)}

# Test function
if __name__ == "__main__":
    mpesa = MpesaSTKPush()
    # Test with your number
    result = mpesa.stk_push(
        phone_number="0110272019",
        amount=10,
        account_reference="TEST001",
        transaction_desc="Test Payment"
    )
    print(result)
