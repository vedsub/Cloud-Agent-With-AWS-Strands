# executor.py
from typing import List, Dict, Any, Callable
from retry import cached_read, request_key

def execute(
    plan: List[Dict[str, str]], 
    provider_adapter: Callable[[str, str], str], 
    max_steps: int = 5, 
    max_chars: int = 180,
    retry_allowance: int = 2
) -> Dict[str, Any]:
    
    results = []
    chars_retained = 0
    cache: Dict[str, str] = {} # Request-local cache
    cache_hits = 0
    
    if max_steps <= 0:
        return _build_state("budget_exhausted", results, chars_retained, cache_hits)

    for action in plan:
        # Check step budget. Note: We only charge steps for logical actions, 
        # actual network retries are handled beneath this layer.
        if len(results) >= max_steps:
            return _build_state("budget_exhausted", results, chars_retained, cache_hits)
            
        operation = action["operation"]
        resource = action["resource"]
        key = request_key(operation, resource)
        
        if key in cache:
            cache_hits += 1
            
        try:
            response_str = cached_read(
                operation, resource, provider_adapter, cache, retry_allowance
            )
        except Exception as e:
            # Halt execution on unrecoverable errors (permissions, exhausted timeouts)
            results.append({"error": str(e), "failed_action": key})
            return _build_state("execution_failed", results, chars_retained, cache_hits)
        
        response_length = len(response_str)
        if chars_retained + response_length > max_chars:
            return _build_state("context_exhausted", results, chars_retained, cache_hits)
            
        results.append({
            "operation": operation,
            "resource": resource,
            "result": response_str
        })
        chars_retained += response_length

    return _build_state("completed", results, chars_retained, cache_hits)

def _build_state(state: str, results: List, chars: int, hits: int) -> Dict[str, Any]:
    return {
        "terminal_state": state,
        "retained_results": results,
        "retained_characters": chars,
        "cache_hits": hits
    }