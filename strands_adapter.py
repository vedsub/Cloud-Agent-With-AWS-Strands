# strands_adapter.py
import json
from typing import List, Dict, Any, Callable

# Safely attempt to import the SDK. 
# This satisfies the requirement to keep pure offline mode working even if the SDK is missing.
try:
    from strands_agents import Model, BedrockModel
except ImportError:
    Model = Any
    BedrockModel = Any

def parse_model_plan(model_output: str) -> List[Dict[str, Any]]:
    """
    Takes the raw string proposed by the LLM and parses it into a Python list.
    Fails safely if the model hallucinates non-JSON text.
    """
    try:
        plan = json.loads(model_output)
        if not isinstance(plan, list):
            raise ValueError("Model output must be a JSON array (list).")
        return plan
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse model output as JSON: {e}")

def run_strands(
    model: Model, 
    prompt: str, 
    allowed_scope: List[str], 
    validator_fn: Callable, 
    executor_fn: Callable,
    provider_fn: Callable
) -> Dict[str, Any]:
    """
    The main framework loop. 
    1. Consumes streaming events from the injected Model.
    2. Parses the proposed plan.
    3. Runs the deterministic validator.
    4. Executes via the bounded executor.
    """
    # 1. The model proposes intent. 
    # (Assuming a standard invoke/stream method from the Strands Model interface)
    raw_response = model.invoke(prompt) 
    
    # 2. Extract and parse the JSON string
    proposed_plan = parse_model_plan(raw_response)
    
    # 3. Deterministic validator grants authority (Stage 1 logic)
    # If the model hallucinates an out-of-scope resource, it dies here.
    safe_plan = validator_fn(proposed_plan, allowed_scope)
    
    # 4. Bounded executor handles budgets and transient retries (Stage 2 & 3 logic)
    execution_report = executor_fn(safe_plan, provider_fn)
    
    return execution_report

def bedrock_agent(model_id: str, region: str = "us-east-1") -> BedrockModel:
    """
    Explicit constructor for the real AWS Bedrock model.
    This is strictly opt-in and requires caller configuration and AWS IAM permissions.
    """
    if BedrockModel is Any:
        raise ImportError(
            "strands-agents SDK is not installed. "
            "Please run: pip install -r requirements-framework.txt"
        )
        
    return BedrockModel(model_id=model_id, region_name=region)