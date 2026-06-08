"""Gunicorn WSGI 入口（Zeabur 生產環境）"""
import startup

startup.run()

from app import app  # noqa: E402,F401
