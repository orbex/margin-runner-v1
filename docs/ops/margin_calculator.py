import argparse

def calculate_amazon_fba_fees(sale_price, fulfillment_fee=0):
    # Lead's spec: 15% Amazon referral fee + FBA fulfillment fee
    return (sale_price * 0.15) + fulfillment_fee

def calculate_ebay_fees(sale_price):
    # Lead's spec: 13.25% + $0.30 fixed fee
    return (sale_price * 0.1325) + 0.30

def calculate_marketplace_fees(sale_price):
    # Facebook Marketplace local sales have 0 fees
    return 0.0

def calculate_margins(sourcing_cost, sale_price, platform, fulfillment_fee=0, shipping_cost=0, tax=0):
    if platform.lower() == 'amazon':
        fees = calculate_amazon_fba_fees(sale_price, fulfillment_fee)
    elif platform.lower() == 'ebay':
        fees = calculate_ebay_fees(sale_price)
    elif platform.lower() == 'marketplace' or platform.lower() == 'facebook marketplace':
        fees = calculate_marketplace_fees(sale_price)
    else:
        fees = 0.0
    
    # Lead's spec: 5% buffer on top of total costs
    subtotal_costs = sourcing_cost + fees + shipping_cost + tax
    buffer = subtotal_costs * 0.05
    total_costs = subtotal_costs + buffer
    
    net_profit = sale_price - total_costs
    margin_percent = (net_profit / sale_price) * 100 if sale_price > 0 else 0
    
    return {
        'sale_price': sale_price,
        'sourcing_cost': sourcing_cost,
        'fees': fees,
        'shipping_cost': shipping_cost,
        'tax': tax,
        'buffer': buffer,
        'net_profit': net_profit,
        'margin_percent': margin_percent
    }

def calculate_breakeven_price(sourcing_cost, target_margin=0.30, platform='amazon', fulfillment_fee=0, shipping_cost=0, tax=0):
    if platform.lower() == 'amazon':
        fee_percent = 0.15
        base_costs = sourcing_cost + fulfillment_fee + shipping_cost + tax
        fixed_fee = 0
    elif platform.lower() == 'ebay':
        fee_percent = 0.1325
        base_costs = sourcing_cost + shipping_cost + tax
        fixed_fee = 0.30
    else:
        fee_percent = 0.0
        base_costs = sourcing_cost + shipping_cost + tax
        fixed_fee = 0

    denominator = 1 - (1.05 * fee_percent) - target_margin
    if denominator <= 0:
        return 0
    
    return (1.05 * (base_costs + fixed_fee)) / denominator

def calculate_breakeven_sourcing_cost(market_price, target_margin=0.30, platform='amazon', fulfillment_fee=0, shipping_cost=0, tax=0):
    if platform.lower() == 'amazon':
        fees = calculate_amazon_fba_fees(market_price, fulfillment_fee)
    elif platform.lower() == 'ebay':
        fees = calculate_ebay_fees(market_price)
    else:
        fees = 0.0
        
    # target_margin * market_price = market_price - (sourcing_cost + fees + shipping + tax) * 1.10
    # (sourcing_cost + fees + shipping + tax) * 1.10 = market_price * (1 - target_margin)
    # sourcing_cost = [market_price * (1 - target_margin) / 1.10] - fees - shipping - tax
    
    target_total_cost = (market_price * (1 - target_margin)) / 1.05
    breakeven_sourcing = target_total_cost - fees - shipping_cost - tax
    return max(0, breakeven_sourcing)

def compare_platforms(sourcing_cost, market_price, fulfillment_fee=0):
    amazon = calculate_margins(sourcing_cost, market_price, 'amazon', fulfillment_fee=fulfillment_fee)
    ebay = calculate_margins(sourcing_cost, market_price, 'ebay')
    return {
        'amazon': amazon,
        'ebay': ebay,
        'better': 'amazon' if amazon['net_profit'] > ebay['net_profit'] else 'ebay'
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Calculate arbitrage margins.')
    parser.add_argument('--cost', type=float, required=True, help='Sourcing cost')
    parser.add_argument('--price', type=float, required=True, help='Expected sale price')
    parser.add_argument('--platform', type=str, choices=['amazon', 'ebay', 'marketplace'], required=True, help='Selling platform')
    parser.add_argument('--fulfillment', type=float, default=0.0, help='FBA fulfillment fee')
    parser.add_argument('--shipping', type=float, default=0.0, help='Estimated shipping cost')
    parser.add_argument('--tax', type=float, default=0.0, help='Estimated tax')

    args = parser.parse_args()

    results = calculate_margins(args.cost, args.price, args.platform, args.fulfillment, args.shipping, args.tax)
    
    print(f"--- Margin Calculation ({args.platform.capitalize()}) ---")
    print(f"Sale Price:     ${results['sale_price']:.2f}")
    print(f"Sourcing Cost:  ${results['sourcing_cost']:.2f}")
    print(f"Platform Fees:  ${results['fees']:.2f}")
    print(f"Shipping Cost:  ${results['shipping_cost']:.2f}")
    print(f"Tax:            ${results['tax']:.2f}")
    print(f"5% Buffer:     ${results['buffer']:.2f}")
    print(f"---------------------------")
    print(f"Net Profit:     ${results['net_profit']:.2f}")
    print(f"Margin %:       {results['margin_percent']:.2f}%")
    
    if args.platform == 'amazon':
        comparison = compare_platforms(args.cost, args.price, args.fulfillment)
        print(f"\n--- Platform Comparison ---")
        print(f"Amazon Net: ${comparison['amazon']['net_profit']:.2f}")
        print(f"eBay Net:   ${comparison['ebay']['net_profit']:.2f}")
        print(f"RECOMMENDATION: Use {comparison['better'].upper()}")

    if results['margin_percent'] >= 30:
        print("\nSTATUS: GOOD (Target met)")
    else:
        print("\nSTATUS: LOW MARGIN (Target 30%+)")
