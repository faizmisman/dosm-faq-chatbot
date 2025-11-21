import json
import logging
import uuid
import os

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = JSONLogFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    return logger

def with_request_id(record: dict) -> dict:
    if "request_id" not in record:
        record["request_id"] = str(uuid.uuid4())
    return record

class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        if hasattr(record, "pathname"):
            payload["path"] = record.pathname
        if hasattr(record, "lineno"):
            payload["lineno"] = record.lineno
        if isinstance(record.args, dict):
            payload.update(record.args)
        return json.dumps(payload, ensure_ascii=False)
