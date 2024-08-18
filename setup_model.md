# AgileCoder Model Configuration Guide

This guide provides instructions for configuring the environment for different models supported by AgileCoder.

## OpenAI

Set the following environment variable:

```bash
OPENAI_API_KEY="your_api_key_here"
```

To run AgileCoder using OpenAI’s GPT models, specify the backend model as either GPT-3.5 or GPT-4 with the following commands:

```bash
agilecoder --task <your_task> --model "GPT_3_5_TURBO"
agilecoder --task <your_task> --model "GPT_4"
```

## Anthropic 
Set the following environment variables:
```bash
MODEL_NAME=<a_model_name_of_claude>
ANTHROPIC_API_KEY=<your_api_key>
```

Replace ```<a_model_name_of_claude>``` with the model name supported by Claude, for example, claude-3-haiku-20240307.

Run AgileCoder using an Anthropic Claude model with the command:

```bash
agilecoder --task <your_task> --model "ANTHROPIC_CLAUDE"
```

## Custom Model with Ollama
Ensure your model is hosted at the URL http://localhost:11434/api/chat, and set the following variable:

```
MODEL_NAME=<model_name>
```

Replace <model_name> with the model name supported by Ollama, for example, llama3.
Run AgileCoder using an Ollama model with the command:

```bash
agilecoder --task <your_task> --model "OLLAMA"
```
