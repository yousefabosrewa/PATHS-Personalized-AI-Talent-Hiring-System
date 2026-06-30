# Recall.ai Notetaker — Setup Guide

PATHS integrates with [Recall.ai](https://recall.ai) to send a notetaker
bot to scheduled interviews and capture either a **post-meeting** transcript
(fetched after the call ends) or a **real-time** transcript (streamed
into the dashboard live via Server-Sent Events). HR picks the mode per
interview from the Interview detail page.

This guide walks through the **one-time setup** an operator must do
before either mode works in dev.

## 1. Recall.ai workspace

1. Sign up / log in at https://recall.ai (or the regional dashboard).
2. Create a workspace in the region you intend to use. PATHS defaults to
   `eu-central-1` to match the MCP URL `https://eu-central-1.recall.ai/mcp`.
3. From **Settings → API Keys**, generate a key and copy it.
4. From **Settings → Webhooks**, create a webhook subscribing to:
   * `bot.status_change`
   * `recording.done`
   * `transcript.done`
   * `transcript.data`
   * `transcript.partial_data`
   Point it at `https://<your-public-host>/api/v1/webhooks/recall`. Copy
   the **signing secret** (starts with `whsec_`).

## 2. Backend env (`backend/.env`)

Paste:

```env
RECALL_API_KEY=<the api key from step 1>
RECALL_REGION=eu-central-1
RECALL_WEBHOOK_SECRET=<whsec_... from step 1>
RECALL_PUBLIC_WEBHOOK_URL=<your public base URL, e.g. https://paths.ngrok.app>
RECALL_BOT_NAME=PATHS Notetaker
RECALL_POLL_INTERVAL_SECONDS=10
RECALL_TRANSCRIPTS_DIR=./uploads/transcripts
```

Leave `RECALL_API_KEY` blank to keep the integration dormant — every
HR-facing endpoint will 503 with a friendly message and the UI shows a
"Recall.ai is not configured" banner inside the interview panel.

## 3. Public tunnel (dev only)

The webhook URL must be reachable from the public Internet so Recall can
POST events to it. In dev, use **cloudflared** or **ngrok**:

```bash
# cloudflared (no signup needed)
cloudflared tunnel --url http://localhost:8001

# OR ngrok
ngrok http 8001
```

Copy the assigned URL (e.g. `https://chic-coral-snail.trycloudflare.com`)
into `RECALL_PUBLIC_WEBHOOK_URL` and into the Recall webhook config from
step 1.

**You can skip the tunnel for post-meeting mode** if you accept the
polling fallback — the `/recall/state` endpoint polls Recall every 5s
while a bot is in flight. Real-time mode does need the public URL
because the live captions arrive via `transcript.data` webhooks.

## 4. Apply the migration

The Recall integration adds 8 columns to the `interviews` table
(`recall_bot_id`, `recall_recording_id`, `recall_transcript_id`,
`recall_recording_mode`, `recall_status`, `recall_status_message`,
`recall_transcript_json`, `recall_transcript_path`). Run:

```bash
cd backend
.venv/Scripts/python.exe -m alembic upgrade head
```

## 5. Restart the backend

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## 6. Smoke test

1. Open the dashboard, sign in as an HR/recruiter user.
2. Schedule an interview (or pick an existing one with a `meeting_url`).
3. On the **Interview detail** page, find the **Recall.ai Notetaker** card.
4. Pick a recording mode: **Post-meeting transcript** or **Real-time transcript**.
5. Click **Start Recall bot**. The status badge flips to **Joining the call**.
6. Join the meeting yourself — you should see the bot join with the
   name from `RECALL_BOT_NAME` and post a consent message into chat.
7. *Real-time mode:* captions stream into the "Live transcript" pane as
   the conversation goes on.
8. *Post-meeting mode:* end the call. Within ~30 seconds the status flips
   to **Recording complete** → **Transcript ready** and the "Final
   transcript" pane appears.
9. The transcript JSON is also written to
   `${RECALL_TRANSCRIPTS_DIR}/<interview_id>__final.json` for audit.

## Troubleshooting

- **503 "Recall.ai is not configured"** — `RECALL_API_KEY` is blank.
- **400 "Interview has no meeting_url"** — schedule the interview with a
  Zoom/Meet/Teams URL or paste one into the interview's
  `meeting_url` column.
- **400 "Pick a recording mode first"** — the radio in the panel is
  unset. Pick one and try again.
- **502 "Recall.ai rejected the bot request"** — bad API key or the
  meeting URL is from an unsupported platform. The response body from
  Recall is in the FastAPI exception detail.
- **401 from `/webhooks/recall`** — Svix signature mismatch. Confirm
  `RECALL_WEBHOOK_SECRET` matches what's printed in the Recall dashboard.
- **Live transcript pane stays empty** — the bot is in the call but no
  speech yet, *or* the public webhook URL is missing/wrong. The pill
  in the top-right of the pane says "Live" when the SSE connection is
  open; "Waiting…" otherwise.

## Endpoint reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/interviews/{id}/recall/state` | Read current bot state. |
| `PUT` | `/api/v1/interviews/{id}/recall/recording-mode` | HR picks `post_meeting` \| `real_time`. |
| `POST` | `/api/v1/interviews/{id}/recall/start` | Dispatch a bot to the meeting URL. |
| `POST` | `/api/v1/interviews/{id}/recall/stop` | Tell the bot to leave. |
| `GET` | `/api/v1/interviews/{id}/recall/transcript` | Final transcript JSON + flat text. |
| `GET` | `/api/v1/interviews/{id}/recall/stream?token=...` | SSE stream of live captions. |
| `POST` | `/api/v1/webhooks/recall` | Receives Recall webhook events. |
