import argparse
import subprocess
import json
import os

# Import calculate_margins from the other file
import sys
sys.path.append('/home/agent-operations-agent')
from margin_calculator import calculate_margins

def run_team_db(query):
    try:
        result = subprocess.run(['team-db', query], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running team-db: {e.stderr}")
        return None

def add_deal(name, cost, price, platform, url, agent_id):
    margins = calculate_margins(cost, price, platform)
    
    query = f"""
    INSERT INTO deals (
        product_name, sourcing_cost, market_price, platform, 
        estimated_fees, estimated_margin, estimated_margin_percent, 
        source_url, sourcing_agent_id
    ) VALUES (
        '{name}', {cost}, {price}, '{platform}', 
        {margins['fees']}, {margins['net_profit']}, {margins['margin_percent']}, 
        '{url}', '{agent_id}'
    )
    """
    
    run_team_db(query)
    print(f"Successfully added deal: {name}")
    print(f"Estimated Profit: ${margins['net_profit']:.2f} ({margins['margin_percent']:.2f}%)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add a new deal to the database.')
    parser.add_argument('--name', type=str, required=True, help='Product name')
    parser.add_argument('--cost', type=float, required=True, help='Sourcing cost')
    parser.add_argument('--price', type=float, required=True, help='Market price')
    parser.add_argument('--platform', type=str, choices=['amazon', 'ebay', 'marketplace'], required=True, help='Platform')
    parser.add_argument('--url', type=str, default='', help='Source URL')
    parser.add_argument('--agent', type=str, default='agent-sourcing-agent', help='Agent ID')

    args = parser.parse_args()
    
    add_deal(args.name, args.cost, args.price, args.platform, args.url, args.agent)
