from flask import Flask, request, redirect, jsonify
import requests
import threading
import mysql.connector
import time

# Cryptomus credentials
API_KEY = ""
MERCHANT_ID = ""
CRYPTO_API_URL = "https://api.cryptomus.com/v1"

def create_payment(amount, comment, expire):
    """
    Create a payment via Cryptomus API.
    """
    url = f"{CRYPTO_API_URL}/payment"
    headers = {
        "Content-Type": "application/json",
        "Merchant": MERCHANT_ID,
        "Authorization": API_KEY,
    }
    data = {
        "amount": str(amount),  # Amount as a string to avoid issues
        "currency": "RUB",  # Adjust as per your needs
        "order_id": comment,
        "expire": expire,  # Expiration in seconds
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        if "result" in response_data:
            return response_data["result"]
        else:
            print(f"Error in response: {response_data}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error creating payment: {e}")
        return None


def check_payment_status(payment_uuid):
    """
    Check payment status via Cryptomus.
    """
    url = f"{CRYPTO_API_URL}/payment/info"
    headers = {
        "Content-Type": "application/json",
        "Merchant": MERCHANT_ID,
        "Authorization": API_KEY,
    }
    data = {"uuid": payment_uuid}

    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        result = response.json().get("result")
        return result.get("status") == "paid"
    else:
        print(f"Error checking payment status: {response.text}")
        return False

def check_payment_status_in_background(payment_uuid, userid, amount):
    timeout = 1830  # Wait time in seconds
    interval = 10  # Check interval
    elapsed_time = 0
    success = False

    while elapsed_time < timeout:
        success = check_payment_status(payment_uuid)
        if success:
            user = getuser(userid)
            user_id, name, email, server_limit, credits = user
            print('Payment successful!')

            con = mysql.connector.connect(
                host="127.0.0.1",
                user="controlpaneluser",
                password="password", # Replace with your db password
                database="controlpanel",
                charset="utf8mb4",
                collation="utf8mb4_general_ci"
            )

            cur = con.cursor()
            cur.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
            credits = cur.fetchone()[0]

            newcredits = int(credits) + int(amount)
            cur.execute("UPDATE users SET credits = %s WHERE id = %s", (newcredits, user_id))
            cur.execute("UPDATE users SET role = 'client' WHERE id = %s", (user_id,))
            cur.execute("UPDATE users SET server_limit = 50 WHERE id = %s", (user_id,))
            con.commit()
            con.close()
            break

        time.sleep(interval)
        elapsed_time += interval

    if not success:
        print("Payment was not completed within the allotted time.")

def getuser(user_id):
    url = f'https://domain.com/api/users/{user_id}'
    headers = {
        'Authorization': 'Bearer YOUR_BEARER_TOKEN', # Replace with your real API token
        'Accept': 'application/json'
    }
    
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data:
            name = data['name']
            role = data['role']
            email = data['email']
            server_limit = data['server_limit']
            credits = data['credits']
            return user_id, name, email, server_limit, credits
    else:
        print(f"Error fetching user: {response.status_code}")

app = Flask(__name__)

@app.route('/process', methods=['GET'])
def process_data():
    userid = request.args.get('id')
    amount = request.args.get('amount')
    
    if not userid or not amount:
        return jsonify({'error': 'id and amount parameters are required!'}), 400
    
    try:
        amount = int(amount)
    except ValueError:
        return jsonify({'error': 'Invalid amount value!'}), 400
    
    comment = 'Balance Top Up'
    expire = 30
    
    # Create payment via Cryptomus
    payment_data = create_payment(amount, comment, expire)
    print('Payment from', userid, amount)

    if payment_data and 'url' in payment_data:
        # Start background payment status check
        payment_uuid = payment_data['uuid']
        threading.Thread(target=check_payment_status_in_background, args=(payment_uuid, userid, amount)).start()
        
        # Redirect user to payment page
        return redirect(payment_data['url'])

    return jsonify({'error': 'Payment creation error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1488, debug=True)
