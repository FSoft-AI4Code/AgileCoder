This guide helps you configure the environment for different models

  * OpenAI

Please set the following environment variables:
```bash
 OPENAI_API_KEY="your_api_key_here"
```

Run AgileCoder by specifying the backend model as GPT-3.5 or GPT-4 below:

```bash
agilecoder --task <yourtask> --model "GPT_3_5_TURBO"
agilecoder --task <yourtask> --model "GPT_4"
```

  * Anthropic

Please set the following environment variables:
```bash
MODEL_NAME=<a_model_name_of_claude>
ANTHROPIC_API_KEY=<your_api_key>
```
where MODEL_NAME is the model name supported by Claude, e.g. `claude-3-haiku-20240307`

Run AgileCoder by running the command below:
```bash
agilecoder --task <yourtask> --model "ANTHROPIC_CLAUDE"
```

  * Ollama

Please host your model on the url `http://localhost:11434/api/chat`, and set the following variables:
```bash
MODEL_NAME=<model_name>
```
where MODEL_NAME is the model name supported by Ollama, e.g. llama3
Run AgileCoder by running the command below:
```bash
agilecoder --task <yourtask> --model "OLLAMA"
```
