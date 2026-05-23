"""Trace explorer query service."""

from typing import Any, Callable, Dict, Iterable, List, Optional


TraceLookup = Callable[..., Iterable[Dict[str, Any]]]


class TraceFilterDepthError(ValueError):
    """Raised when a trace filter is too deeply nested."""


class TraceQueryValidationError(ValueError):
    """Raised when a trace query request is malformed."""


def validate_filter_depth(
    value: Any,
    max_depth: int,
    current_depth: int = 0,
) -> None:
    if current_depth > max_depth:
        message = f"Trace filter depth exceeds maximum of {max_depth}"
        raise TraceFilterDepthError(message)

    if isinstance(value, dict):
        for child in value.values():
            validate_filter_depth(child, max_depth, current_depth + 1)
        return

    if isinstance(value, list):
        for child in value:
            validate_filter_depth(child, max_depth, current_depth + 1)


class TraceQueryService:
    def __init__(
        self,
        lookup: Optional[TraceLookup] = None,
        max_filter_depth: int = 8,
    ):
        self._lookup = lookup or self._empty_lookup
        self.max_filter_depth = max_filter_depth
        self.success_count = 0

    def query(self, request: Dict[str, Any]) -> Dict[str, Any]:
        tenant_id = request.get("tenant_id")
        if not tenant_id:
            raise TraceQueryValidationError("tenant_id is required")

        filters = request.get("filters", {})
        if not isinstance(filters, dict):
            raise TraceQueryValidationError("filters must be an object")

        validate_filter_depth(filters, self.max_filter_depth)

        traces = list(self._lookup(tenant_id=tenant_id, filters=filters))
        self.success_count += 1
        return {"traces": traces, "count": len(traces)}

    @staticmethod
    def _empty_lookup(**_: Any) -> List[Dict[str, Any]]:
        return []
