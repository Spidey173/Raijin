from unittest.mock import patch, MagicMock
import json
from app.services.llm import (
    classify_categories_batch,
    generate_job_summary,
    call_gemini_api_with_retry,
    clean_json_response,
    get_active_provider,
    _call_groq,
    _call_anthropic,
    _call_google,
)
from app.config import settings

def test_classify_categories_batch_with_mock_api():
    # Mock response returning a JSON array of classifications
    mock_response = json.dumps([
        {"index": 0, "category": "Food"},
        {"index": 1, "category": "Transport"}
    ])

    transactions = [
        {"index": 0, "merchant": "Swiggy", "amount": 150.0, "currency": "INR", "category": ""},
        {"index": 1, "merchant": "Uber", "amount": 250.0, "currency": "INR", "category": ""}
    ]

    with patch("app.services.llm.call_gemini_api_with_retry", return_value=mock_response):
        results = classify_categories_batch(transactions)
        
        assert len(results) == 2
        assert results[0][0] == 0
        assert results[0][1] == "Food"
        assert results[0][3] is False
        assert results[1][0] == 1
        assert results[1][1] == "Transport"
        assert results[1][3] is False

def test_generate_job_summary_with_mock_api():
    mock_summary_response = json.dumps({
        "total_spend_by_currency": {"INR": 10000.0, "USD": 50.0},
        "top_3_merchants": [
            {"merchant": "Amazon", "spend": 5000.0, "currency": "INR"}
        ],
        "anomaly_count": 1,
        "narrative": "A test spending narrative from the LLM.",
        "risk_level": "medium"
    })

    stats_summary = {
        "total_spend_by_currency": {"INR": 10000.0, "USD": 50.0},
        "top_3_merchants": [
            {"merchant": "Amazon", "spend": 5000.0, "currency": "INR"}
        ]
    }
    
    transactions = [
        {"merchant": "Amazon", "amount": 5000.0, "currency": "INR"}
    ]

    with patch("app.services.llm.call_gemini_api_with_retry", return_value=mock_summary_response):
        result = generate_job_summary(stats_summary, transactions, 1)
        
        assert result["risk_level"] == "medium"
        assert result["anomaly_count"] == 1
        assert result["narrative"] == "A test spending narrative from the LLM."
        assert "Amazon" in result["top_3_merchants"][0]["merchant"]

def test_clean_json_response_with_markdown_fences():
    fenced_input = "```json\n[{\"index\": 0, \"category\": \"Food\"}]\n```"
    cleaned = clean_json_response(fenced_input)
    assert json.loads(cleaned) == [{"index": 0, "category": "Food"}]

def test_clean_json_response_with_conversational_text():
    noisy_input = "Here is the response:\n{\"risk_level\": \"high\", \"anomaly_count\": 3}\nHope this helps!"
    cleaned = clean_json_response(noisy_input)
    assert json.loads(cleaned) == {"risk_level": "high", "anomaly_count": 3}

def test_provider_selection():
    with patch.object(settings, "LLM_PROVIDER", "groq"):
        assert get_active_provider() == "groq"
    with patch.object(settings, "LLM_PROVIDER", "claude"):
        assert get_active_provider() == "anthropic"
    with patch.object(settings, "LLM_PROVIDER", "google"):
        assert get_active_provider() == "google"

def test_call_groq_mocked():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "{\"status\": \"ok\"}"}}]
    }
    
    with patch.object(settings, "GROQ_API_KEY", "gsk_valid_key_12345678"):
        with patch("requests.post", return_value=mock_resp):
            res = _call_groq("test prompt", response_json=True)
            assert res == "{\"status\": \"ok\"}"

def test_call_anthropic_mocked():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": [{"text": "{\"status\": \"ok\"}"}]
    }
    
    with patch.object(settings, "ANTHROPIC_API_KEY", "sk-ant-valid_key_12345678"):
        with patch("requests.post", return_value=mock_resp):
            res = _call_anthropic("test prompt", response_json=True)
            assert res == "{\"status\": \"ok\"}"
