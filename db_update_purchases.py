import os
import sys

# Change to the application directory to allow relative imports inside server
curr_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, curr_dir)

from server.database import engine, Base
from server.models import CoinPurchase

def reset_table():
    print("Dropping coin_purchases table...")
    CoinPurchase.__table__.drop(engine, checkfirst=True)
    print("Creating coin_purchases table with new schema...")
    CoinPurchase.__table__.create(engine, checkfirst=True)
    print("Done!")

if __name__ == "__main__":
    reset_table()
