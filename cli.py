# cli.py
import argparse
import json
import sys
from plan import validate_plan
from executor import execute

def mock_cloud_provider(operation: str, resource: str) -> str:
    """A dummy adapter simulating cloud responses."""
    # Simulate the failure boundary case directly for demonstration
    if resource == "giant-log":
        return "X" * 1000
    
    return f"Data for {operation} on {resource}"

def main():
    parser = argparse.ArgumentParser(description="Cloud Agent Executor")
    parser.add_argument("input_file", help="Path to input JSON")
    parser.add_argument("--output", required=True, help="Path to write output")
    parser.add_argument("--max-steps", type=int, default=5, help="Step budget")
    parser.add_argument("--max-chars", type=int, default=180, help="Context character budget")
    args = parser.parse_args()

    try:
        with open(args.input_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {args.input_file} not found.", file=sys.stderr)
        sys.exit(1)

    proposed_plan = data.get("plan", [])
    allowed_scope = data.get("allowed_scope", [])

    try:
        # Stage 1: Validate Intent
        safe_plan = validate_plan(proposed_plan, allowed_scope)
        
        # Stage 2: Execute with Budgets
        execution_report = execute(
            plan=safe_plan,
            provider_adapter=mock_cloud_provider,
            max_steps=args.max_steps,
            max_chars=args.max_chars
        )
        
        with open(args.output, 'w') as f:
            json.dump(execution_report, f, indent=2)
            
        print(f"Execution finished with state: {execution_report['terminal_state']}")
        print(f"Provider calls made: {execution_report['provider_calls']}")
        print(f"Results saved to {args.output}")

    except ValueError as e:
        print(f"VALIDATION FAILED: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()