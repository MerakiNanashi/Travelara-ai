# ─────────────────────────── Errors ─────────────────────────────────────── #

class ExtractionError(Exception):
    """Base class for all standardized extraction failures."""
    code = "extraction_error"


class ExtractionParseError(ExtractionError):
    """Gemini returned text that isn't valid JSON at all."""
    code = "parse_error"


class ExtractionSchemaError(ExtractionError):
    """Gemini returned valid JSON but it doesn't match the expected shape."""
    code = "schema_error"

class ExtractionServiceError(ExtractionError):
    """The Gemini call itself failed (network, auth, rate limit, timeout)."""
    code = "service_error"