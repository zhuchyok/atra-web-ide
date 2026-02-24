"""
Victoria Fallback with Retry and Exponential Backoff

Implements resilient Victoria → Veronica → Hardcoded fallback chain
with automatic retry using tenacity.
"""

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)

# Default URLs (can be overridden via env vars)
VICTORIA_URL = "http://localhost:8010"
VERONICA_URL = "http://localhost:8011"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
)
async def call_victoria_with_retry(
    query: str, context: dict[str, Any], timeout: int = 60
) -> httpx.Response:
    """
    Call Victoria with exponential backoff retry.

    Retries on:
    - TimeoutException
    - ConnectError

    Does NOT retry on:
    - 4xx/5xx HTTP errors (falls through to fallback)
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VICTORIA_URL}/run", json={"goal": query, **context}, timeout=timeout
        )
        response.raise_for_status()
        return response


async def call_victoria_with_fallback(
    query: str, context: dict[str, Any] | None = None, timeout: int = 60
) -> dict[str, Any]:
    """
    Call Victoria with automatic fallback to Veronica and hardcoded response.

    Fallback chain:
    1. Victoria (with 3 retries, exponential backoff)
    2. Veronica (single attempt, shorter timeout)
    3. Hardcoded error response

    Args:
        query: User query/goal
        context: Additional context (project_context, max_steps, etc.)
        timeout: Timeout for Victoria (seconds)

    Returns:
        Response dict with 'status' and 'response' keys
    """
    if context is None:
        context = {}

    # Try Victoria with retry
    try:
        response = await call_victoria_with_retry(query, context, timeout)
        result = response.json()

        # Extract response from various possible keys
        response_text = (
            result.get("output") or result.get("result") or result.get("response") or str(result)
        )

        return {"status": "victoria", "response": response_text, "source": "Victoria Agent"}

    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.warning(
            f"Victoria unavailable ({type(e).__name__}: {e}), trying Veronica fallback"
        )

        # Try Veronica (single attempt, shorter timeout)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{VERONICA_URL}/run", json={"goal": query, **context}, timeout=30
                )
                response.raise_for_status()
                result = response.json()

                response_text = (
                    result.get("output")
                    or result.get("result")
                    or result.get("response")
                    or str(result)
                )

                return {
                    "status": "veronica",
                    "response": response_text,
                    "source": "Veronica Agent (fallback)",
                }

        except Exception as veronica_error:
            logger.error(
                f"Veronica also unavailable ({type(veronica_error).__name__}: "
                f"{veronica_error}), returning hardcoded response"
            )

            # Final fallback: hardcoded response
            return {
                "status": "fallback",
                "response": (
                    "Агенты временно недоступны. Пожалуйста, попробуйте позже. "
                    "Если проблема повторяется, проверьте статус служб: "
                    "Victoria (8010), Veronica (8011)."
                ),
                "source": "Hardcoded fallback",
                "error": f"Victoria: {e}, Veronica: {veronica_error}",
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"Victoria HTTP error {e.response.status_code}: {e}")

        # For HTTP errors, go directly to Veronica
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{VERONICA_URL}/run", json={"goal": query, **context}, timeout=30
                )
                response.raise_for_status()
                result = response.json()

                return {
                    "status": "veronica",
                    "response": result.get("output") or result.get("response") or str(result),
                    "source": "Veronica Agent (Victoria HTTP error fallback)",
                }
        except Exception:
            return {
                "status": "fallback",
                "response": "Агенты временно недоступны. Попробуйте позже.",
                "source": "Hardcoded fallback",
                "error": str(e),
            }

    except Exception as e:
        logger.exception(f"Unexpected error calling Victoria: {e}")
        return {
            "status": "error",
            "response": "Внутренняя ошибка при обращении к агентам.",
            "source": "Error handler",
            "error": str(e),
        }


# Convenience function for chat endpoints
async def chat_with_fallback(message: str, project_context: str = "atra-web-ide") -> str:
    """
    Simplified chat interface with fallback.

    Returns only the response text (string).
    """
    result = await call_victoria_with_fallback(
        query=message, context={"project_context": project_context}
    )
    return str(result["response"])
