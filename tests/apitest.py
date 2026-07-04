from dotenv import load_dotenv
import os
import httpx

load_dotenv()

key = os.getenv("LLM_API_KEY")

print("KEY =", key)

headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
}

print("HEADERS =", headers)

r = httpx.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers=headers,
    json={
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Say hello"}],
    }
)

print(r.status_code)
print(r.text)