import subprocess
import json
from datetime import datetime, timedelta

def run_team_db(query):
    try:
        result = subprocess.run(['team-db', query], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running team-db: {e.stderr}")
        return None

def generate_report():
    # 1. Total Profit this week
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    profit_query = f"SELECT SUM(net_profit) as total_profit FROM sales WHERE sale_date >= '{one_week_ago}'"
    profit_data = run_team_db(profit_query)
    total_profit = profit_data[0]['total_profit'] if profit_data and profit_data[0]['total_profit'] else 0.0
    
    # 2. Inventory Stats
    inv_query = "SELECT COUNT(*) as count, SUM(purchase_price) as total_value FROM inventory WHERE status != 'sold'"
    inv_data = run_team_db(inv_query)
    inv_count = inv_data[0]['count'] if inv_data else 0
    inv_value = inv_data[0]['total_value'] if inv_data and inv_data[0]['total_value'] else 0.0
    
    # 3. Deal Pipeline
    deal_query = "SELECT COUNT(*) as count FROM deals WHERE status = 'new'"
    deal_data = run_team_db(deal_query)
    new_deals = deal_data[0]['count'] if deal_data else 0

    print("=== Margin Runner KPI Report ===")
    print(f"Weekly Net Profit:  ${total_profit:,.2f} / $2,000.00 ({(total_profit/2000)*100:.1f}%)")
    print(f"Active Inventory:   {inv_count} items")
    print(f"Inventory Value:    ${inv_value:,.2f}")
    print(f"New Deals Found:    {new_deals}")
    print("================================")

if __name__ == "__main__":
    generate_report()
