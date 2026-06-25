import sys
import os
import json
import subprocess

# Ensure we can import from current directory
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from margin_calculator import calculate_margins, calculate_breakeven_price, calculate_breakeven_sourcing_cost, compare_platforms

def run_team_db(query):
    try:
        result = subprocess.run(['team-db', query], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error running team-db: {e}")
        return []

def get_deals():
    return run_team_db("SELECT * FROM deals WHERE status = 'new'")

def get_fba_fee(product_name):
    name = product_name.lower()
    if 'soundbar' in name:
        return 12.50
    if 'earbuds' in name or 'controller' in name or 'screwdriver' in name:
        return 6.50
    return 5.00 # Default

def display_dashboard():
    deals = get_deals()
    if not deals:
        print("No new deals found.")
        return

    # Sort by estimated_margin_percent descending as requested
    deals.sort(key=lambda x: x['estimated_margin_percent'] if x['estimated_margin_percent'] else 0, reverse=True)

    print(f"{'Product Name':<40} {'Cost':<8} {'Market':<8} {'Platform':<15} {'Margin%':<8} {'Status'}")
    print("-" * 90)
    
    for deal in deals:
        margin_pct = deal['estimated_margin_percent'] if deal['estimated_margin_percent'] else 0
        print(f"{deal['product_name'][:39]:<40} ${deal['sourcing_cost']:<7.2f} ${deal['market_price']:<7.2f} {deal['platform']:<15} {margin_pct:<7.2f}% {deal['status']}")

    print("\n" + "=" * 155)
    print("LISTING PRICING ANALYSIS (Targeting 30% Net Margin)")
    print("=" * 155)
    print(f"{'Product':<35} {'Market':<10} {'Rec. Price':<12} {'Target Cost':<14} {'Amz Net':<10} {'eBay Net':<10} {'Better'} {'Notes'}")
    print("-" * 155)

    for deal in deals:
        platform_orig = str(deal['platform']).lower()
        is_amazon = 'amazon' in platform_orig
        
        fba_fee = get_fba_fee(deal['product_name'])
        
        # Recommended price: 2% undercut for speed
        rec_price = deal['market_price'] * 0.98
        
        # Target Sourcing Cost to hit 30% net margin at CURRENT market price (Amazon)
        target_cost_amz = calculate_breakeven_sourcing_cost(
            deal['market_price'],
            target_margin=0.30,
            platform='amazon',
            fulfillment_fee=fba_fee
        )

        # Compare Amazon vs eBay
        comp = compare_platforms(deal['sourcing_cost'], rec_price, fulfillment_fee=fba_fee)
        
        better_platform = comp['better'].upper()
        amz_net = comp['amazon']['net_profit']
        ebay_net = comp['ebay']['net_profit']

        notes = ""
        if 'marketplace' in platform_orig:
            results_mp = calculate_margins(deal['sourcing_cost'], rec_price, 'marketplace')
            target_cost_mp = calculate_breakeven_sourcing_cost(deal['market_price'], 0.30, 'marketplace')
            print(f"{deal['product_name'][:34]:<35} ${deal['market_price']:<9.2f} ${rec_price:<11.2f} ${target_cost_mp:<13.2f} {'-':<10} {'-':<10} {'MP':<6} MP Net: ${results_mp['net_profit']:.2f}")
        else:
            print(f"{deal['product_name'][:34]:<35} ${deal['market_price']:<9.2f} ${rec_price:<11.2f} ${target_cost_amz:<13.2f} ${amz_net:<9.2f} ${ebay_net:<9.2f} {better_platform:<6} {notes}")

if __name__ == "__main__":
    print("=== Margin Runner Deal Qualification Dashboard ===")
    display_dashboard()
