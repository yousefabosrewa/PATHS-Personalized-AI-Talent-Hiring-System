"""
PATHS Backend — Outreach Agent module.

Implements the HR Outreach feature: OpenRouter-generated personalized email,
HR availability windows, public secure scheduling link, Google OAuth, Gmail
send, Google Calendar event with Meet link.

Compliance:
  * No raw Google passwords — OAuth 2.0 only.
  * Tokens are encrypted at rest (Fernet from secret_key).
  * Public scheduling URL uses random token; only the SHA-256 hash is stored.
  * HR must click Send — nothing is sent automatically.
"""
