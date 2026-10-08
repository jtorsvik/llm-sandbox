# Langflow

Langflow is a **visual, low-code builder** for LLM workflows and agents. You drag components onto a canvas, connect them, and run the result as a chat, an API endpoint or an MCP tool. Under the hood it is built on LangChain, and every component is Python code you can inspect and edit.

Installed: `langflow` 1.10 (with `langflow-base` and `lfx` 1.12).

## 1. Packages

| Package | Purpose |
|---|---|
| `langflow` | The full distribution: web UI, backend, bundled components and CLI. |
| `langflow-base` | The core backend and UI without the large set of optional integrations. Installed as a dependency of `langflow`. |
| `lfx` | The Langflow Executor: a lightweight runtime for running flows without the UI/database. |
| `langflow-sdk` | Python client for talking to a running Langflow server. |
| `lfx-*` plugin packages | Optional component bundles (for example `lfx-duckduckgo`, `lfx-arxiv`, `lfx-docling`). |

## 2. Running Langflow

```bash
uv run langflow run                     # UI at http://127.0.0.1:7860
uv run langflow run --port 8000 --host 0.0.0.0
uv run langflow run --env-file .env
uv run langflow run --backend-only      # API only, no UI
```

Useful `run` options: `--components-path` (load your own components), `--log-level`, `--workers`, `--auto-saving/--no-auto-saving`, `--remove-api-keys`.

Other CLI commands (`uv run langflow --help`):

| Command | What it does |
|---|---|
| `langflow superuser` | Create an admin user |
| `langflow api-key` | Create an API key for the default superuser (when `LANGFLOW_AUTO_LOGIN` is enabled) |
| `langflow lfx run <flow>` | Run a flow file directly from the terminal |
| `langflow lfx serve <flow>` | Serve a single flow as an API |
| `langflow copy-db` | Copy the database files to the current directory |
| `langflow migration` | Run or test database migrations |

Langflow stores flows, users and settings in its own database (SQLite by default, in its config directory). Configure it with `LANGFLOW_*` environment variables, for example `LANGFLOW_DATABASE_URL`, `LANGFLOW_SECRET_KEY`, `LANGFLOW_AUTO_LOGIN` and `LANGFLOW_CONFIG_DIR`. Add them to `.env` and pass `--env-file .env`.

## 3. The building blocks

A **flow** is a graph of **components** connected by typed edges. The sidebar groups components into categories (names vary slightly between versions):

| Category | Examples and purpose |
|---|---|
| **Inputs / Outputs** | `Chat Input`, `Text Input`, `Chat Output`, `Text Output`. The entry and exit points of a flow, and what the Playground chats with. |
| **Models** | Language model components for OpenAI, Anthropic, Google, Ollama, etc., plus embedding models. Take an API key and model name, and output a model or a message. |
| **Prompts** | `Prompt` template with `{variables}` that become input handles. |
| **Agents** | `Agent` component: an LLM that can use connected tools and decide what to do. |
| **Tools** | Components used as agent tools: calculator, web search, URL fetch, other flows, MCP tools, and any component switched into *Tool mode*. |
| **Data / Files** | File loaders, URL, API request, directory, and database connectors that produce `Data`/`DataFrame` objects. |
| **Processing** | Split text, parse data, combine, filter, structured output, conditional router, loops, Python/function logic. |
| **Vector stores & embeddings** | Chroma, FAISS, Qdrant, pgvector and others for RAG. |
| **Memory** | Chat memory components for conversations. |
| **Logic / Helpers** | Routing, loops, notes, and utility components. |
| **Custom** | A blank component where you write your own Python. |

### Data types

Edges are colour-coded by type, and you can only connect compatible types:

- `Message`: chat text with sender and session metadata.
- `Data`: a record (a dict with text and metadata).
- `DataFrame`: tabular data.
- `LanguageModel`, `Embeddings`, `Tool`, `Memory`: object-typed connections.
- Primitive inputs (text, number, dropdown, secret, file, etc.), which you can also set per component.

### Other platform features

- **Playground**: chat with a flow in the UI and see each component's inputs and outputs for debugging.
- **Global variables**: store API keys and settings once (Settings > Global Variables) and reference them from components.
- **Projects / folders**: organise flows; export and import flows as JSON.
- **API access**: every flow gets an endpoint and a code snippet generator (Python, JavaScript, cURL).
- **MCP**: Langflow can act as an MCP **server** that exposes your flows as tools to other clients, and as an MCP **client** that uses external MCP servers as tools.
- **Knowledge bases / files**: manage uploaded files and vectorised knowledge for reuse across flows.
- **Observability**: Langflow can send traces to LangSmith, Langfuse, and others via environment variables (see section 7).

## 4. Building a first flow

**Basic chatbot**

1. New flow: *Blank flow*, or start from a template such as *Basic Prompting* or *Simple Agent*.
2. Drag in `Chat Input` -> `Prompt` -> a model component (set the API key) -> `Chat Output`.
3. In the `Prompt` template use variables like `{question}`, and connect the chat input to that field.
4. Open the **Playground** and chat.

**RAG flow** (typical shape)

- Ingestion: `File` -> `Split Text` -> `Embedding Model` + `Vector Store` (write).
- Query: `Chat Input` -> `Vector Store` (search) -> `Parse Data` -> `Prompt` (with `{context}` and `{question}`) -> model -> `Chat Output`.

**Agent flow**

- `Chat Input` -> `Agent` -> `Chat Output`, with tools (calculator, URL, a vector-store search, another flow) connected to the agent's *Tools* handle. Components that support it can be toggled into **Tool mode**.

## 5. Calling flows from code

### REST API

Each flow has an ID (or endpoint name). Create an API key in the UI (Settings > Langflow API Keys) and call the run endpoint:

```python
import os
import httpx

LANGFLOW_URL = "http://127.0.0.1:7860"
FLOW_ID = "<flow-id-or-endpoint-name>"

resp = httpx.post(
    f"{LANGFLOW_URL}/api/v1/run/{FLOW_ID}",
    headers={"x-api-key": os.environ["LANGFLOW_API_KEY"]},
    json={
        "input_value": "Hello!",
        "input_type": "chat",
        "output_type": "chat",
        "session_id": "user-1",   # keeps conversation memory per session
    },
    timeout=120,
)
resp.raise_for_status()
print(resp.json()["outputs"][0]["outputs"][0]["results"]["message"]["text"])
```

Add `?stream=true` for streaming. Use **Tweaks** (a `"tweaks"` object keyed by component ID) to override component settings per request. The interactive API reference is available at `http://127.0.0.1:7860/docs` while the server runs.

### Run a saved flow in-process

Export a flow as JSON (`flows/my_flow.json`) and run it without the server:

```python
from langflow.load import run_flow_from_json

result = run_flow_from_json(
    flow="flows/my_flow.json",
    input_value="Hello!",
    fallback_to_env_vars=True,    # read API keys from the environment
)
```

Or from the terminal with the lightweight executor:

```bash
uv run langflow lfx run flows/my_flow.json "Hello!"
uv run langflow lfx serve flows/my_flow.json      # expose it as an API
```

Keep exported flow JSON files in the `flows/` folder of this repo so they can be version-controlled. Remove secrets from the export (or use global variables) before committing.

## 6. Custom components

Every component is a Python class. Create your own by subclassing `Component`, declaring `inputs` and `outputs`, and implementing a method for each output.

```python
# components/word_counter.py
from langflow.custom import Component
from langflow.io import MessageTextInput, IntInput, Output
from langflow.schema import Data


class WordCounter(Component):
    display_name = "Word Counter"
    description = "Counts the words in a text."
    icon = "hash"
    name = "WordCounter"

    inputs = [
        MessageTextInput(name="text", display_name="Text", info="Text to analyse"),
        IntInput(name="min_length", display_name="Min word length", value=1, advanced=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="count_words"),
    ]

    def count_words(self) -> Data:
        words = [w for w in self.text.split() if len(w) >= self.min_length]
        self.status = f"{len(words)} words"      # shown on the component in the UI
        return Data(data={"count": len(words)})
```

Load it by starting Langflow with the folder: `uv run langflow run --components-path ./components` (organise as `components/<category>/<file>.py`), or paste the code into a **Custom Component** in the UI.

Common input classes in `langflow.io`: `MessageTextInput`, `StrInput`, `MultilineInput`, `IntInput`, `FloatInput`, `BoolInput`, `DropdownInput`, `SecretStrInput` (for API keys), `FileInput`, `HandleInput` (connect objects such as models or tools), `DataInput`. Common return types: `Message` (`langflow.schema.message`), `Data`, `DataFrame` (`langflow.schema`). Set `tool_mode=True` on an input to let an agent fill it in when the component is used as a tool.

## 7. Observability with LangSmith

Langflow reads the standard LangSmith variables, so add them to the `.env` that you pass to `--env-file`:

```bash
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=llm-sandbox
LANGCHAIN_TRACING_V2=true
```

Flow runs then appear in LangSmith with one trace per run and a span per component. See [langsmith.md](./langsmith.md).

## 8. When to use Langflow vs. code

| Use Langflow when | Use LangChain/LangGraph in code when |
|---|---|
| Prototyping and iterating quickly with a visual graph | You need full control, tests and type checking |
| Sharing a workflow with non-developers | The logic is complex or highly custom |
| You want an instant API/MCP endpoint for a flow | The app is embedded in a larger codebase |

The two combine well: prototype a flow in Langflow, then export the JSON and run it with `run_flow_from_json` or the REST API, or re-implement the stable parts in code ([langchain.md](./langchain.md)).

## 9. Troubleshooting

- **Dependency errors**: keep Langflow in this project's `pyproject.toml` (managed with `uv add`). Running it from a different project can pull in conflicting `fastapi`/`pydantic` versions.
- **Port already in use**: pass `--port`.
- **Lost flows after changing directories**: the SQLite database lives in the Langflow config directory; set `LANGFLOW_CONFIG_DIR` or `LANGFLOW_DATABASE_URL` for a stable location.
- **Missing API keys in components**: add them as global variables or export them in `.env` and use `--env-file`.

## References

- https://docs.langflow.org
- https://github.com/langflow-ai/langflow
