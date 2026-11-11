# Cloud Agent with AWS Strands

A secure, bounded execution environment for Agentic AI interactions with cloud infrastructure.

This project demonstrates how to safely bridge a Large Language Model (LLM) with real-world cloud APIs (AWS). Because LLMs are probabilistic—prone to hallucinations, prompt injections, and unbounded loops—this system wraps the AI in a deterministic, zero-trust security envelope.

This README serves as a deep dive into the system's architecture, specifically designed to explain the "why" and "how" behind the implementation choices.

---

## 🏛 Core Philosophy: Intent vs. Authority

The foundational principle of this project is the strict separation of **Intent** and **Authority**.

* **Intent (The LLM):** The model evaluates a prompt and proposes a JSON plan of action (e.g., "I need to read the checkout metrics"). It has zero execution power.
* **Authority (The Validator):** A hard-coded, deterministic Python layer intercepts the proposal. It verifies the plan against strict security rules. Only if the plan is perfectly safe does the system grant the authority to execute it.

---

## ⚙️ Architecture & First-Principles Explanations

The system is built in four distinct stages, progressively adding layers of security, efficiency, and integration.

### Stage 1: The Deterministic Validator (`plan.py`)

Before a single network call is made, the proposed plan is scrubbed. We enforce a "fail-fast" boundary.

**Deep Dive: Preventing Silent Parameters**
We enforce that every action dictionary contains *exactly* two keys: `operation` and `resource`.
Why not just check if those two exist and ignore the rest? Because of prompt injection. If an LLM is tricked into outputting `{"operation": "metrics.read", "resource": "checkout", "force_override": true, "shell": "rm -rf"}`, a lazy parser might ignore the extra keys, but a downstream API might accept them as kwargs. By strictly failing on unknown keys, we ensure no model-generated instructions can silently become executable parameters. We also strictly enforce that operations must end in `.read` to guarantee no state-mutating actions (like `.delete`) are authorized.

### Stage 2: Execution Budgets (`executor.py`)

If the plan is safe, we execute it. But LLMs can easily propose 10,000 steps or request a 5GB log file, which would bankrupt your cloud account or crash the application. We implement two budgets:

1. **Step Budget (Limits Dispatch):** We charge this budget *before* making the API call. If the model is in a loop, it exhausts steps and the system safely halts, returning an explicit `budget_exhausted` state.
2. **Context Character Budget (Limits Retention):** LLMs have strict context windows. If an API returns massive data, we drop the result before appending it to the LLM's prompt.

**Deep Dive: The Network Truncation Boundary**
Notice that the Context Character Budget drops the payload *after* the API call succeeds but *before* the LLM sees it. Why not stop the API call itself? Because this executor layer doesn't control the network. If an AWS CloudWatch log is 5GB, Python will attempt to load 5GB into RAM and crash with an Out-of-Memory (OOM) error before our `len(result)` check even runs. Therefore, this project scopes the *executor* to protecting the LLM's context window, while explicitly recognizing that a separate *network adapter* (using byte-range requests) must handle physical memory protection.

### Stage 3: Request-Local Caching & Retries (`retry.py`)

Cloud APIs fail. We gracefully retry transient errors (like `TimeoutError`) but immediately escape on non-transient errors (like `PermissionError/IAM failures`—retrying a 403 Forbidden is pointless). Furthermore, since we enforced read-only operations in Stage 1, our actions are idempotent, meaning we can cache them.

**Deep Dive: How the Request-Local Cache Works**
In cloud infrastructure, state changes rapidly. A global cache (like Redis) is dangerous because an LLM might make decisions on stale data from 5 minutes ago. We need a cache that lives *exactly* as long as the current execution plan, and then vanishes.

Here is how we built this using Python's variable scope and memory management:

1. **The Birth:** Inside the `execute()` function, we declare `cache = {}`. This dictionary is instantiated locally in memory for this specific run.
2. **Pass-by-Reference:** Python passes mutable objects (like dictionaries) by reference. When we call `cached_read(..., cache)`, Python does not make a copy. The `cached_read` function looks at and modifies that exact memory address. If it fetches `checkout` metrics, it saves it into that specific dictionary.
3. **The Cache Hit:** The next time `cached_read` is called in the loop, it checks `if key in cache:`. Because it's the exact same dictionary, it finds the data and skips the network call.
4. **The Death (Garbage Collection):** When `execute()` hits its `return` statement, the function's scope closes. Python's Garbage Collector sees that nothing is pointing to the `cache` dictionary anymore. The memory is immediately destroyed. If a new request comes in 1 second later, it gets a brand new, empty `{}`.

### Stage 4: Framework Integration (`strands_adapter.py`)

The core logic (Stages 1-3) is completely pure—it doesn't know about AWS, CLI arguments, or specific LLMs. Stage 4 introduces the adapter pattern to plug this pure core into the real AWS Strands framework.

**Deep Dive: Graceful Degradation & Dependency Injection**
We use `try...except ImportError` when importing the Strands SDK. This allows the system to run in three distinct modes:

1. **Pure Offline Core:** Runs unit tests without needing the SDK installed.
2. **Local-Model Comparison:** Injects a fake, mock model into the framework loop. This tests our JSON parsing (`parse_model_plan`) and orchestration logic without needing AWS credentials or internet access.
3. **Opt-in AWS (Bedrock):** Uses an explicit constructor (`bedrock_agent`) to instantiate real AWS Bedrock LLMs. This is tightly isolated so offline tests never accidentally trigger billing or IAM errors.

---

## 🚀 Project Scope

**What this project IS:**

* A robust, defensive orchestration engine for Agentic AI.
* A demonstration of separating core pure functions from side-effect-heavy adapters (CLI, Network, LLM APIs).
* A showcase of advanced Python concepts: pass-by-reference mutation, garbage collection lifecycles, and dependency injection.

**What this project IS NOT:**

* **An AWS Deployment Tool:** This does not provision EC2 instances or write Terraform. It assumes the resources exist and strictly manages the *read access* the AI has to them.
* **A Prompt-Engineering Wrapper:** This framework does not care what the LLM's system prompt is. It relies entirely on deterministic JSON parsing and Python enforcement to maintain safety.



Here is the **Usage & Execution** section to add to the bottom of your README. It provides exact steps, explains what the inputs/outputs mean, and shows an interviewer how to actually run the code we built.

---

## 💻 How to Use This Project

This system is designed to be run from the command line. The CLI driver (`cli.py`) handles all file I/O, allowing the core executor to remain pure and testable.

### 1. Initial Setup

Create a virtual environment and prepare the workspace. *(Note: The core framework runs entirely on the standard Python library. The SDK is only required for the opt-in Stage 4 integration).*

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# (Optional) Install the Strands SDK for Stage 4 framework integration
pip install strands-agents==1.57.1

```

### 2. Defining the Input (The LLM's Proposal)

The system expects a JSON input file that contains two things: the `allowed_scope` (set by the human/system administrator) and the `plan` (proposed by the AI model).

Create a file at `samples/input.json`:

```json
{
  "allowed_scope": ["checkout", "inventory"],
  "plan": [
    {
      "operation": "metrics.read",
      "resource": "checkout"
    },
    {
      "operation": "logs.read",
      "resource": "checkout"
    }
  ]
}

```

### 3. Running the Executor

Run the driver script, passing the input file and specifying where you want the execution report saved.

```bash
python3 cli.py samples/input.json --output incident.json

```

**Customizing Execution Budgets:**
You can explicitly set the budgets we built in Stage 2 to test how the system traps greedy or hallucinating models.

```bash
python3 cli.py samples/input.json --output incident.json --max-steps 3 --max-chars 500

```

### 4. Understanding the Output

The system writes an execution report to `incident.json`. This provides an inspectable, auditable trail of exactly what happened, why it stopped, and how much context was retained.

```json
{
  "terminal_state": "completed", 
  "retained_results": [
    {
      "operation": "metrics.read",
      "resource": "checkout",
      "result": "Data for metrics.read on checkout"
    },
    {
      "operation": "logs.read",
      "resource": "checkout",
      "result": "Data for logs.read on checkout"
    }
  ],
  "retained_characters": 64,
  "cache_hits": 0
}

```

* **`terminal_state`**: Will show `"completed"` on a successful run. If a budget is hit, this explicitly states `"budget_exhausted"` or `"context_exhausted"` so the LLM knows why it didn't get all its data.
* **`cache_hits`**: Proves that the request-local cache from Stage 3 successfully intercepted duplicate read actions.

### 5. Running the Test Suite 

To verify the integrity of the intent-validator boundary and execution budgets, run the cumulative grading scripts.

**Test the Pure Offline Core (Stages 1-3):**

```bash
python3 scripts/project_test.py cloud-agent-with-aws-strands --stage 3 --path . --strict

```

**Test the Framework Integration (Stage 4):**
*(Requires the `strands-agents` package to be installed in your venv)*

```bash
python3 scripts/project_test.py cloud-agent-with-aws-strands --solution --optional --strict

```