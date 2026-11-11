# cli.py
import argparse
import json
import sys
from plan import validate_plan

def main():
    parser = argparse.ArgumentParser(description="Cloud Agent Intent Validator")
    parser.add_argument("input_file", help="Path to input JSON containing the proposed plan")
    parser.add_argument("--output", required=True, help="Path to write the validated output")
    args = parser.parse_args()

    # Driver owns file input
    try:
        with open(args.input_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file {args.input_file} not found.", file=sys.stderr)
        sys.exit(1)

    proposed_plan = data.get("plan", [])
    allowed_scope = data.get("allowed_scope", [])

    print(f"Validating plan with scope {allowed_scope}...")

    try:
        # Core function execution
        safe_plan = validate_plan(proposed_plan, allowed_scope)
        
        # Driver owns presentation and file output
        with open(args.output, 'w') as f:
            json.dump({"status": "success", "executable_plan": safe_plan}, f, indent=2)
        
        print(f"Validation successful. 0 provider calls made during validation.")
        print(f"Executable plan written to {args.output}")

    except ValueError as e:
        print(f"VALIDATION FAILED: {e}", file=sys.stderr)
        print("0 provider calls made. Execution halted.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()