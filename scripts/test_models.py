from anthropic import Anthropic
import os

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

models = [
"claude-3-opus-20240229",
"claude-3-sonnet-20240229",
"claude-3-haiku-20240307",
"claude-3-5-sonnet-latest",
]

for model in models:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}]
        )
        print(f"{model}: OK")
    except Exception as e:
        print(f"{model}: FAIL -> {e}")
