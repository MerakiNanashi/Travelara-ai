import os
import time
from datetime import datetime
from functools import wraps
import inspect



# Gemini pricing (as of 2026-07)
# Per 1 million tokens
INPUT_COST_PER_MILLION = 0.10   # USD
OUTPUT_COST_PER_MILLION = 0.40   # USD


# =========================
# METRICS HELPERS
# =========================

def estimate_tokens(text: str) -> int:
    """
    Rough token estimation.
    Approximation:
    1 token ~= 4 chars (English average)
    """
    return max(1, len(text) // 4)


def calculate_cost(input_tokens: int, output_tokens: int):
    """
    Cost calculation using per-million-token billing.
    """

    input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_MILLION

    total_cost = input_cost + output_cost

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": round(input_cost, 8),
        "output_cost_usd": round(output_cost, 8),
        "total_cost_usd": round(total_cost, 8)
    }



def measure_latency(func):

    # --------------------------------------------------
    # ASYNC FUNCTION
    # --------------------------------------------------

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):

            start = time.perf_counter()

            result = await func(*args, **kwargs)

            end = time.perf_counter()

            print(
                f"[LATENCY] {func.__name__}: "
                f"{end - start:.2f} sec"
            )

            return result

        return async_wrapper

    # --------------------------------------------------
    # SYNC FUNCTION
    # --------------------------------------------------

    @wraps(func)
    def sync_wrapper(*args, **kwargs):

        start = time.perf_counter()

        result = func(*args, **kwargs)

        end = time.perf_counter()

        print(
            f"[LATENCY] {func.__name__}: "
            f"{end - start:.2f} sec"
        )

        return result

    return sync_wrapper