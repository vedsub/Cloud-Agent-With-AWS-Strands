# retry.py
from typing import Dict, Callable

def request_key(operation: str, resource: str) -> str:
    """
    Generates a canonical, deterministic cache key for an action identity.
    """
    return f"{operation}::{resource}"

def cached_read(
    operation: str, 
    resource: str, 
    provider_adapter: Callable[[str, str], str], 
    cache: Dict[str, str], 
    retry_allowance: int = 2
) -> str:
    """
    Executes a read with a request-local cache. Retries transient timeouts, 
    but immediately escapes on non-transient permission errors.
    """
    key = request_key(operation, resource)
    
    # Return immediately if we already fetched this during the current request
    if key in cache:
        return cache[key]

    max_attempts = retry_allowance + 1
    
    for attempt in range(max_attempts):
        try:
            result = provider_adapter(operation, resource)
            # Store successful reads in the request-local cache
            cache[key] = result
            return result
            
        except TimeoutError as e:
            # Transient failure: retry if allowance remains
            if attempt == max_attempts - 1:
                raise RuntimeError(f"Action {key} exhausted retries due to timeouts.") from e
            continue
            
        except PermissionError as e:
            # Non-transient failure: escape immediately. Repeating cannot grant authority.
            raise e