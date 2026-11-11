# plan.py
from typing import List, Dict, Any

def validate_plan(plan: List[Dict[str, Any]], allowed_scope: List[str], step_budget: int = 5) -> List[Dict[str, str]]:
    """
    Validates an LLM-generated execution plan before any provider calls are made.
    """
    if len(plan) > step_budget:
        raise ValueError(f"Plan exceeds step budget. Max allowed: {step_budget}, Proposed: {len(plan)}")

    allowed_scope_set = set(allowed_scope)
    validated_plan = []

    for action in plan:
        # 1. Reject unknown keys (Prevents silent execution parameters like "shell" or "region")
        if set(action.keys()) != {"operation", "resource"}:
            raise ValueError(f"Invalid keys in action. Expected exactly 'operation', 'resource'. Got: {list(action.keys())}")

        operation = action["operation"]
        resource = action["resource"]

        if not isinstance(operation, str) or not isinstance(resource, str):
            raise ValueError("Operation and resource values must be strings.")

        # 2. Accept only explicit read operations
        if not operation.endswith(".read"):
            raise ValueError(f"Unauthorized operation '{operation}'. Only '.read' operations are permitted.")

        # 3. Reject out-of-scope resources
        if resource not in allowed_scope_set:
            raise ValueError(f"Resource '{resource}' is outside the authorized scope: {allowed_scope}")

        validated_plan.append({"operation": operation, "resource": resource})

    return validated_plan