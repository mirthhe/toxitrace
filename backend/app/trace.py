"""Records every external call and local lookup, so each displayed value can cite its source."""

from datetime import UTC, datetime
from typing import Any

from app.schemas import TraceEntry, TraceStatus


class Tracer:
    def __init__(self) -> None:
        self.entries: list[TraceEntry] = []
        self._counters: dict[str, int] = {}

    def record(
        self,
        source: str,
        tool: str,
        status: TraceStatus,
        request: dict[str, Any] | None = None,
        response: Any = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> str:
        """Append an entry and return its ref (e.g. "toxindex-2")."""
        self._counters[source] = self._counters.get(source, 0) + 1
        ref = f"{source}-{self._counters[source]}"
        self.entries.append(
            TraceEntry(
                ref=ref,
                source=source,
                tool=tool,
                status=status,
                request=request or {},
                response=response,
                error=error,
                duration_ms=duration_ms,
                retrieved_at=datetime.now(UTC),
            )
        )
        return ref
