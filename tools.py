"""
Tools for the Alex Researcher agent
"""
import os
from typing import Dict, Any
from datetime import datetime, UTC
import httpx
from agents import function_tool
from tenacity import retry, stop_after_attempt, wait_exponential

# Configuration from environment
ALEX_API_ENDPOINT = os.getenv("ALEX_API_ENDPOINT")
ALEX_API_KEY = os.getenv("ALEX_API_KEY")

MAX_ANALYSIS_CHARS = 2000  # Cap stored analysis length

def compress_for_context(text: str, max_chars: int) -> str:
    """Truncate text with a marker so the agent knows content was compressed."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n[TRUNCATED — {len(text) - max_chars} chars removed]"


def _ingest(document: Dict[str, Any]) -> Dict[str, Any]:
    """Internal function to make the actual API call."""
    with httpx.Client() as client:
        response = client.post(
            ALEX_API_ENDPOINT,
            json=document,
            headers={"x-api-key": ALEX_API_KEY},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def ingest_with_retries(document: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest with retry logic for SageMaker cold starts."""
    return _ingest(document)


@function_tool
def ingest_financial_document(topic: str, analysis: str) -> Dict[str, Any]:
    """
    Ingest a financial document into the Alex knowledge base.
    
    Args:
        topic: The topic or subject of the analysis (e.g., "AAPL Stock Analysis", "Retirement Planning Guide")
        analysis: Detailed analysis or advice with specific data and insights
    
    Returns:
        Dictionary with success status and document ID
    """
    if not ALEX_API_ENDPOINT or not ALEX_API_KEY:
        return {
            "success": False,
            "error": "Alex API not configured. Running in local mode."
        }
    
    document = {
        "text": compress_for_context(analysis, MAX_ANALYSIS_CHARS),
        "metadata": {
            "topic": topic,
            "timestamp": datetime.now(UTC).isoformat()
        }
    }
    
    try:
        result = ingest_with_retries(document)
        return {
            "success": True,
            "document_id": result.get("document_id"),  # Changed from documentId
            "message": f"Successfully ingested analysis for {topic}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@function_tool
def update_todo(step_number: int, status: str, note: str = "") -> str:
    """
    Mark a todo step as complete, failed, or skipped.
    Use this after finishing each step to track progress.

    Args:
        step_number: The step number being updated (1-7)
        status:      "complete", "failed", or "skipped"
        note:        Optional brief note about what happened
    """
    note_str = f" — {note}" if note else ""
    return f"Step {step_number} {status.upper()}{note_str}. Proceed to Step {step_number + 1}."