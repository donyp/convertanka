import json
import os
import math

COINS_FILE = os.path.join(os.path.dirname(__file__), "coins.json")

def get_coin_data():
    if not os.path.exists(COINS_FILE):
        return {"balance": 100}
    try:
        with open(COINS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"balance": 100}

def save_coin_data(data):
    with open(COINS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_balance():
    return get_coin_data().get("balance", 0)

def deduct_coins(amount):
    data = get_coin_data()
    current = data.get("balance", 0)
    if current >= amount:
        data["balance"] = current - amount
        save_coin_data(data)
        return True, data["balance"]
    return False, current

def calculate_cost(page_count):
    if page_count <= 0: return 0
    # 1 coin for every 2 pages
    return math.ceil(page_count / 2)
