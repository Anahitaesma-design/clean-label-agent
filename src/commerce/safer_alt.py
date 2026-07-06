# AP2/UCP Commerce Safer Alternative Finder & Purchase Preparer
# Owner: ALI

from typing import Dict, Any

def find_safer_alternative(unsafe_product: str, category: str = None) -> Dict[str, Any]:
    """
    Uses UCP (Universal Commerce Protocol) simulation to search for a clean product
    alternative and AP2 (Agent Purchase Protocol) to prepare a pre-filled checkout link.
    
    Args:
        unsafe_product (str): Name of the unsafe product evaluated.
        category (str): Optional category of the product (food, skincare, cookware, cleaning).
        
    Returns:
        dict: Alternative product details containing names, retailer, and AP2 checkout link.
    """
    product_lower = unsafe_product.lower().strip()
    category_lower = category.lower().strip() if category else ""
    
    # If category is not provided, try to infer it from the product name keywords
    if not category_lower:
        if any(w in product_lower for w in ["pan", "skillet", "cookware", "pot", "teflon", "frying"]):
            category_lower = "cookware"
        elif any(w in product_lower for w in ["lotion", "cream", "moisturizer", "vanicream", "oats", "sunscreen", "spf", "sun block"]):
            category_lower = "skincare"
        elif any(w in product_lower for w in ["spray", "cleaner", "cleaning", "detergent", "soap"]):
            category_lower = "cleaning"
        else:
            category_lower = "food"

    alternative = None

    # Sunscreen subtype (matches category sunscreen or sunscreen/spf in name)
    if "sunscreen" in product_lower or "spf" in product_lower or "sun block" in product_lower:
        alternative = {
            "alternative_product": "Badger Mineral Sunscreen SPF 30",
            "retailer": "Target",
            "price": 15.99,
            "sku": "BAD-SUN-30",
            "buy_link": "https://cart.example.com/checkout?sku=BAD-SUN-30&partner=ap2"
        }
    # Pizza subtype
    elif "pizza" in product_lower or "pepperoni" in product_lower or "supreme" in product_lower:
        alternative = {
            "alternative_product": "Amy's Kitchen Organic Cheese Pizza",
            "retailer": "Whole Foods Market",
            "price": 8.99,
            "sku": "AMY-PIZ-100",
            "buy_link": "https://cart.example.com/checkout?sku=AMY-PIZ-100&partner=ap2"
        }
    # Cookware subtype
    elif category_lower == "cookware" or any(w in product_lower for w in ["pan", "skillet", "cookware", "pot", "teflon", "frying"]):
        alternative = {
            "alternative_product": "10-inch Ceramic Non-Stick Skillet",
            "retailer": "Target",
            "price": 29.99,
            "sku": "CER-PAN-10",
            "buy_link": "https://cart.example.com/checkout?sku=CER-PAN-10&partner=ap2"
        }
    # Skincare / lotion subtype
    elif category_lower in ["skincare", "cosmetic", "personal care"] or any(w in product_lower for w in ["lotion", "cream", "moisturizer", "vanicream", "oats"]):
        alternative = {
            "alternative_product": "Gentle Oats Moisturizer",
            "retailer": "CVS Pharmacy",
            "price": 12.49,
            "sku": "OAT-MOIST-200",
            "buy_link": "https://cart.example.com/checkout?sku=OAT-MOIST-200&partner=ap2"
        }
    # Cleaning subtype
    elif category_lower in ["cleaning", "household"] or any(w in product_lower for w in ["spray", "cleaner", "cleaning", "detergent", "soap"]):
        alternative = {
            "alternative_product": "Seventh Generation Free & Clear All-Purpose Cleaner",
            "retailer": "Whole Foods Market",
            "price": 6.49,
            "sku": "SEV-CLN-300",
            "buy_link": "https://cart.example.com/checkout?sku=SEV-CLN-300&partner=ap2"
        }
    # Beverage / Soda subtype
    elif "soda" in product_lower or "beverage" in product_lower or "grape" in product_lower or "cola" in product_lower:
        alternative = {
            "alternative_product": "Organic Apple Cider Vinegar",
            "retailer": "Whole Foods Market",
            "price": 5.99,
            "sku": "ACV-ORG-500",
            "buy_link": "https://cart.example.com/checkout?sku=ACV-ORG-500&partner=ap2"
        }

    if alternative:
        print(f"[UCP SEARCH] Found cleaner alternative for '{unsafe_product}': {alternative['alternative_product']}")
        print(f"[AP2 CHECKOUT] Pre-filled checkout link generated: {alternative['buy_link']}")
        return alternative

    # Default fallback when no safer alternative is found for this product type
    no_alt = {
        "alternative_product": "No safer alternative found for this product type",
        "retailer": "N/A",
        "price": 0.0,
        "sku": "N/A",
        "buy_link": ""
    }
    print(f"[UCP SEARCH] No specific alternative found for product: '{unsafe_product}' (category: '{category_lower}')")
    return no_alt
