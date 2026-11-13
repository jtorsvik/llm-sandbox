# LangSmith

LangSmith is a platform for **observability and evaluation** of LLM applications. It works with LangChain and LangGraph, but also with plain OpenAI/Anthropic SDK calls or any Python function. It answers three questions: *what did my app do?* (tracing), *is it any good?* (evaluation), and *is it still good in production?* (monitoring).

Installed: `langsmith` 0.14 (with the `pytest` extra) and `openevals` 0.2.

## 1. Packages

| Package | Purpose |
|---|---|
| `langsmith` | The SDK: tracing decorators, the `Client` for datasets/experiments/feedback, `evaluate()`, pytest integration. |
| `langsmith[pytest]` | Extra that adds pytest plugin support so test runs can be logged as experiments. |
| `openevals` | Ready-made evaluators: LLM-as-judge, exact match, trajectory match for agents. |

## 2. Setup

1. Create an account and an API key at https://smith.langchain.com.
2. Put the following in `.env` (see `.env.example`):

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=llm-sandbox        # where traces are grouped
# LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com   # for the EU region
```

3. Call `load_dotenv()` before running your code. Set `LANGSMITH_TRACING=false` to turn tracing off without removing code.

On macOS, the Deep Agents model setup uses `truststore` so Python HTTPS clients
can use the system certificate store (including certificates trusted by the
login keychain). If TLS verification still fails, ask your administrator to
install the required CA in the system keychain or provide a trusted CA bundle;
do not disable certificate verification.

## 3. Core concepts

| Concept | Meaning |
|---|---|
| **Run** | One unit of work (an LLM call, a tool call, a function). Has inputs, outputs, timing, tokens and errors. |
| **Trace** | A tree of runs for one end-to-end request. |
| **Project** | A collection of traces, typically one per app or environment. |
| **Thread** | A group of traces that belong to the same conversation. |
| **Dataset** | A set of example inputs (and optionally reference outputs) used for testing. |
| **Experiment** | The result of running your app over a dataset, with scores from evaluators. |
| **Evaluator** | A function that scores an output (code check, LLM judge, human). |
| **Feedback** | A named score or comment attached to a run, from users, evaluators or annotators. |
| **Prompt Hub** | Versioned prompts that you can pull from code. |

## 4. Tracing

### LangChain and LangGraph: automatic

With the env vars above, nothing else is needed. Every `invoke`/`stream` of a chain, agent or graph shows up as a trace with nested runs for each model, tool and retriever call.

To add metadata, tags or a run name:

```python
chain.invoke(
    {"question": "hi"},
    config={"run_name": "support-bot", "tags": ["dev"], "metadata": {"user_id": "42"}},
)
```

### Any Python function: `@traceable`

```python
from langsmith import traceable

@traceable(run_type="retriever", name="search_docs")
def search(query: str) -> list[str]:
    ...

@traceable(run_type="chain")
def answer(question: str) -> str:
    docs = search(question)      # appears as a child run
    return llm(question, docs)
```

`run_type` can be `chain`, `llm`, `tool`, `retriever`, `embedding`, `prompt` or `parser`. Nested traced calls automatically form a tree.

### Raw provider SDKs: wrappers

```python
from openai import OpenAI
from langsmith.wrappers import wrap_openai

client = wrap_openai(OpenAI())   # every call is traced with tokens and cost
```

`wrap_anthropic` works the same way for the Anthropic SDK.

### Manual blocks: `trace`

```python
from langsmith import trace

with trace("load-data", run_type="chain", inputs={"path": path}) as run:
    data = load(path)
    run.add_outputs({"rows": len(data)})
```

### Controlling tracing

- `tracing_context(enabled=False)` (from `langsmith`) disables tracing in a block.
- `@traceable(process_inputs=..., process_outputs=...)` lets you redact sensitive data before it leaves your machine.
- Traces are sent in a background thread. In short-lived scripts call `langsmith.Client().flush()` (or `wait_for_all_tracers()` from `langchain_core.tracers.langchain`) before exit.

## 5. Datasets

Create a dataset of examples with the `Client`:

```python
from langsmith import Client

client = Client()
dataset = client.create_dataset("qa-smoke-tests", description="Basic QA checks")
client.create_examples(
    dataset_id=dataset.id,
    examples=[
        {"inputs": {"question": "Capital of Norway?"}, "outputs": {"answer": "Oslo"}},
        {"inputs": {"question": "Capital of France?"}, "outputs": {"answer": "Paris"}},
    ],
)
```

A good source of examples is real traces: in the UI, add interesting production runs to a dataset.

## 6. Evaluation

`evaluate()` runs your app on every example in a dataset and applies evaluators. The results are saved as an experiment you can compare against earlier ones.

```python
from langsmith import evaluate

def target(inputs: dict) -> dict:               # the thing under test
    return {"answer": answer(inputs["question"])}

def correct(outputs: dict, reference_outputs: dict) -> bool:   # a custom evaluator
    return outputs["answer"].strip().lower() == reference_outputs["answer"].lower()

results = evaluate(
    target,
    data="qa-smoke-tests",
    evaluators=[correct],
    experiment_prefix="baseline",
    max_concurrency=4,
)
```

Evaluator functions can take any of `inputs`, `outputs`, `reference_outputs`, and return a bool, number, or `{"key": ..., "score": ..., "comment": ...}`. Use `aevaluate()` for async targets.

### openevals: prebuilt evaluators

```python
from openevals.exact import exact_match
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT

exact_match(outputs="Oslo", reference_outputs="Oslo")
# {'key': 'exact_match', 'score': True, ...}

correctness = create_llm_as_judge(
    prompt=CORRECTNESS_PROMPT,
    model="openai:gpt-4o-mini",
    feedback_key="correctness",
)
```

Pass these straight into `evaluate(..., evaluators=[exact_match, correctness])`. For agents, `create_trajectory_match_evaluator` compares the sequence of tool calls to a reference, and `create_trajectory_llm_as_judge` judges the trajectory with a model. Async variants are prefixed `create_async_`.

## 7. Testing with pytest

The pytest integration logs each test as an example and each run as an experiment.

```python
# tests/test_qa.py
import pytest
from langsmith import testing as t

@pytest.mark.langsmith
def test_capital():
    question = "Capital of Norway?"
    t.log_inputs({"question": question})
    out = answer(question)
    t.log_outputs({"answer": out})
    t.log_reference_outputs({"answer": "Oslo"})
    assert "Oslo" in out
```

Run it with `uv run pytest --langsmith-output`. Without a LangSmith API key (or with `LANGSMITH_TEST_TRACKING=false`) the tests still run locally.

## 8. Feedback and monitoring

- Attach feedback in code: `Client().create_feedback(run_id, key="thumbs", score=1)`.
- In the UI, build **dashboards** (latency, error rate, token cost), add **online evaluators** that automatically score a sample of production traces, and set **alerts**.
- **Annotation queues** let people review and label runs, which you can feed back into datasets.

## 9. Prompt Hub

Store and version prompts in LangSmith and pull them in code:

```python
from langsmith import Client

prompt = Client().pull_prompt("my-prompt")   # a LangChain prompt template
chain = prompt | model
```

The Playground in the UI lets you iterate on prompts against dataset examples.

## 10. Typical workflow

1. Turn on tracing and use the app; inspect failures in the trace view.
2. Save problematic or representative runs as a **dataset**.
3. Write **evaluators** (code or LLM-as-judge via `openevals`).
4. Run `evaluate()` for a baseline, change a prompt/model/tool, run again, and **compare experiments**.
5. Add the evaluations to pytest/CI, and monitor production with online evaluators.

## Privacy note

Traces contain your prompts and model outputs and are sent to LangSmith. Do not trace sensitive data unless your organization allows it; use input/output processors to redact, or self-host LangSmith.

## References

- https://docs.langchain.com/langsmith
- https://github.com/langchain-ai/openevals
