import json
import logging
import httpx
from api.config import settings
from tenacity import retry,stop_after_attempt,wait_exponential,retry_if_exception_type

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def is_trivial_diff(parsed_files: list[dict]) -> bool:
    for file in parsed_files:
        for line in file["content"].splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return False
    return True

MAX_DIFF_CHARS=8_000

def truncate_diff(parsed_files: list[dict]) -> tuple[str, bool]:
    lines = []
    total_chars = 0
    truncated = False

    for file in parsed_files:
        lines.append(f"### {file['filename']}")
        for line in file["content"].splitlines():
            if total_chars + len(line) > MAX_DIFF_CHARS:
                truncated = True
                break
            lines.append(line)
            total_chars += len(line)
        if truncated:
            break

    if truncated:
        lines.append("\n[diff truncated due to size]")

    return "\n".join(lines), truncated

SYSTEM_PROMPT = """You are a code review assistant. Analyze the provided code diff and return findings as a JSON array.

Rules:
- Respond with ONLY a JSON array. No explanation, no markdown, no preamble.
- Each finding must match this exact schema:
  {
    "type": "bug | security | style | suggestion",
    "severity": "critical | high | medium | low",
    "file": "<filename>",
    "line": <integer>,
    "message": "<what the issue is>",
    "suggestion": "<how to fix it>",
    "source": "llm"
  }
- Only report findings on lines that appear in the diff.
- Do not invent line numbers. If you are unsure of the exact line, omit the finding.
- Focus on logic bugs, security issues, and meaningful suggestions that static tools miss.
- If there are no findings, return an empty array: []
"""

logger=logging.getLogger(__name__)

@retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1,min=2,max=30),
        stop=stop_after_attempt(4),
    )

def run_llm_review(parsed_files:list[dict])-> list[dict]:
    if is_trivial_diff(parsed_files):
        logger.info("Skipping LLM review -trivial diff")
        return []
    
      
    diff_text, was_truncated= truncate_diff(parsed_files)
    if len(diff_text) > 4000:
        diff_text = diff_text[:4000] 
    if was_truncated:
        logger.info("Diff truncated before LLM review")
    logger.info("Using API key: %s", settings.llm_api_key[:15])
    print(settings.model_dump())
    response=httpx.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={
            "model":settings.llm_model,
            "messages":[
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":diff_text},
            ]  
        },
        timeout=30.0
    )
    response.raise_for_status()

    data=response.json()
    raw=data["choices"][0]["message"]["content"].strip()
    logger.info("LLM raw response: %s", raw[:500])

    usage=data.get("usage",{})
    logger.info(
        "LLM review compelte",
        extra={
            "input_tokens":usage.get("prompt_tokens"),
            "output_tokens":usage.get("completion_token"),
            "total_tokens":usage.get("total_tokens"),
            "truncated":was_truncated,
        },
    )   


    try:
        findings=json.loads(raw)
    
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON outpute: %s",raw[:200])
        return []

    if not isinstance(findings,list):
        logger.error("LLM returned non-list JSON: %s",raw[:200])
        return[]
 
    return findings   