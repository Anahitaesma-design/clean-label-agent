# LLM-as-Judge Evaluation Suite
# Owner: ALI

import os
import sys
import json
import pytest
import asyncio
from typing import Dict, Any

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AUTO_APPROVE"] = "true"  # Automatically approve Vibe Diff human audits in eval runs

from google.genai import Client
from google.genai import types
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from src.agent import root_agent

# Initialize standard Gemini Client using ADK setup key
client = Client()

async def run_product_through_agent(barcode: str, name: str) -> Dict[str, Any]:
    """
    Runs a query (barcode first, falling back to name if barcode fails or is empty)
    through the live Clean Label ADK workflow graph.
    """
    app = App(name="eval_app", root_agent=root_agent)
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(app_name="eval_app", user_id="eval_user")
    
    # 1. Decide on the initial query input
    input_value = barcode.strip() if barcode and barcode.strip() else name.strip()
    use_fallback = False
    
    # Run the live stream to execute the graph
    async def execute_query(query_text: str) -> Dict[str, Any]:
        user_msg = types.Content(role="user", parts=[types.Part.from_text(text=query_text)])
        # Run workflow stream
        async for event in runner.run_async(user_id="eval_user", session_id=session.id, new_message=user_msg):
            pass
        # Retrieve final safety facts directly from session state (bypassing A2UI payload formatting)
        session_obj = await runner.session_service.get_session(app_name="eval_app", user_id="eval_user", session_id=session.id)
        state = session_obj.state
        res = {
            "product_name": state.get("product_name"),
            "category": state.get("category"),
            "verdict": state.get("verdict"),
            "explanation": state.get("explanation"),
            "chemicals_of_concern": state.get("chemicals_of_concern"),
            "sources": state.get("sources"),
            "ingredients": state.get("ingredients")
        }
        return res

    result = await execute_query(input_value)
    
    # 2. Check if barcode failed to resolve (verdict UNKNOWN or ingredients empty)
    # and we have a fallback name to try
    if barcode and barcode.strip() and name:
        is_unknown = result.get("verdict") == "UNKNOWN"
        explanation = str(result.get("explanation", "")).lower()
        no_ingredients = not result.get("ingredients")
        
        if is_unknown or "could not be found" in explanation or no_ingredients:
            print(f"[EVAL RUN] Barcode '{barcode}' failed to resolve. Retrying with fallback name: '{name}'...")
            # Recreate session for fresh name-based run
            session = await runner.session_service.create_session(app_name="eval_app", user_id="eval_user")
            result = await execute_query(name)
            use_fallback = True
            
    result["input_used"] = name if (use_fallback or not barcode) else barcode
    result["barcode_failed"] = use_fallback
    return result

async def run_product_through_agent_with_retry(barcode: str, name: str) -> Dict[str, Any]:
    """
    Wrapper to run case execution with exponential backoff retries to handle transient 503 errors.
    """
    import random
    max_retries = 6
    for attempt in range(max_retries):
        try:
            return await run_product_through_agent(barcode, name)
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff with jitter: 4s, 8s, 16s, 32s, 64s
                wait_time = (2 ** (attempt + 2)) + random.uniform(0, 3)
                print(f"[EVAL RETRY] Attempt {attempt+1}/{max_retries} failed: {e}. Retrying in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
            else:
                raise e

def evaluate_llm_score(case: Dict[str, Any], agent_output: Dict[str, Any]) -> float:
    """
    Uses Gemini LLM-as-Judge to score the agent safety explanation against the rubrics.
    Implements ordering bias neutralization by running evaluation twice with outputs swapped,
    then averaging the scores.
    """
    rubric = """
    Evaluate this product safety report card against the following quality rubrics:
    1. Verdict Match: Check if the actual verdict matches the expected verdict.
       - Expected verdict is: {expected_verdict}
       - Actual verdict is: {actual_verdict}
       - Rule: If expected is SAFE or UNSAFE, they must match exactly. If expected is CAUTION, then a verdict of SAFE or CAUTION is acceptable.
    2. Sources: The explanation must cite at least one real external database source with a URL (e.g. PubChem GHS, Food Safety Specialist rules, EWG Skin Deep, Open Food/Beauty Facts).
    3. Tone: The explanation must NOT be alarmist. It must clearly distinguish the raw-material industrial handling hazard from the actual finished product consumer risk.
    
    Provide a score between 1 and 10 based on these criteria.
    Format your response as a JSON block:
    {{"score": <integer_score_1_to_10>, "rationale": "<brief_reasoning>"}}
    """
    
    prompt = rubric.format(
        expected_verdict=case["expected_verdict"],
        actual_verdict=agent_output.get("verdict", "UNKNOWN")
    )
    
    input_text = f"""
    Product Name: {agent_output.get('product_name')}
    Report Card: {json.dumps(agent_output)}
    """
    
    # Order A: Prompt first, then input
    prompt_a = f"{prompt}\n\nInput Report Card:\n{input_text}"
    # Order B: Input first, then prompt
    prompt_b = f"Input Report Card:\n{input_text}\n\n{prompt}"
    
    def get_score_from_llm(full_prompt: str) -> float:
        import random
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                data = json.loads(response.text)
                return float(data.get("score", 5.0))
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** (attempt + 1)) + random.uniform(0, 2)
                    print(f"[JUDGE RETRY] Attempt {attempt+1}/{max_retries} failed: {e}. Retrying in {wait_time:.1f}s...")
                    import time
                    time.sleep(wait_time)
                else:
                    print(f"[JUDGE ERROR] Max retries exceeded: {e}")
                    return 5.0
            
    score_a = get_score_from_llm(prompt_a)
    score_b = get_score_from_llm(prompt_b)
    
    # Neutralize ordering bias by averaging the two runs
    return (score_a + score_b) / 2.0

@pytest.mark.asyncio
async def test_llm_as_judge_evaluation_suite():
    """
    Loads cases from golden_dataset.json, executes them through the live agent,
    scores each case using LLM-as-judge, and prints a final validation summary table.
    """
    golden_path = os.path.join(os.path.dirname(__file__), "golden_dataset.json")
    with open(golden_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
        
    print(f"\nStarting LLM-as-Judge Evaluation Suite across {len(cases)} cases...")
    
    results = []
    barcodes_failed = []
    passed_count = 0
    
    for case in cases:
        case_id = case["case_id"]
        print(f"\nEvaluating Case: {case_id} ({case['input_name']})...")
        
        # Run live workflow with retry support
        output = await run_product_through_agent_with_retry(case["input_barcode"], case["input_name"])
        
        # Score output using LLM-as-Judge
        score = evaluate_llm_score(case, output)
        
        # Determine PASS/FAIL (we consider a score of 7.0 or higher a PASS)
        is_pass = score >= 7.0
        if is_pass:
            passed_count += 1
            
        category_correct = str(case["category"]).lower() in str(output.get("category", "")).lower()
        
        results.append({
            "case_id": case_id,
            "input_used": output.get("input_used"),
            "expected_verdict": case["expected_verdict"],
            "actual_verdict": output.get("verdict"),
            "category_correct": "YES" if category_correct else "NO",
            "score": score,
            "status": "PASS" if is_pass else "FAIL"
        })
        
        if output.get("barcode_failed"):
            barcodes_failed.append(case["input_barcode"])
            
    # Calculate final accuracy percentage
    accuracy = (passed_count / len(cases)) * 100.0
    
    # Output the structured result table
    print("\n" + "="*85)
    print("                      LLM-AS-JUDGE EVALUATION RESULTS")
    print("="*85)
    print(f"{'Case ID':<18} | {'Input Used':<14} | {'Expected':<8} | {'Actual':<8} | {'Cat?':<4} | {'Score':<5} | {'Status'}")
    print("-"*85)
    for r in results:
        print(f"{r['case_id']:<18} | {r['input_used']:<14} | {r['expected_verdict']:<8} | {r['actual_verdict']:<8} | {r['category_correct']:<4} | {r['score']:<5.1f} | {r['status']}")
    print("="*85)
    print(f"Overall Accuracy: {accuracy:.1f}%")
    print(f"Failed Barcodes: {barcodes_failed}")
    print("="*85 + "\n")
    
    # Write result summary file to test artifacts
    summary_path = os.path.join(os.path.dirname(__file__), "eval_results_summary.json")
    with open(summary_path, "w", encoding="utf-8") as out:
        json.dump({
            "accuracy": accuracy,
            "failed_barcodes": barcodes_failed,
            "results": results
        }, out, indent=2)
        
    # Standard assertion of evaluation agreement target (target 90%+)
    assert accuracy >= 90.0, f"Evaluation agreement fell below 90% (Actual: {accuracy:.1f}%)"
