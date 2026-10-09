# LangChain

LangChain is a framework for building applications on top of LLMs. It gives you a common interface for models, prompts, tools, retrievers and agents, so you can swap providers without rewriting your app. [LangGraph](./langgraph.md) is the lower-level orchestration engine that powers LangChain agents.

Installed versions: `langchain` 1.3, `langchain-core` 1.6, `langgraph` 1.2.

## 1. The package map

LangChain is split into many packages. Knowing which one owns what makes imports and errors much easier to understand.

| Package | Purpose |
|---|---|
| `langchain-core` | Base abstractions: messages, prompts, `Runnable`, output parsers, tools, `Document`, `Embeddings`, `VectorStore`, callbacks. Everything else depends on it. |
| `langchain` | High-level entry points: `create_agent`, `init_chat_model`, `init_embeddings`, agent middleware, `langchain.tools`, `langchain.messages`. |
| `langgraph` | Graph-based runtime for stateful, multi-step, resumable workflows and agents (`StateGraph`, checkpointers, human-in-the-loop). `create_agent` runs on it. See [langgraph.md](./langgraph.md). |
| `langchain-openai`, `langchain-anthropic`, `langchain-google-genai`, `langchain-ollama`, `langchain-huggingface` | Provider integrations (chat models and embeddings). Install only the providers you use. |
| `langchain-text-splitters` | Splits documents into chunks for embedding and retrieval. |
| `langchain-chroma` | Chroma vector store integration (backed by `chromadb`). |
| `langchain-community` | Large collection of third-party integrations (loaders, FAISS, etc.). Being sunset: prefer standalone integration packages where they exist. |
| `langchain-classic` | Legacy chains, `AgentExecutor`, old memory classes. Only for maintaining pre-1.0 code. |
| `langchain-experimental` | Experimental features with no stability promise. |
| `langchainhub` | Client for pulling shared prompts from the LangChain Hub. |
| `langsmith` | Tracing and evaluation. See [langsmith.md](./langsmith.md). |

Related packages in this project: `faiss-cpu` (vector index used by the FAISS store), `sentence-transformers` (local embedding models), `tiktoken` (token counting), `tenacity` (retries), `openai` and `anthropic` (raw provider SDKs).

## 2. Configuration

Copy `.env.example` to `.env` and fill in the keys. Load them at the top of your script:

```python
from dotenv import load_dotenv

load_dotenv()  # reads OPENAI_API_KEY, ANTHROPIC_API_KEY, LANGSMITH_*, ...
```

## 3. Chat models

A chat model takes a list of messages and returns an `AIMessage`. `init_chat_model` creates one for any provider from a single string.

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("anthropic:claude-sonnet-4-5", temperature=0)
# or: init_chat_model("openai:gpt-4o-mini"), init_chat_model("ollama:llama3.1")

response = model.invoke("Explain vector databases in one sentence.")
print(response.content)

for chunk in model.stream("Write a haiku about uv."):   # streaming
    print(chunk.content, end="", flush=True)
```

You can also use the provider classes directly (`ChatOpenAI`, `ChatAnthropic`, `ChatGoogleGenerativeAI`, `ChatOllama`) when you need provider-specific options.

Every model is a `Runnable` (see section 6), so it also supports `ainvoke`, `batch`, `abatch` and `astream`.

### Messages

Conversations are lists of typed messages from `langchain.messages`:

| Type | Meaning |
|---|---|
| `SystemMessage` | Instructions that steer the model |
| `HumanMessage` | User input |
| `AIMessage` | Model output; may contain `tool_calls` and `usage_metadata` |
| `ToolMessage` | The result of a tool call, linked by `tool_call_id` |

```python
from langchain.messages import SystemMessage, HumanMessage

model.invoke([SystemMessage("Answer tersely."), HumanMessage("What is RAG?")])
```

Plain dicts such as `{"role": "user", "content": "hi"}` and tuples such as `("human", "hi")` are accepted too.

## 4. Prompts

Prompt templates build messages from variables.

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a {role}."),
    ("human", "{question}"),
])
messages = prompt.invoke({"role": "data engineer", "question": "What is a DAG?"})
```

Use `MessagesPlaceholder("history")` to inject a list of earlier messages, and `FewShotChatMessagePromptTemplate` for examples.

## 5. Structured output and parsers

The preferred way to get typed data back is `with_structured_output`, which uses the provider's native tool/JSON mode:

```python
from pydantic import BaseModel, Field

class Person(BaseModel):
    name: str = Field(description="Full name")
    age: int

structured = model.with_structured_output(Person)
person = structured.invoke("Ada Lovelace was 36 when she died.")
```

Output parsers (`StrOutputParser`, `JsonOutputParser`, `PydanticOutputParser`) from `langchain_core.output_parsers` turn raw model text into other formats and are useful in chains.

## 6. Runnables and LCEL

Every component (prompt, model, parser, retriever, tool, graph) implements the `Runnable` interface: `invoke`, `batch`, `stream` and their `a`-prefixed async versions. The `|` operator composes them into a sequence. This is called LCEL (LangChain Expression Language).

```python
from langchain_core.output_parsers import StrOutputParser

chain = prompt | model | StrOutputParser()
chain.invoke({"role": "chef", "question": "How do I poach an egg?"})
chain.batch([{"role": "chef", "question": q} for q in ["Poach?", "Boil?"]])
```

Useful building blocks from `langchain_core.runnables`:

- `RunnableLambda(fn)`: wrap any Python function.
- `RunnablePassthrough()`: pass input through unchanged (often with `.assign(...)`).
- `RunnableParallel({...})`: run several runnables on the same input and collect a dict.
- `chain.with_retry()`, `chain.with_fallbacks([...])`, `chain.with_config({...})`: resilience and configuration.

## 7. Tools

A tool is a function the model can request. The `@tool` decorator builds the schema from the type hints and docstring.

```python
from langchain.tools import tool

@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

model_with_tools = model.bind_tools([add])
ai = model_with_tools.invoke("What is 3 + 4?")
print(ai.tool_calls)            # [{'name': 'add', 'args': {'a': 3, 'b': 4}, 'id': ...}]
add.invoke(ai.tool_calls[0]["args"])
```

Tools can also receive runtime context with `ToolRuntime`, injected state with `InjectedState`, and signal recoverable errors with `ToolException`.

## 8. Agents

`create_agent` builds a tool-calling agent: the model decides when to call tools, the tools run, and the loop repeats until the model answers. It is compiled as a LangGraph graph.

```python
from langchain.agents import create_agent

agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=[add],
    system_prompt="You are a helpful math assistant.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "What is 12 + 30?"}]})
print(result["messages"][-1].content)
```

Useful `create_agent` options: `response_format` (structured final answer), `checkpointer` (persistence), `store` (long-term memory), `middleware`, `name`.

### Middleware

Middleware hooks into the agent loop to customize behavior without rewriting the graph. Built-ins in `langchain.agents.middleware` include:

| Middleware | What it does |
|---|---|
| `SummarizationMiddleware` | Summarizes old messages when the context grows too large |
| `HumanInTheLoopMiddleware` | Pauses for human approval before selected tool calls |
| `ModelFallbackMiddleware`, `ModelRetryMiddleware`, `ToolRetryMiddleware` | Resilience against model/tool failures |
| `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware` | Cap runaway loops |
| `PIIMiddleware` | Redact or block personal data |
| `TodoListMiddleware` | Gives the agent a planning/to-do tool |
| `LLMToolSelectorMiddleware` | Picks relevant tools when you have many |
| `ContextEditingMiddleware` | Trims old tool results from the context |

Write your own with the decorators `@before_model`, `@after_model`, `@wrap_model_call`, `@wrap_tool_call`, `@dynamic_prompt`, or by subclassing `AgentMiddleware`:

```python
from langchain.agents.middleware import wrap_model_call

@wrap_model_call
def log_calls(request, handler):
    print("model call with", len(request.messages), "messages")
    return handler(request)

agent = create_agent("openai:gpt-4o-mini", tools=[add], middleware=[log_calls])
```

## 9. Embeddings, documents and vector stores (RAG)

Retrieval-augmented generation (RAG) feeds relevant text into the prompt. The pieces:

1. **Document loaders** produce `Document(page_content, metadata)` objects (`langchain_community.document_loaders`, e.g. `WebBaseLoader`, `PyPDFLoader`, `TextLoader`).
2. **Text splitters** chunk them.
3. **Embeddings** turn text into vectors.
4. **Vector stores** index and search the vectors.
5. **Retrievers** wrap a store behind `invoke(query) -> list[Document]`.

```python
from langchain.embeddings import init_embeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

embeddings = init_embeddings("openai:text-embedding-3-small")
# Local alternative: HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
chunks = splitter.split_documents([Document(page_content=long_text, metadata={"source": "notes"})])

store = Chroma(
    collection_name="notes",
    embedding_function=embeddings,
    persist_directory=".chroma",   # git-ignored
)
store.add_documents(chunks)

retriever = store.as_retriever(search_kwargs={"k": 4})
docs = retriever.invoke("What did the notes say about uv?")
```

Chroma collection names must be 3-512 characters from `[a-zA-Z0-9._-]`.

Other stores in this environment: `FAISS` (`langchain_community.vectorstores`, in-memory/file index), `InMemoryVectorStore` (`langchain_core.vectorstores`, good for tests), plus Qdrant, Weaviate and MongoDB integrations.

### Simple RAG chain

```python
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

rag_prompt = ChatPromptTemplate.from_template(
    "Answer using only this context:\n{context}\n\nQuestion: {question}"
)
format_docs = lambda docs: "\n\n".join(d.page_content for d in docs)

rag = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | rag_prompt | model | StrOutputParser()
)
rag.invoke("What did the notes say about uv?")
```

Alternatively, expose the retriever as a tool (`@tool` that calls `retriever.invoke`) and let an agent decide when to search.

## 10. LangGraph

Use LangGraph directly when you need explicit control flow: branches, loops, parallel steps, persistence, human approval, or several cooperating agents. `create_agent` already runs on it. A minimal graph with memory:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph

def chatbot(state: MessagesState):
    return {"messages": [model.invoke(state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "user-1"}}
graph.invoke({"messages": [("human", "My name is Sam.")]}, config)
graph.invoke({"messages": [("human", "What is my name?")]}, config)  # remembers
```

See [langgraph.md](./langgraph.md) for state and reducers, conditional edges, `Command` and `Send`, checkpointers and stores, human-in-the-loop, streaming, subgraphs, multi-agent patterns and the dev server.

## 11. Callbacks and tracing

Callbacks (`langchain_core.callbacks`) observe model, tool and chain events for logging or streaming. With `LANGSMITH_TRACING=true` every LangChain and LangGraph run is traced to LangSmith automatically; see [langsmith.md](./langsmith.md).

## 12. Practical tips

- Pin the provider in a single string (`"openai:gpt-4o-mini"`) and read it from an env var so you can switch models quickly.
- Use `tenacity` or `.with_retry()` for flaky network calls, and `tiktoken` to estimate token counts.
- Use `InMemoryVectorStore` with `DeterministicFakeEmbedding` and `GenericFakeChatModel` (from `langchain_core`) to write offline unit tests.
- Prefer `create_agent` over the legacy `AgentExecutor` in `langchain-classic`.
- Model names change often; check each provider's docs for current identifiers.

## References

- https://docs.langchain.com
- https://langchain-ai.github.io/langgraph/
