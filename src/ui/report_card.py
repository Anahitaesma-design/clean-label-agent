# Premium A2UI Safety Report Card Generator
# Owner: ALI

from typing import Dict, Any, List

def render_card(verdict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a declarative A2UI (Agent-to-User Interface) payload matching
    the basic catalog schema for a premium, interactive safety report card.
    
    Args:
        verdict (dict): Product evaluation result including name, verdict, explanation, etc.
        
    Returns:
        dict: A2UI JSON payload with MIME type 'application/json+a2ui'.
    """
    product_name = verdict.get("product_name", "Unknown Product")
    safety_rating = str(verdict.get("verdict", "UNKNOWN")).upper().strip()
    explanation = verdict.get("explanation", "No safety evaluation details provided.")
    chemicals = verdict.get("chemicals_of_concern", [])
    sources = verdict.get("sources", [])
    alternative = verdict.get("alternative", {})
    
    # Define aesthetic color palettes and badges based on safety ratings (Tier 2 Aesthetic)
    if safety_rating == "SAFE":
        badge_color = "#10B981"  # Emerald Green
        badge_text = "🟢 SAFE - Clean Label Verified"
        card_theme = "success"
    elif safety_rating == "CAUTION":
        badge_color = "#F59E0B"  # Amber Yellow
        badge_text = "🟡 CAUTION - Moderate Risks Detected"
        card_theme = "warning"
    elif safety_rating == "UNSAFE":
        badge_color = "#EF4444"  # Coral/Crimson Red
        badge_text = "🔴 UNSAFE - Hazardous Additives Flagged"
        card_theme = "danger"
    else:
        badge_color = "#6B7280"  # Charcoal Gray
        badge_text = "⚪ UNKNOWN - Safety Not Verified"
        card_theme = "neutral"

    # Construct the core declarative A2UI card structure
    ui_payload = {
        "mime_type": "application/json+a2ui",
        "type": "Card",
        "props": {
            "id": f"card_{product_name.lower().replace(' ', '_')}",
            "title": f"Safety Scan: {product_name}",
            "theme": {
                "primary_color": badge_color,
                "card_style": "glassmorphism",
                "theme_mode": card_theme,
                "border_radius": "12px",
                "padding": "16px"
            },
            "children": [
                # 1. Safety Status Badge
                {
                    "type": "Badge",
                    "props": {
                        "text": badge_text,
                        "color": badge_color,
                        "text_color": "#FFFFFF",
                        "size": "large",
                        "margin": "0 0 12px 0"
                    }
                },
                # 2. Plain English Explanation
                {
                    "type": "Text",
                    "props": {
                        "content": explanation,
                        "style": "body-large",
                        "weight": "normal",
                        "line_height": "1.5"
                    }
                }
            ]
        }
    }
    
    # 3. Chemical list component (if present)
    if chemicals:
        ui_payload["props"]["children"].append({
            "type": "List",
            "props": {
                "header": "⚠️ Identified Chemicals of Concern",
                "items": [f"• {c}" for c in chemicals],
                "item_style": "danger-text"
            }
        })

    # 4. Collapsible Ingredients Breakdown with risk levels
    ingredients_breakdown = []
    # Try parsing raw ingredients or structured audit
    raw_ingredients = verdict.get("raw_ingredients", [])
    
    for ing in raw_ingredients:
        # Default safe ratings unless matched in known toxic list
        hazard = 1
        note = "Low risk ingredient"
        ing_lower = ing.lower()
        if "pfoa" in ing_lower or "red 3" in ing_lower:
            hazard = 9
            note = "High risk carcinogenic toxin."
        elif "ptfe" in ing_lower or "phenoxyethanol" in ing_lower:
            hazard = 5
            note = "Moderate hazard warning."
            
        ingredients_breakdown.append({
            "type": "Row",
            "props": {
                "title": ing,
                "value": f"Risk Score: {hazard}/10",
                "subtitle": note,
                "color_indicator": "#EF4444" if hazard > 7 else ("#F59E0B" if hazard > 3 else "#10B981")
            }
        })
        
    if ingredients_breakdown:
        ui_payload["props"]["children"].append({
            "type": "Collapsible",
            "props": {
                "header": f"🔍 View Ingredient Audit ({len(ingredients_breakdown)} items)",
                "is_collapsed": True,
                "children": ingredients_breakdown
            }
        })

    # 5. Buy-Safer-Alternative Action Button & Showcase
    if alternative and alternative.get("alternative_product"):
        alt_name = alternative.get("alternative_product")
        alt_link = alternative.get("buy_link", "#")
        ui_payload["props"]["children"].append({
            "type": "AlternativeBanner",
            "props": {
                "title": f"🌿 Recommended Alternative: {alt_name}",
                "description": "This alternative is free of flagged hazardous chemical additives.",
                "action_button": {
                    "type": "Button",
                    "props": {
                        "label": f"Buy {alt_name}",
                        "url": alt_link,
                        "style": "primary-button",
                        "color": "#10B981"
                    }
                }
            }
        })
    elif safety_rating == "UNSAFE":
        # Add fallback button to request alternative search
        ui_payload["props"]["children"].append({
            "type": "Button",
            "props": {
                "label": "🛒 Find Safer Alternative",
                "action": "find_alternative",
                "style": "secondary-button",
                "color": "#10B981"
            }
        })

    # 6. Citations
    if sources:
        citations = []
        for s in sources:
            citations.append({
                "type": "Link",
                "props": {
                    "label": f"🔗 {s.get('name')}",
                    "url": s.get('url')
                }
            })
        ui_payload["props"]["children"].append({
            "type": "Group",
            "props": {
                "header": "Sources & Citations",
                "children": citations
            }
        })

    return ui_payload
