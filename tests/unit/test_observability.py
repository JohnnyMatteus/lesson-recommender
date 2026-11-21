import json
import logging

from lesson_recommender.observability import JsonFormatter


def test_json_formatter_includes_extra_fields() -> None:
    record = logging.LogRecord("lr", logging.INFO, __file__, 1, "olá %s", ("mundo",), None)
    record.student_id = "ana"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "olá mundo"
    assert payload["level"] == "INFO"
    assert payload["student_id"] == "ana"
    assert "trace_id" not in payload
