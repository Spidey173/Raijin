import json
import logging
import time
import re
import requests
from typing import Dict, List, Any, Optional, Tuple
from app.config import settings

logger = logging.getLogger("raijin")

ALLOWED_CATEGORIES = [
    "Food",
    "Shopping",
    "Travel",
    "Transport",
    "Utilities",
    "Cash Withdrawal",
    "Entertainment",
    "Other"
]

def clean_json_response(text: str) -> str:
    """
    Cleans raw LLM response text, stripping markdown code blocks and extracting
    the valid JSON array or object.
    """
    if not text:
        return ""
    text = text.strip()
    
    # 1. Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) > 1:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    # 2. Check if text is directly parseable
    try:
        json.loads(text)
        return text
    except Exception:
        pass
        
    # 3. Extract JSON object
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    # 4. Extract JSON array
    first_bracket = text.find('[')
    last_bracket = text.rfind(']')
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        candidate = text[first_bracket:last_bracket + 1]
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass
            
    return text

def is_valid_key(key: Optional[str]) -> bool:
    if not key:
        return False
    k = key.strip().lower()
    if k.startswith("your_") or k.startswith("placeholder") or "api_key_here" in k:
        return False
    return len(k) > 5

def get_active_provider() -> str:
    """
    Determines the active LLM provider.
    Supported: 'groq', 'google', 'anthropic', 'openai', or 'mock'.
    """
    provider = (settings.LLM_PROVIDER or "auto").lower().strip()
    
    if provider in ["groq"]:
        return "groq"
    if provider in ["google", "gemini"]:
        return "google"
    if provider in ["anthropic", "claude"]:
        return "anthropic"
    if provider in ["openai"]:
        return "openai"
        
    # Auto-detection by valid keys
    if is_valid_key(settings.GROQ_API_KEY):
        return "groq"
    if is_valid_key(settings.GEMINI_API_KEY):
        return "google"
    if is_valid_key(settings.ANTHROPIC_API_KEY):
        return "anthropic"
    if is_valid_key(settings.OPENAI_API_KEY):
        return "openai"
        
    if settings.GROQ_API_KEY.strip():
        return "groq"
    if settings.GEMINI_API_KEY.strip():
        return "google"
    if settings.ANTHROPIC_API_KEY.strip():
        return "anthropic"
    if settings.OPENAI_API_KEY.strip():
        return "openai"

    return "mock"

def _call_groq(prompt: str, response_json: bool) -> str:
    if not is_valid_key(settings.GROQ_API_KEY):
        logger.warning("GROQ_API_KEY is not set or placeholder. Falling back to mock generator.")
        return get_mock_response(prompt, response_json)

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY.strip()}",
        "Content-Type": "application/json"
    }
    
    model = settings.GROQ_MODEL.strip() or "qwen/qwen3.8-27b"
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert financial transaction classification and analysis engine. You output strictly valid JSON without preamble or conversational text."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1
    }
    
    if response_json:
        payload["response_format"] = {"type": "json_object"}
        
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=25.0)
        if response.status_code == 400 and response_json and "response_format" in response.text:
            logger.info("Model does not support response_format json_object on Groq; retrying without it.")
            payload.pop("response_format", None)
            response = requests.post(url, json=payload, headers=headers, timeout=25.0)
            
        response.raise_for_status()
        res_data = response.json()
        return res_data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"Groq API call error: {e}")
        raise e

def _call_google(prompt: str, response_json: bool) -> str:
    if not is_valid_key(settings.GEMINI_API_KEY):
        logger.warning("GEMINI_API_KEY is not set or placeholder. Falling back to mock generator.")
        return get_mock_response(prompt, response_json)

    model = settings.GEMINI_MODEL.strip() or "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY.strip()}"
    headers = {"Content-Type": "application/json"}
    
    payload: Dict[str, Any] = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    if response_json:
        payload["generationConfig"] = {
            "responseMimeType": "application/json"
        }
        
    response = requests.post(url, json=payload, headers=headers, timeout=25.0)
    response.raise_for_status()
    res_data = response.json()
    candidates = res_data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "")
    raise ValueError(f"Unexpected Google Gemini response structure: {res_data}")

def _call_anthropic(prompt: str, response_json: bool) -> str:
    if not is_valid_key(settings.ANTHROPIC_API_KEY):
        logger.warning("ANTHROPIC_API_KEY is not set or placeholder. Falling back to mock generator.")
        return get_mock_response(prompt, response_json)

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY.strip(),
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    model = settings.ANTHROPIC_MODEL.strip() or "claude-3-5-haiku-20241022"
    payload: Dict[str, Any] = {
        "model": model,
        "max_tokens": 2048,
        "temperature": 0.1,
        "system": "You are an expert financial transaction classification and analysis engine. You output strictly valid JSON without preamble or conversational text.",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, json=payload, headers=headers, timeout=25.0)
    response.raise_for_status()
    res_data = response.json()
    content = res_data.get("content", [])
    if content:
        return content[0].get("text", "")
    raise ValueError(f"Unexpected Claude response structure: {res_data}")

def _call_openai(prompt: str, response_json: bool) -> str:
    if not is_valid_key(settings.OPENAI_API_KEY):
        logger.warning("OPENAI_API_KEY is not set or placeholder. Falling back to mock generator.")
        return get_mock_response(prompt, response_json)

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY.strip()}",
        "Content-Type": "application/json"
    }
    model = settings.OPENAI_MODEL.strip() or "gpt-4o-mini"
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert financial transaction classification and analysis engine. You output strictly valid JSON without preamble or conversational text."
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }
    if response_json:
        payload["response_format"] = {"type": "json_object"}
    response = requests.post(url, json=payload, headers=headers, timeout=25.0)
    response.raise_for_status()
    res_data = response.json()
    return res_data["choices"][0]["message"]["content"]

def call_llm_api_with_retry(prompt: str, response_json: bool = True) -> str:
    """
    Calls configured LLM provider with exponential backoff retry.
    """
    provider = get_active_provider()
    if provider == "mock":
        return get_mock_response(prompt, response_json)

    max_retries = 3
    delay = 1.5

    for attempt in range(max_retries + 1):
        try:
            if provider == "groq":
                return _call_groq(prompt, response_json)
            elif provider == "google":
                return _call_google(prompt, response_json)
            elif provider == "anthropic":
                return _call_anthropic(prompt, response_json)
            elif provider == "openai":
                return _call_openai(prompt, response_json)
            else:
                return get_mock_response(prompt, response_json)
        except Exception as e:
            logger.warning(f"LLM API call ({provider}) attempt {attempt + 1}/{max_retries + 1} failed: {e}")
            if attempt == max_retries:
                logger.error(f"All {provider} retries exhausted.")
                raise e
            time.sleep(delay)
            delay *= 2.0

    return ""

def call_gemini_api_with_retry(prompt: str, response_json: bool = True) -> str:
    """
    Primary interface and backward-compatible wrapper for LLM requests.
    """
    return call_llm_api_with_retry(prompt, response_json)

def classify_categories_batch(transactions: List[Dict[str, Any]]) -> List[Tuple[Any, str, str, bool]]:
    """
    Classifies a batch of transactions missing categories using the configured LLM.
    Uses robust ID tracking to prevent index-shift or out-of-bounds array hazards.
    
    Returns: List of tuples (id_or_index, category, raw_response, llm_failed)
    """
    if not transactions:
        return []

    # Map items by unique ID (either txn['id'] or txn['index'] or row index)
    items_to_classify = []
    id_map = {}
    for i, txn in enumerate(transactions):
        item_id = txn.get("id") if txn.get("id") is not None else txn.get("index", i)
        id_map[str(item_id)] = item_id
        items_to_classify.append({
            "id": item_id,
            "index": item_id,
            "merchant": txn.get("merchant", "Unknown"),
            "amount": txn.get("amount", 0.0),
            "currency": txn.get("currency", "INR"),
            "notes": txn.get("notes", "")
        })

    prompt = f"""
You are an expert financial transaction classification engine.
Classify each transaction below into exactly ONE of these allowed categories:
{", ".join(ALLOWED_CATEGORIES)}

Transactions to classify:
{json.dumps(items_to_classify, indent=2)}

Output format:
Return a valid JSON object with a key "classifications" containing an array of objects.
Each object must specify "id" (matching the input transaction ID) and "category".

Example response:
{{
  "classifications": [
    {{"id": {items_to_classify[0]["id"]}, "category": "Food"}}
  ]
}}
"""

    try:
        response_text = call_gemini_api_with_retry(prompt, response_json=True)
        clean_text = clean_json_response(response_text)
        data = json.loads(clean_text)
        
        # Handle dict wrapping or raw list
        results_list = []
        if isinstance(data, dict):
            if "classifications" in data and isinstance(data["classifications"], list):
                results_list = data["classifications"]
            else:
                for val in data.values():
                    if isinstance(val, list):
                        results_list = val
                        break
        elif isinstance(data, list):
            results_list = data
            
        parsed_results = []
        processed_ids = set()

        for res in results_list:
            if not isinstance(res, dict):
                continue
            raw_id = res.get("id") if res.get("id") is not None else res.get("index")
            if raw_id is None:
                continue
            id_key = str(raw_id)
            if id_key in id_map:
                actual_id = id_map[id_key]
                cat = res.get("category", "Other")
                if cat not in ALLOWED_CATEGORIES:
                    cat = "Other"
                parsed_results.append((actual_id, cat, response_text, False))
                processed_ids.add(actual_id)

        # Fallback for any items missed by the LLM
        for item in items_to_classify:
            actual_id = item["id"]
            if actual_id not in processed_ids:
                parsed_results.append((actual_id, "Other", response_text, False))

        return parsed_results

    except Exception as e:
        logger.error(f"Category classification failed: {e}", exc_info=True)
        return [(item["id"], "Other", str(e), True) for item in items_to_classify]

def generate_job_summary(
    stats_summary: Dict[str, Any],
    transactions: List[Dict[str, Any]],
    anomaly_count: int
) -> Dict[str, Any]:
    """
    Generates a narrative spending summary and contextual explanation.
    Maintains deterministic calculation boundaries for spend and top merchants.
    """
    total_txns = len(transactions)
    # Deterministic risk rating baseline
    if anomaly_count >= 3:
        deterministic_risk = "high"
    elif anomaly_count > 0:
        deterministic_risk = "medium"
    else:
        deterministic_risk = "low"

    prompt = f"""
Analyze the following financial transaction summary statistics and write a professional narrative.

Summary Statistics:
{json.dumps(stats_summary, indent=2)}

Anomaly Count: {anomaly_count}
Total Transactions: {total_txns}
Baseline Risk Level: {deterministic_risk}

Output format:
Return a valid JSON object matching:
{{
  "narrative": "A concise, executive summary explaining the main spending areas, anomaly drivers, and transaction patterns.",
  "risk_level": "low" | "medium" | "high"
}}
"""
    try:
        response_text = call_gemini_api_with_retry(prompt, response_json=True)
        clean_text = clean_json_response(response_text)
        summary_data = json.loads(clean_text)
        
        narrative = summary_data.get("narrative") or f"Processed {total_txns} transactions with {anomaly_count} anomalies flagged."
        risk = (summary_data.get("risk_level") or deterministic_risk).lower()
        if risk not in ["low", "medium", "high"]:
            risk = deterministic_risk
            
        return {
            "narrative": narrative,
            "risk_level": risk,
            "anomaly_count": anomaly_count,
            "total_spend_by_currency": stats_summary.get("total_spend_by_currency", {}),
            "top_3_merchants": summary_data.get("top_3_merchants", stats_summary.get("top_3_merchants", []))
        }
    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        return {
            "narrative": f"Automated summary: Processed {total_txns} transactions with {anomaly_count} anomalies detected.",
            "risk_level": deterministic_risk,
            "anomaly_count": anomaly_count,
            "total_spend_by_currency": stats_summary.get("total_spend_by_currency", {}),
            "top_3_merchants": stats_summary.get("top_3_merchants", [])
        }

def get_mock_response(prompt: str, response_json: bool) -> str:
    """
    Fallback mock generator when API keys are not provided.
    """
    if "Classify each transaction" in prompt or "Transactions to classify" in prompt or "classifications" in prompt:
        try:
            ids = [int(i) for i in re.findall(r'"id":\s*(\d+)', prompt)]
            if not ids:
                ids = [int(i) for i in re.findall(r'"index":\s*(\d+)', prompt)]
        except Exception:
            ids = []
            
        classifications = []
        seen = set()
        for idx in ids:
            if idx not in seen:
                seen.add(idx)
                cat = ALLOWED_CATEGORIES[idx % len(ALLOWED_CATEGORIES)]
                classifications.append({"id": idx, "index": idx, "category": cat})
        return json.dumps({"classifications": classifications})
        
    elif "narrative" in prompt:
        return json.dumps({
            "narrative": "Automated financial report: Transaction patterns reflect regular operational and personal expenses with expected distribution across domestic merchants.",
            "risk_level": "medium"
        })
        
    return "{}"
