# Vercel Python Serverless entry. Reuse existing handler implementation.
# File-based routing: this function will be available at /api/webhook
from python.api.webhook import handler as handler  # type: ignore