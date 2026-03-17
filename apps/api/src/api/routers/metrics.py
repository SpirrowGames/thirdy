"""Prometheus metrics endpoint for Thirdy API."""

import time
from collections import defaultdict

from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

router = APIRouter()

# Simple in-memory counters (no prometheus_client dependency needed)
_request_counts: dict[str, int] = defaultdict(int)
_error_counts: dict[str, int] = defaultdict(int)
_total_duration: float = 0.0
_total_requests: int = 0


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track request metrics."""

    async def dispatch(self, request: Request, call_next):
        global _total_duration, _total_requests

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        path = request.url.path
        _request_counts[path] += 1
        _total_requests += 1
        _total_duration += duration

        if response.status_code >= 400:
            _error_counts[f"{response.status_code}"] += 1

        return response


@router.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus-compatible metrics endpoint."""
    lines = []
    lines.append("# HELP thirdy_requests_total Total HTTP requests")
    lines.append("# TYPE thirdy_requests_total counter")
    lines.append(f"thirdy_requests_total {_total_requests}")

    lines.append("# HELP thirdy_request_duration_seconds_total Total request duration")
    lines.append("# TYPE thirdy_request_duration_seconds_total counter")
    lines.append(f"thirdy_request_duration_seconds_total {_total_duration:.4f}")

    if _total_requests > 0:
        lines.append("# HELP thirdy_avg_duration_seconds Average request duration")
        lines.append("# TYPE thirdy_avg_duration_seconds gauge")
        lines.append(f"thirdy_avg_duration_seconds {_total_duration / _total_requests:.4f}")

    lines.append("# HELP thirdy_errors_total Total HTTP errors by status")
    lines.append("# TYPE thirdy_errors_total counter")
    for status, count in sorted(_error_counts.items()):
        lines.append(f'thirdy_errors_total{{status="{status}"}} {count}')

    lines.append("# HELP thirdy_requests_by_path Total requests by path")
    lines.append("# TYPE thirdy_requests_by_path counter")
    # Top 20 paths
    top_paths = sorted(_request_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    for path, count in top_paths:
        safe_path = path.replace('"', '\\"')
        lines.append(f'thirdy_requests_by_path{{path="{safe_path}"}} {count}')

    return Response(content="\n".join(lines) + "\n", media_type="text/plain")
