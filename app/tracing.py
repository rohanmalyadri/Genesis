"""Optional Opik tracing. The opik package (about 35 MB) is only imported when OPIK_API_KEY is set."""
from app.config import settings


def track(name: str | None = None):
    if settings.OPIK_API_KEY:
        try:
            from opik import track as opik_track
            return opik_track(name=name)
        except Exception as e:  # tracing must never break the app
            print(f"Tracing disabled: {e}")

    def decorator(fn):
        return fn
    return decorator
