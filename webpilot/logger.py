"""日志工具。

默认 WARNING 级别，设置环境变量 WEBPILOT_LOG=DEBUG 可以看到
每一条 WebDriver 协议请求/响应，排查问题时非常有用。
"""
from __future__ import annotations

import logging
import os

_INITIALIZED = False


def get_logger(name: str = "webpilot") -> logging.Logger:
    global _INITIALIZED
    logger = logging.getLogger(name)
    if not _INITIALIZED:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(os.environ.get("WEBPILOT_LOG", "WARNING").upper())
        _INITIALIZED = True
    return logger
