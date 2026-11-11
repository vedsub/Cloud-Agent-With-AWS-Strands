# cli.py
import argparse
import json
import sys
from plan import validate_plan
from executor import execute

class MockCloud:
    def __init__(self):
        self.network_calls = 0
        self.timeout_tracker = {}
        
    def adapter(self, operation: str, resource: str) -> str:
        self.network_calls += 1
        
        if resource == "secret-db":
            raise PermissionError("IAM Role missing for secret-db")
            
        if resource == "flakey-api":
            if "flakey-api" not in self.timeout_tracker:
                self.timeout_tracker["flakey-api"] = True
                raise TimeoutError("Connection timed out on first attempt")
                
        return f"Data for {operation} on {resource}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input_file, 'r') as f:
        data = json.load(f)

    proposed_plan = data.get("plan", [])
    allowed_scope = data.get("allowed_scope", [])
    
    cloud = MockCloud()

    try:
        safe_plan = validate_plan(proposed_plan, allowed_scope)
        report = execute(
            plan=safe_plan,
            provider_adapter=cloud.adapter,
            max_steps=5,
            max_chars=180
        )
        
        report["total_network_calls"] = cloud.network_calls
        
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"State: {report['terminal_state']} | Network Calls: {cloud.network_calls} | Cache Hits: {report['cache_hits']}")

    except ValueError as e:
        print(f"VALIDATION FAILED: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()