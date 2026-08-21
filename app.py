# app.py - Interactive version

import json
from datetime import datetime

pending_trades = []
completed_trades = []

def create_trade(producer_name, consumer_name, watt_hours):
    disco_price_per_kwh = 160
    p2p_price = disco_price_per_kwh * 0.85
    total_price = (watt_hours / 1000) * p2p_price
    
    trade = {
        "trade_id": f"TRADE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "producer": producer_name,
        "consumer": consumer_name,
        "watt_hours": watt_hours,
        "price_per_kwh": round(p2p_price, 2),
        "total_price": round(total_price, 2),
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    pending_trades.append(trade)
    print(f"✅ Trade created: {trade['consumer']} buys {watt_hours/1000}kWh from {trade['producer']}")
    print(f"   Price: ₦{trade['total_price']} (₦{trade['price_per_kwh']}/kWh)")
    return trade

def validate_delivery(trade_id):
    for t in pending_trades:
        if t['trade_id'] == trade_id:
            import random
            delivered = random.choice([True, True, True, False])
            if delivered:
                t['status'] = 'completed'
                pending_trades.remove(t)
                completed_trades.append(t)
                print(f"✅ Trade {trade_id} COMPLETED!")
                return True
            else:
                t['status'] = 'failed'
                print(f"❌ Trade {trade_id} FAILED.")
                return False
    print("❌ Trade not found")
    return False

def list_trades():
    print("\n" + "="*50)
    print("📊 ALL TRADES")
    if pending_trades:
        print("\n🟡 PENDING:")
        for t in pending_trades:
            print(f"   {t['trade_id']}: {t['consumer']} ← {t['producer']} ({t['watt_hours']/1000}kWh, ₦{t['total_price']})")
    if completed_trades:
        print("\n🟢 COMPLETED:")
        for t in completed_trades:
            print(f"   {t['trade_id']}: {t['consumer']} ← {t['producer']} ({t['watt_hours']/1000}kWh, ₦{t['total_price']})")

def show_help():
    print("\n" + "="*50)
    print("📖 COMMANDS")
    print("   create [producer] [consumer] [watt_hours]")
    print("   validate [trade_id]")
    print("   list")
    print("   help")
    print("   exit")
    print("="*50)

def run_app():
    print("🏠 OFFGRIDPRO - Interactive Demo")
    print("Type 'help' for commands")
    
    while True:
        command = input("\n> ").strip().split()
        
        if not command:
            continue
            
        if command[0] == "exit":
            break
            
        elif command[0] == "help":
            show_help()
            
        elif command[0] == "list":
            list_trades()
            
        elif command[0] == "create":
            if len(command) < 4:
                print("Usage: create [producer] [consumer] [watt_hours]")
                continue
            try:
                watt_hours = float(command[3])
                create_trade(command[1], command[2], watt_hours)
            except:
                print("Invalid watt_hours. Use a number like 3000")
                
        elif command[0] == "validate":
            if len(command) < 2:
                print("Usage: validate [trade_id]")
                continue
            validate_delivery(command[1])
            
        else:
            print("Unknown command. Type 'help'")

if __name__ == "__main__":
    run_app()
