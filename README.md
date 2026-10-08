# llm-sandbox

Sandbox for LLM application development: LangChain, LangGraph, Langflow, LangSmith and LLM provider SDKs. Managed with [uv](https://docs.astral.sh/uv/).

## Setup

    uv sync
    cp .env.example .env   # add your API keys

## Usage

    uv run langflow run            # start Langflow UI
    uv run jupyter lab             # notebooks
    uv run pytest                  # tests
    uv run ruff check .            # lint

## Included

- Frameworks: langchain, langgraph, langflow
- Observability / evaluation: langsmith (set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in `.env` to trace runs)
- Providers: OpenAI, Anthropic, Google GenAI, Ollama, HuggingFace
- Vector stores / embeddings: chromadb, faiss-cpu, sentence-transformers
- Utilities: tiktoken, tenacity, pydantic, python-dotenv, httpx
