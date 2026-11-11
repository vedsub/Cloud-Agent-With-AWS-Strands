# executor.py
from typing import List, Dict, Any, Callable

def execute(
    plan: List[Dict[str, str]], 
    provider_adapter: Callable[[str, str], str], 
    max_steps: int = 5, 
    max_chars: int = 180
) -> Dict[str, Any]:
    """
    Executes a validated plan while strictly enforcing step and character budgets.
    """
    results = []
    provider_calls_made = 0
    chars_retained = 0
    
    # 1. A zero-step budget performs no provider calls
    if max_steps <= 0:
        return _build_state("budget_exhausted", results, provider_calls_made, chars_retained)

    for action in plan:
        # 2. Charge steps before starting an operation
        if provider_calls_made >= max_steps:
            return _build_state("budget_exhausted", results, provider_calls_made, chars_retained)
        
        operation = action["operation"]
        resource = action["resource"]
        
        # Dispatch the call (Step consumed)
        provider_calls_made += 1
        response_str = provider_adapter(operation, resource)
        
        # 3. Charge serialized output before retaining it
        response_length = len(response_str)
        if chars_retained + response_length > max_chars:
            # Call succeeded, but result is too large to retain. Halt execution.
            return _build_state("context_exhausted", results, provider_calls_made, chars_retained)
        
        # Retain the result and update the context budget
        results.append({
            "operation": operation,
            "resource": resource,
            "result": response_str
        })
        chars_retained += response_length

    return _build_state("completed", results, provider_calls_made, chars_retained)

def _build_state(state: str, results: List, calls: int, chars: int) -> Dict[str, Any]:
    return {
        "terminal_state": state,
        "retained_results": results,
        "provider_calls": calls,
        "retained_characters": chars
    }