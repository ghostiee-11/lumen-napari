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
