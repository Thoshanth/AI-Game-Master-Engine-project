import os
import time
from openai import OpenAI
from dotenv import load_dotenv
from backend.logger import get_logger

load_dotenv()
logger = get_logger("llm_client")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

PRIMARY_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
FALLBACK_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
]


def chat_completion(
    messages: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    models_to_try = [PRIMARY_MODEL] + FALLBACK_MODELS

    for i, model in enumerate(models_to_try):
        try:
            logger.debug(f"LLM | model={model} | attempt={i+1}")

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                extra_headers={
                    "HTTP-Referer": "https://ai-game-master.local",
                    "X-Title": "AI Game Master Engine",
                },
            )

            result = response.choices[0].message.content
            logger.debug(f"LLM response | chars={len(result)}")
            return result

        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                logger.warning(f"Rate limit on {model} | trying fallback")
                if i < len(models_to_try) - 1:
                    time.sleep(1)
                    continue
                raise Exception(
                    "All models rate limited. Wait for reset or add credits."
                )
            raise

    raise Exception("No models available")


def chat_completion_json(
    messages: list[dict],
    max_tokens: int = 1024,
) -> str:
    return chat_completion(
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.1,
    )