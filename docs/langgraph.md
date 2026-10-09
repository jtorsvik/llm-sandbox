# LangGraph

LangGraph is a low-level orchestration framework for **stateful, long-running, multi-step LLM workflows and agents**. You describe the workflow as a graph: nodes do the work, edges decide what runs next, and a shared state is passed along. It adds what plain chains lack: loops, branching, parallelism, persistence, human approval and resumability. LangChain's `create_agent` is built on it (see [langchain.md](./langchain.md)).

Installed: `langgraph` 1.2.

## 1. Packages

| Package | Purpose |
|---|---|
| `langgraph` | The core library: `StateGraph`, `START`/`END`, `Command`, `Send`, `interrupt`, in-memory checkpointer and store, streaming. |
| `langgraph-checkpoint` | Base checkpointer interfaces and `InMemorySaver`. Installed with `langgraph`. |
| `langgraph-checkpoint-sqlite` | `SqliteSaver` for persisting threads in a local SQLite file. |
| `langgraph-prebuilt` | Prebuilt pieces such as `ToolNode` and `tools_condition`. Installed with `langgraph`. |
| `langgraph-supervisor` | `create_supervisor`: a supervisor agent that delegates to specialist agents. |
| `langgraph-swarm` | `create_swarm`: agents that hand off to each other, remembering who is active. |
| `langgraph-sdk` | Python client for a LangGraph server (assistants, threads, runs). |
| `langgraph-cli[inmem]` | The `langgraph` command: scaffold, run a local dev server with Studio, build Docker images. |
| `langgraph-api`, `langgraph-runtime-inmem` | The server runtime used by the CLI dev server. |

For production Postgres persistence, add `langgraph-checkpoint-postgres` (it needs a Postgres driver and server).

## 2. Core concepts

| Concept | Meaning |
|---|---|
| **State** | The data shared by all nodes: a `TypedDict`, dataclass or Pydantic model. |
| **Node** | A function (sync or async) that receives the state and returns a partial update. |
| **Edge** | A transition between nodes: fixed (`add_edge`) or computed (`add_conditional_edges`). |
| **Reducer** | A function on a state field that says how updates are merged (default: overwrite). |
| **Checkpointer** | Saves a snapshot of the state after each step, keyed by `thread_id`. |
| **Thread** | A conversation or run history, identified by `thread_id`. |
| **Store** | Cross-thread long-term memory (key-value with namespaces, optional semantic search). |
| **Super-step** | One round in which all ready nodes run (in parallel); the state is merged and checkpointed afterwards. |

You build a `StateGraph`, call `.compile()`, and get a runnable that supports `invoke`, `ainvoke`, `stream`, `astream`, `batch` and `get_state`.

## 3. A first graph

```python
from typing import TypedDict
from langgraph.graph import END, START, StateGraph

class State(TypedDict):
    question: str
    answer: str

def respond(state: State) -> dict:
    return {"answer": f"You asked: {state['question']}"}

builder = StateGraph(State)
builder.add_node("respond", respond)
builder.add_edge(START, "respond")
builder.add_edge("respond", END)
graph = builder.compile()

graph.invoke({"question": "What is LangGraph?"})
# {'question': 'What is LangGraph?', 'answer': 'You asked: What is LangGraph?'}
```

Nodes return only the keys they change. Replace the function with a model call to make an LLM node.

### State and reducers

By default a returned key overwrites the old value. A reducer, supplied with `Annotated`, merges instead:

```python
import operator
from typing import Annotated, TypedDict

class State(TypedDict):
    items: Annotated[list[str], operator.add]   # lists are concatenated
    count: int                                    # overwritten
```

For chat apps, `MessagesState` (or `Annotated[list, add_messages]`) gives you a `messages` list that appends new messages and updates existing ones by ID:

```python
from langgraph.graph import MessagesState

class State(MessagesState):
    summary: str
```

Use separate `input_schema`/`output_schema` arguments on `StateGraph` to hide internal fields from callers.

## 4. Control flow

### Conditional edges

A routing function returns the name of the next node (or `END`):

```python
def route(state: State) -> str:
    return "tools" if state["messages"][-1].tool_calls else END

builder.add_conditional_edges("agent", route)
```

### `Command`: update state and route in one step

```python
from typing import Literal
from langgraph.types import Command

def triage(state: State) -> Command[Literal["billing", "support"]]:
    target = "billing" if "invoice" in state["question"] else "support"
    return Command(update={"topic": target}, goto=target)
```

`Command` is also how you resume after an interrupt (section 6) and how a subgraph or agent hands control to another agent (`Command(goto=..., graph=Command.PARENT)`).

### Parallel branches and map-reduce with `Send`

Several outgoing edges from one node run in parallel. When the number of branches is only known at runtime, return `Send` objects, each starting a node with its own input:

```python
from langgraph.types import Send

def fan_out(state: State):
    return [Send("summarize", {"doc": d}) for d in state["docs"]]

builder.add_conditional_edges(START, fan_out, ["summarize"])
# 'summarize' returns {"summaries": [...]} and the field uses operator.add as its reducer
```

### Loops

Edges can point back to earlier nodes, which is what makes agent loops possible. A `recursion_limit` in `config` caps the number of steps per run. The default is very high (10007 here, changeable with the `LANGGRAPH_DEFAULT_RECURSION_LIMIT` environment variable), so set a smaller value for agent loops:

```python
graph.invoke(inputs, config={"recursion_limit": 25})
```

### Node options

`add_node(..., retry_policy=RetryPolicy(max_attempts=3))` retries a failing node, and `cache_policy` caches its result. Compile with `graph.compile(...)` after adding all nodes and edges.

## 5. A tool-calling agent built by hand

```python
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

tools = [multiply]
model = init_chat_model("openai:gpt-4o-mini").bind_tools(tools)

def agent(state: MessagesState):
    return {"messages": [model.invoke(state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)   # -> "tools" or END
builder.add_edge("tools", "agent")
graph = builder.compile()

graph.invoke({"messages": [("human", "What is 6 times 7?")]})
```

This is exactly the loop that `langchain.agents.create_agent` gives you in one call. Build it by hand when you need extra nodes, custom routing, or special state.

## 6. Persistence, memory and human-in-the-loop

### Checkpointers (short-term memory)

Compile with a checkpointer and pass a `thread_id`; the state of that thread is saved after every step and restored on the next call.

```python
from langgraph.checkpoint.memory import InMemorySaver

graph = builder.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "user-1"}}

graph.invoke({"messages": [("human", "My name is Sam.")]}, config)
graph.invoke({"messages": [("human", "What is my name?")]}, config)   # remembers
```

To keep threads across restarts, use SQLite:

```python
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
    graph = builder.compile(checkpointer=saver)
    graph.invoke(inputs, config)
```

(`*.sqlite3` is git-ignored; add `*.sqlite` too if you use that suffix.) Async code uses `AsyncSqliteSaver` from the same package (`langgraph.checkpoint.sqlite.aio`).

With a checkpointer you can also inspect and rewind:

```python
graph.get_state(config)                 # latest snapshot: .values, .next
list(graph.get_state_history(config))   # every checkpoint (time travel)
graph.update_state(config, {"messages": [...]})   # edit state manually
```

### Stores (long-term memory)

A store holds data that outlives a single thread, such as user preferences.

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
store.put(("users", "42"), "prefs", {"tone": "formal"})
store.get(("users", "42"), "prefs").value

graph = builder.compile(checkpointer=InMemorySaver(), store=store)
```

Nodes can accept a `store` argument (and `config`) in their signature to read and write it. A store can also be given an embedding `index` for semantic search.

### Human-in-the-loop with `interrupt`

`interrupt()` pauses the graph, saves state, and returns control to the caller. Resume with `Command(resume=...)`; the value becomes the return value of `interrupt()`. This requires a checkpointer.

```python
from langgraph.types import Command, interrupt

def approve(state: State):
    decision = interrupt({"question": "Send this email?", "draft": state["draft"]})
    return {"approved": decision == "yes"}

graph = builder.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "t1"}}

result = graph.invoke({"draft": "Hi!"}, config)
print(result["__interrupt__"])                       # what the human should see

graph.invoke(Command(resume="yes"), config)          # continue from the pause
```

Typical uses: approve a tool call, edit a draft, ask the user for missing information. Because the node re-runs from its start on resume, keep side effects after the `interrupt()` call.

## 7. Streaming

`stream` yields results as the graph runs. Pick a `stream_mode`:

| Mode | Yields |
|---|---|
| `"values"` | The full state after each step |
| `"updates"` | Only the changes each node made, keyed by node name |
| `"messages"` | LLM tokens as they are generated, with metadata |
| `"custom"` | Anything your nodes send with `get_stream_writer()` |
| `"debug"` | Detailed events for each task |

```python
for chunk in graph.stream({"messages": [("human", "hi")]}, config, stream_mode="updates"):
    print(chunk)

for token, meta in graph.stream(inputs, config, stream_mode="messages"):
    print(token.content, end="")
```

You can pass a list of modes to get tuples of `(mode, chunk)`. Use `astream` in async code.

## 8. Subgraphs and multi-agent systems

A compiled graph can be used as a node in another graph, which lets you build hierarchical systems and reuse components. Parent and child can share state keys or you can transform the state in a wrapper node.

```python
parent.add_node("research", research_graph)   # research_graph is a compiled StateGraph
```

### Supervisor pattern (`langgraph-supervisor`)

A central agent decides which specialist to call and collects the results.

```python
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph_supervisor import create_supervisor

model = init_chat_model("openai:gpt-4o-mini")
math_agent = create_agent(model, tools=[add], name="math_expert")
research_agent = create_agent(model, tools=[search], name="research_expert")

workflow = create_supervisor(
    [math_agent, research_agent],
    model=model,
    prompt="Delegate math to math_expert and lookups to research_expert.",
)
app = workflow.compile(checkpointer=InMemorySaver())
```

Agents need unique `name`s. `create_supervisor` returns an uncompiled `StateGraph`; compile it yourself. Use `output_mode="full_history"` to keep each agent's messages.

### Swarm pattern (`langgraph-swarm`)

Agents hand control directly to one another with handoff tools; the swarm remembers the active agent between turns (this needs a checkpointer).

```python
from langgraph_swarm import create_handoff_tool, create_swarm

alice = create_agent(
    model, tools=[add, create_handoff_tool(agent_name="Bob")], name="Alice",
    system_prompt="You are Alice, a math expert.",
)
bob = create_agent(
    model, tools=[create_handoff_tool(agent_name="Alice")], name="Bob",
    system_prompt="You are Bob. Hand math questions to Alice.",
)

app = create_swarm([alice, bob], default_active_agent="Alice").compile(
    checkpointer=InMemorySaver()
)
```

Choose a supervisor for central control and predictable routing, and a swarm when agents should talk to the user directly and pass the conversation along.

## 9. Visualising and debugging

```python
print(graph.get_graph().draw_mermaid())          # Mermaid diagram of nodes and edges
graph.get_graph().draw_mermaid_png()              # PNG bytes (needs network or extra deps)
```

In a notebook, display the PNG with `IPython.display.Image`. With `LANGSMITH_TRACING=true` every node, model call and tool call is traced ([langsmith.md](./langsmith.md)).

## 10. Dev server, Studio and deployment (`langgraph-cli`)

A **LangGraph server** exposes your graphs through an API (assistants, threads, runs, streaming, persistence). Local development:

```bash
uv run langgraph new my_agent --template new-langgraph-project-python   # scaffold
uv run langgraph dev                  # run locally with hot reload; opens LangGraph Studio
uv run langgraph validate             # check langgraph.json
uv run langgraph build -t my-agent    # build a Docker image
```

The server is configured by a `langgraph.json` in the project root:

```json
{
  "dependencies": ["."],
  "graphs": { "agent": "./src/agent.py:graph" },
  "env": ".env"
}
```

`graphs` maps an ID to the module path and the variable that holds the compiled graph. The local `dev` server uses an in-memory runtime; the cloud/self-hosted server adds Postgres persistence. Studio lets you run the graph, inspect each step and edit state.

Call a running server from Python with the SDK:

```python
from langgraph_sdk import get_sync_client

client = get_sync_client(url="http://localhost:2024")
thread = client.threads.create()
for chunk in client.runs.stream(
    thread["thread_id"], "agent", input={"messages": [("human", "hi")]}, stream_mode="updates"
):
    print(chunk)
```

## 11. Choosing between the layers

| Need | Use |
|---|---|
| A single agent that calls tools in a loop | `langchain.agents.create_agent` |
| Custom flow: branches, loops, special state, several stages | `StateGraph` (this doc) |
| Several specialist agents | `langgraph-supervisor` or `langgraph-swarm` |
| A visual prototype or an instant API | Langflow ([langflow.md](./langflow.md)) |

`langgraph.prebuilt.create_react_agent` still exists but is the older entry point; prefer `create_agent` for new code.

## 12. Testing tips

- Build graphs with fake models (`GenericFakeChatModel` from `langchain_core.language_models.fake_chat_models`) so tests run offline.
- Test nodes as plain functions, and the whole graph with `invoke` on a fresh `InMemorySaver` per test.
- Use `stream_mode="updates"` to assert which nodes ran and in which order.

## References

- https://docs.langchain.com/oss/python/langgraph
- https://github.com/langchain-ai/langgraph
