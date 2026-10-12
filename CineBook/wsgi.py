"""
WSGI compatibility entrypoint for CineBook.wsgi:application.
Forwards to config.wsgi.application.
"""
import os
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.wsgi import application

__all__ = ["application"]
