# Pytest Suite for Clean Label Agent BDD Scenarios
# Owner: ALI

import os
import sys
import pytest
import asyncio
from unittest.mock import patch, AsyncMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["GEMINI_API_KEY"] = "mock-key-for-testing"
os.environ["AUTO_APPROVE"] = "true"  # Automatically approve Vibe Diff human audits in tests

from google.adk.agents import LlmAgent
from google.adk.events.event import Event as AdkEvent
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.genai import types

from src.agent import root_agent
from src.tools.mcp_client import get_product_data
from src.agents.toxicology import assess_toxicity
from src.commerce.safer_alt import find_safer_alternative
from src.ui.report_card import render_card
from src.checkpoints.vibe_diff import require_approval

# ==========================================
# 1. HELPER: WORKFLOW TEST RUNNER
# ==========================================

async def run_test_workflow(product_name: str, mock_llm_response: dict) -> dict:
    """
    Helper function to run the full workflow graph, mocking the LLM agent response.
    """
    async def mock_run_async(self, ctx, new_message=None):
        yield AdkEvent(
            state=mock_llm_response,
            output=mock_llm_response
        )
        
    with patch.object(LlmAgent, "run_async", mock_run_async):
        app = App(name="test_app", root_agent=root_agent)
        runner = InMemoryRunner(app=app)
        session = await runner.session_service.create_session(app_name="test_app", user_id="test_user")
        
        user_msg = types.Content(
            role="user", 
            parts=[types.Part.from_text(text=f"Is {product_name} safe?")]
        )
        
        final_verdict = {}
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=user_msg
        ):
            if hasattr(event, "output") and event.output:
                final_verdict = event.output
                
        # If the verdict was not emitted as output (e.g. paused at HITL), retrieve from state
        if not final_verdict:
            state = await runner.session_service.get_state(session.id)
            final_verdict = {
                "product_name": state.get("product_name"),
                "verdict": state.get("verdict"),
                "explanation": state.get("explanation"),
                "chemicals_of_concern": state.get("chemicals_of_concern"),
                "sources": state.get("sources"),
                "alternative": state.get("alternative")
            }
            
        return final_verdict


# ==========================================
# 2. PYTEST CASES (Gherkin Scenarios)
# ==========================================

@pytest.mark.asyncio
async def test_scenario_1_unsafe_food_additive():
    """
    Scenario 1: Scan a food item with a banned additive (Sparkling Grape Soda).
    Given the product contains Red 3, it must evaluate to UNSAFE and flag Red 3.
    """
    # Verify the MCP client pulls correct ingredients
    raw_data = get_product_data("Sparkling Grape Soda")
    assert "Red 3" in raw_data["ingredients"]
    
    # Verify toxicology flags it
    tox_report = assess_toxicity(raw_data["ingredients"])
    assert tox_report["Red 3"]["hazard_level"] >= 9
    
    mock_llm = {
        "product_name": "Sparkling Grape Soda",
        "verdict": "UNSAFE",
        "explanation": "Contains Red 3, which is linked to thyroid tumors and banned by EFSA.",
        "chemicals_of_concern": ["Red 3"],
        "sources": [{"name": "Open Food Facts", "url": "https://world.openfoodfacts.org/product/sparkling-grape-soda"}]
    }
    
    result = await run_test_workflow("Sparkling Grape Soda", mock_llm)
    assert result["verdict"] == "UNSAFE"
    assert "Red 3" in result["chemicals_of_concern"]
    assert len(result["sources"]) > 0


@pytest.mark.asyncio
async def test_scenario_2_unsafe_cookware_with_alternative():
    """
    Scenario 2: Scan a non-stick pan with PFOA and suggest ceramic alternative.
    """
    raw_data = get_product_data("Classic Teflon Pan")
    assert "PFOA" in raw_data["ingredients"]
    
    # Verify commerce module maps it to ceramic skillet
    alt_data = find_safer_alternative("Classic Teflon Pan")
    assert "Ceramic" in alt_data["alternative_product"]
    assert "buy_link" in alt_data
    
    mock_llm = {
        "product_name": "Classic Teflon Pan",
        "verdict": "UNSAFE",
        "explanation": "Contains PFOA which is listed under CA Prop 65 as toxic.",
        "chemicals_of_concern": ["PFOA"],
        "sources": [{"name": "EWG Cookware", "url": "https://www.ewg.org/cookware/classic-teflon-pan"}]
    }
    
    result = await run_test_workflow("Classic Teflon Pan", mock_llm)
    assert result["verdict"] == "UNSAFE"
    assert "PFOA" in result["chemicals_of_concern"]


@pytest.mark.asyncio
async def test_scenario_3_clean_skincare_cream():
    """
    Scenario 3: Scan a clean skincare cream (Gentle Oats Moisturizer).
    All ingredients should be low hazard and verdict is SAFE.
    """
    raw_data = get_product_data("Gentle Oats Moisturizer")
    tox_report = assess_toxicity(raw_data["ingredients"])
    
    # Check that all ingredients are low hazard
    for ing, details in tox_report.items():
        assert details["hazard_level"] <= 2
        
    mock_llm = {
        "product_name": "Gentle Oats Moisturizer",
        "verdict": "SAFE",
        "explanation": "All ingredients are clean and safe.",
        "chemicals_of_concern": [],
        "sources": [{"name": "EWG Skin Deep", "url": "https://www.ewg.org/skindeep/gentle-oats-moisturizer"}]
    }
    
    result = await run_test_workflow("Gentle Oats Moisturizer", mock_llm)
    assert result["verdict"] == "SAFE"
    assert len(result["chemicals_of_concern"]) == 0


@pytest.mark.asyncio
async def test_scenario_4_product_not_found_fallback():
    """
    Scenario 4: Product not found in any database (Super-Gizmo Shiny Paste).
    Result must fallback gracefully to UNKNOWN.
    """
    raw_data = get_product_data("Super-Gizmo Shiny Paste")
    assert len(raw_data["ingredients"]) == 0
    assert raw_data["database"] == "Unknown Database"
    
    mock_llm = {
        "product_name": "Super-Gizmo Shiny Paste",
        "verdict": "UNKNOWN",
        "explanation": "Product could not be found in safety databases.",
        "chemicals_of_concern": [],
        "sources": []
    }
    
    result = await run_test_workflow("Super-Gizmo Shiny Paste", mock_llm)
    assert result["verdict"] == "UNKNOWN"
    assert "could not be found" in result["explanation"]


@pytest.mark.asyncio
async def test_scenario_5_high_risk_vibe_diff_approval():
    """
    Scenario 5: High-risk baby product requires Vibe Diff audit.
    """
    raw_data = get_product_data("Baby Sleepy Lotion")
    assert "Phenoxyethanol" in raw_data["ingredients"]
    
    # Verify vibe diff checkpoint approve runs
    verdict = {
        "product_name": "Baby Sleepy Lotion",
        "verdict": "CAUTION",
        "explanation": "Contains Phenoxyethanol, restricted in baby lotions.",
        "chemicals_of_concern": ["Phenoxyethanol"]
    }
    approved = require_approval(verdict, raw_data)
    assert approved is True
    
    mock_llm = {
        "product_name": "Baby Sleepy Lotion",
        "verdict": "CAUTION",
        "explanation": "Contains Phenoxyethanol.",
        "chemicals_of_concern": ["Phenoxyethanol"],
        "sources": [{"name": "EWG Skin Deep", "url": "https://www.ewg.org/skindeep/baby-sleepy-lotion"}]
    }
    
    result = await run_test_workflow("Baby Sleepy Lotion", mock_llm)
    assert result["verdict"] == "CAUTION"
    assert "Phenoxyethanol" in result["chemicals_of_concern"]


@pytest.mark.asyncio
async def test_scenario_6_source_citation_mandatory():
    """
    Scenario 6: Every verdict must cite at least one source with URL.
    """
    # Test safe product sources
    raw_data = get_product_data("Organic Apple Cider Vinegar")
    
    mock_llm = {
        "product_name": "Organic Apple Cider Vinegar",
        "verdict": "SAFE",
        "explanation": "Pure organic apple cider vinegar with water. Safe.",
        "chemicals_of_concern": [],
        "sources": [{"name": "Open Food Facts", "url": "https://world.openfoodfacts.org/product/organic-apple-cider-vinegar"}]
    }
    
    result = await run_test_workflow("Organic Apple Cider Vinegar", mock_llm)
    assert len(result["sources"]) > 0
    assert result["sources"][0]["name"] == "Open Food Facts"
    assert result["sources"][0]["url"].startswith("http")
