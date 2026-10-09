# Choosing an LLM

Lumen plans each answer with a large language model (LLM). lumen-napari uses whatever Lumen is configured to use.

## From an environment variable

When napari starts the chat from the **Ask Lumen** dock, Lumen picks the first provider whose key is set in the environment, in this order:

| Provider | Environment variable |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Google Gemini | `GEMINI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| AWS Bedrock | `AWS_ACCESS_KEY_ID` |
| Mistral | `MISTRAL_API_KEY` |
| Azure OpenAI or Azure Mistral | `AZUREAI_ENDPOINT_KEY` |
| Groq | `GROQ_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Kilo | `KILO_API_KEY` |

With none of these set, Lumen falls back to a local Anaconda AI Navigator server, which must be running.

Set the variable in the same shell before you launch napari:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
napari
```

!!! warning "Keep keys out of files"
    Do not paste API keys into scripts, notebooks or the chat. Set them in your shell or a secret manager, and rotate a key that was shared by accident.

## Use your Claude, ChatGPT, Copilot or Antigravity subscription

Lumen can run on a coding CLI you are already signed in to, so no API key is needed. Install and sign in to the CLI first, then name the provider in `LUMEN_NAPARI_PROVIDER` before starting napari:

| Subscription | CLI to sign in to | `LUMEN_NAPARI_PROVIDER` |
|---|---|---|
| Claude (Pro, Max, Team) | [Claude Code](https://claude.com/claude-code) (`claude`) | `claude-code` |
| ChatGPT (Plus, Pro, Team) | [Codex CLI](https://github.com/openai/codex) (`codex`) | `codex-cli` |
| GitHub Copilot | [Copilot CLI](https://github.com/github/copilot-cli) (`copilot`) | `copilot-cli` |
| Google Antigravity | Antigravity CLI (`agy`) | `antigravity-cli` |

```bash
export LUMEN_NAPARI_PROVIDER=claude-code
napari
```

These providers run the CLI in a read-only or planning mode and are meant for local use. They cannot make native tool calls, so lumen-napari offers its segment and measure actions to them as tools, which they can call; every question works, just more slowly. They are slower than an API key, because each answer waits for the CLI to finish, and they cannot read images.

`LUMEN_NAPARI_PROVIDER` takes any Lumen provider name, so it also forces a key-based one when several keys are set, for example `anthropic` or `ollama`. An unknown name fails with the list of valid ones.

## Choosing a model in Python

To pick the provider and model yourself, start the chat from Python and pass an `llm`. Every keyword argument of `LumenServer` goes to Lumen's `ExplorerUI`:

```python
import napari
from lumen.ai.llm import Anthropic
from lumen_napari.app import LumenServer

viewer = napari.Viewer()
server = LumenServer(viewer, llm=Anthropic(model_kwargs={"default": {"model": "claude-sonnet-5-5"}}))
print(server.start())
napari.run()
```

## Local models

Lumen also runs on local models through Ollama, llama.cpp, MLX or LiteLLM, so images and measurements never leave your machine:

```python
from lumen.ai.llm import Ollama

server = LumenServer(viewer, llm=Ollama(model_kwargs={"default": {"model": "qwen3:8b"}}))
```

Smaller models plan less reliably. lumen-napari helps them where it can: its tools accept the table name for a layer name, strip units the model writes into SQL filters ("area > 50 µm²"), and segment automatically when a question needs objects that do not exist yet. Still, expect more retries than with a hosted frontier model.

## What the LLM sees

The LLM sees your questions, the layer names, shapes and pixel sizes, table schemas, summary statistics and the rows that SQL queries return. It does not see pixels: segmentation and measurement run locally in Python. See the [Lumen docs](https://lumen.holoviz.org) for each provider's options.
