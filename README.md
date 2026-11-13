# llm-sandbox

Sandbox for LLM application development: LangChain, LangGraph, Langflow, LangSmith and LLM provider SDKs. Managed with [uv](https://docs.astral.sh/uv/).

## Setup

    uv sync
    cp .env.example .env   # add your API keys

`langchain-deepagents/python` is part of the root uv workspace. To run one of
its scripts with both the root and member dependencies in the shared environment:

    cd langchain-deepagents/python
    uv run --all-packages python m1/m1.2_scratch_agent.py

This uses the root `.venv` and `uv.lock`; `--all-packages` prevents syncing only
the member's dependencies into the shared environment. The workspace supports
Python `>=3.12,<3.15`, the intersection of the root and member requirements.

## Usage

    uv run langflow run            # start Langflow UI
    uv run jupyter lab             # notebooks
    uv run pytest                  # tests
    uv run ruff check .            # lint

## Included

- Frameworks: langchain, langgraph (with sqlite checkpointer, supervisor, swarm and CLI), langflow
- Observability / evaluation: langsmith (set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in `.env` to trace runs)
- Providers: OpenAI, Anthropic, Google GenAI, Ollama, HuggingFace
- Vector stores / embeddings: chromadb, faiss-cpu, sentence-transformers
- Utilities: tiktoken, tenacity, pydantic, python-dotenv, httpx

## Docs

- [docs/langchain.md](docs/langchain.md): LangChain packages and components
- [docs/langgraph.md](docs/langgraph.md): stateful graphs, persistence, human-in-the-loop and multi-agent systems
- [docs/langsmith.md](docs/langsmith.md): tracing, datasets and evaluation with LangSmith and openevals
- [docs/langflow.md](docs/langflow.md): the visual builder, API usage and custom components
