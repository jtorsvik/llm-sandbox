"""Model Initialization File

Configures the LLM model used throughout the course.

Default: Anthropic claude-haiku-4-5 (fast, cheap, great for learning).

═══════════════════════════════════════════════════════════════════════════
  ⚠  IMPORTANT: install the matching extra BEFORE swapping providers
═══════════════════════════════════════════════════════════════════════════

  Provider              Install command              Already installed?
  --------------------  ---------------------------  ---------------------
  Anthropic (default)   -                            yes (default dep)
  OpenAI                -                            yes (default dep)
  Azure OpenAI          uv sync --extra azure        no - install first
  AWS Bedrock           uv sync --extra bedrock      no - install first
  Google Vertex/Gemini  uv sync --extra google       no - install first

═══════════════════════════════════════════════════════════════════════════

To swap providers:
  1. Run the install command above (if needed).
  2. Comment out the active model line(s) below.
  3. Uncomment the section for your desired provider.
  4. Set the provider's env vars in `.env` (see notes inline).
"""

import os  # noqa: F401  # used in commented-out model examples below
from pathlib import Path

import truststore
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
ENV_PATH = (
    ROOT_ENV_PATH
    if ROOT_ENV_PATH.is_file()
    else Path(__file__).resolve().parent / ".env"
)
truststore.inject_into_ssl()
load_dotenv(dotenv_path=ENV_PATH, override=True)

from langchain.chat_models import init_chat_model

# ─── Google Gemini ────────────────────────────────────────────────────────────
# Install first:  uv sync --extra google
# Requires GOOGLE_API_KEY in .env
#
model = init_chat_model("google_genai:gemini-3.5-flash-lite")

# ═══ Default Models ══════════════════════════════════════════════════════════
# Workshop default: Anthropic claude-haiku-4-5, fast and cost-effective.
# Requires ANTHROPIC_API_KEY in .env
# model = init_chat_model("gem:claude-haiku-4-5", timeout=60, max_retries=2)

# A more capable model for steps that need stronger reasoning
# strong_model = init_chat_model(
#    "anthropic:claude-sonnet-5-5", timeout=120, max_retries=2
# )
# 
# ═══ Alternative Models (comment out default above, uncomment one below) ═════
# model = init_chat_model("anthropic:claude-sonnet-5-5")
# model = init_chat_model("openai:gpt-6-luna", use_responses_api=True)
# strong_model = init_chat_model("openai:gpt-6.1-sol", use_responses_api=True)

# ═══ Open-Source / Alternative Hosted Models ══════════════════════════════════

# ═══ Cloud Provider Models (extra install required, see table above) ═════════
# ─── Azure OpenAI ─────────────────────────────────────────────────────────────
# Install first:  uv sync --extra azure
# Requires AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, OPENAI_API_VERSION in .env
# Set your deployment name directly below (it isn't read from .env)
#
# from langchain_openai import AzureChatOpenAI
# model = AzureChatOpenAI(azure_deployment="gpt-4.1", api_version="2024-12-01-preview")


# ─── AWS Bedrock ──────────────────────────────────────────────────────────────
# Install first:  uv sync --extra bedrock
# Requires AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY in .env
# Set your region directly below (it isn't read from .env)
#
# from langchain_aws import ChatBedrockConverse
# model = ChatBedrockConverse(model_id="anthropic.claude-sonnet-4-6", region_name="us-east-1")



