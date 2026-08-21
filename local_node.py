# local_node.py - The brain of your system
# This is a SIMPLE version that runs on your laptop to test the concept

import json
from datetime import datetime

# This is your "database" - a simple list of trades
pending_trades = []
completed_trades = []

def create_trade(producer_name, consumer_name, watt_hours):
    """Step 1: Create a trade between a producer and consumer"""
    
    # Calculate the price (15% below DisCo tariff)
    disco_price_per_kwh = 160  # Enugu Band A rate
    p2p_price = disco_price_per_kwh * 0.85  # 15% discount
    
    total_price = (watt_hours / 1000) * p2p_price
    
    # Create the trade record
    trade = {
        "trade_id": f"TRADE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "producer": producer_name,
        "consumer": consumer_name,
        "watt_hours": watt_hours,
        "price_per_kwh": p2p_price,
        "total_price": round(total_price, 2),
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    pending_trades.append(trade)
    print(f"✅ Trade created: {trade['consumer']} buys {watt_hours/1000}kWh from {trade['producer']}")
    print(f"   Price: ₦{trade['total_price']} (₦{trade['price_per_kwh']}/kWh)")
    print(f"   Trade ID: {trade['trade_id']}")
    
    return trade

def validate_delivery(trade_id):
    """Step 2: Check if the power was actually delivered"""
    
    # Find the trade
    trade = None
    for t in pending_trades:
        if t['trade_id'] == trade_id:
            trade = t
            break
    
    if not trade:
        print("❌ Trade not found")
        return False
    
    # For MVP (Minimum Viable Product), we SIMULATE the validation
    # In real life, this would check the smart meters
    import random
    delivered = random.choice([True, True, True, False])  # 75% success rate
    
    if delivered:
        trade['status'] = 'completed'
        pending_trades.remove(trade)
        completed_trades.append(trade)
        print(f"✅ Trade {trade_id} COMPLETED! Power delivered successfully.")
        print(f"   Consumer paid ₦{trade['total_price']}")
        print(f"   Producer receives ₦{trade['total_price'] * 0.85}")
        print(f"   Platform fee: ₦{trade['total_price'] * 0.05}")
        print(f"   DisCo fee: ₦{trade['total_price'] * 0.10}")
        return True
    else:
        trade['status'] = 'failed'
        print(f"❌ Trade {trade_id} FAILED. Consumer refunded.")
        return False

def show_all_trades():
    """Step 3: See all trades that have happened"""
    
    print("\n" + "="*50)
    print("📊 ALL TRADES")
    print("="*50)
    
    if not pending_trades and not completed_trades:
        print("No trades yet.")
        return
    
    if pending_trades:
        print("\n🟡 PENDING TRADES:")
        for t in pending_trades:
            print(f"   {t['trade_id']}: {t['consumer']} ← {t['producer']} ({t['watt_hours']/1000}kWh, ₦{t['total_price']})")
    
    if completed_trades:
        print("\n🟢 COMPLETED TRADES:")
        for t in completed_trades:
            print(f"   {t['trade_id']}: {t['consumer']} ← {t['producer']} ({t['watt_hours']/1000}kWh, ₦{t['total_price']})")

# ============================================
# TEST YOUR SYSTEM!
# ============================================

if __name__ == "__main__":
    print("🏠 OFFGRIDPRO - Local Node Simulator")
    print("="*50)
    
    # Create some trades
    create_trade("Mr. Ade (Solar on Adebayo St)", "Mama Bose (Shop on Adebayo St)", 3000)  # 3kWh
    create_trade("Chief Okonkwo (GRA Enugu)", "Mr. Emeka (Phone Charging Center)", 2000)   # 2kWh
    
    # Show all trades
    show_all_trades()
    
    # Validate one trade
    print("\n" + "="*50)
    print("🔍 VALIDATING TRADE...")
    print("="*50)
    if pending_trades:
        validate_delivery(pending_trades[0]['trade_id'])
    
    # Show updated trades
    show_all_trades()
