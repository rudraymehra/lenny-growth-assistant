"""Structured JSON logging via structlog, plus the event taxonomy.

Every operationally-interesting moment emits one of the EVT_* events with
key=value context, so failures in the model, retrieval, database, or artifact
pipeline can be diagnosed from logs alone (see architecture.md#observability).
"""

import logging
import sys

import structlog

# Event taxonomy — grep targets for operators.
EVT_REQUEST = "http.request"
EVT_RETRIEVAL = "retrieval.query"          # query, hit_count, top_score, latency_ms
EVT_MODEL_CALL = "model.call"              # provider, model, latency_ms, ok
EVT_MODEL_TIMEOUT = "model.timeout"        # provider, model, timeout_s
EVT_CITATION_UNMATCHED = "citation.unmatched"  # marker index the model used but retrieval didn't provide
EVT_ARTIFACT_SANITIZED = "artifact.sanitized"  # kind, removed_bytes
EVT_INGEST = "ingest.run"                  # status, episodes_written, chunks_written
EVT_ENGINE_ERROR = "engine.error"          # provider, code, detail
EVT_DB_ERROR = "db.error"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(stream=sys.stdout, level=level.upper(), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
