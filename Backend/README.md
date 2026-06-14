# Tala Backend

Tala is the FastAPI backend used by n8n workflows. The backend exposes clean
HTTP endpoints for style adaptation, calendar processing, and Personal Context
Memory (PCM). n8n owns workflow orchestration and calls these endpoints with
HTTP Request nodes.

## Run Locally

Install dependencies from the repository root:

```bash
pip install -r requirements.txt
```

Start the backend:

```bash
cd Backend
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Environment Variables

Create `Backend/app/.env` or export these values before starting the server:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_ROLE_KEY=your_server_only_service_role_key
SUPABASE_KEY=your_publishable_fallback_key
```

## Endpoints

- `GET /` - backend status message
- `GET /health` - health check
- `GET /reports/daily` - generate an end-of-day activity report from Supabase logs
- `POST /style/process` - generate a style-adapted response and evaluate PCM
- `POST /calendar/process` - process a calendar request
- `POST /personal-context/evaluate` - return the current status as prompt context
- `POST /personal-context/status` - set current user status
- `GET /personal-context/status` - get current user status
- `PATCH /personal-context/status` - update current user status
- `DELETE /personal-context/status` - clear current user status
- `POST /approvals` - create a pending risk approval request
- `GET /approvals` - list approval requests
- `GET /approvals/{approval_id}` - get one approval request
- `POST /approvals/{approval_id}/approve` - approve a request
- `POST /approvals/{approval_id}/reject` - reject a request

## n8n Integration

n8n should receive external events and orchestrate the workflow. Use HTTP
Request nodes to call the backend endpoints above. The backend does not expose
or process WhatsApp callback routes.

Example request to `POST /style/process`:

```json
{
  "message": "Can you send the file today?",
  "contact_id": "friend",
  "user_id": "default_user",
  "risk_level": "low",
  "action_type": "send_message"
}
```

Run the Supabase migrations through
`Backend/supabase/migrations/012_remove_legacy_pcm_decisions.sql` before
using the simplified PCM behavior.

Run `Backend/supabase/migrations/002_daily_report_logs.sql` in Supabase before
using the daily report endpoint.

## Daily Reports

`GET /reports/daily` returns a structured activity report for the selected
calendar date. It summarizes messages received and sent, automatic actions,
approved and rejected actions, pending approvals, high-risk alerts, reminders,
scheduled messages, and RAG file access.

Example request:

```bash
curl "http://127.0.0.1:8000/reports/daily?date=2026-05-22&user_id=default_user"
```

The `date` and `user_id` query parameters are optional. If `date` is omitted,
the backend uses today's date.

The style adaptation, PCM context, and separate risk approval flows write
report records automatically through `app.daily_activity_logger`. New backend modules or n8n workflows that
create reminders, scheduled WhatsApp messages, or RAG/file accesses should call
the matching helper (`log_reminder_created`, `log_scheduled_message_created`,
or `log_rag_access`) so those sections appear in the daily report. Logging is
best effort: failures are returned as warning metadata where possible and do
not block response generation or approval updates.

## Personal Context Memory

PCM stores only the user's current free-text status. Values such as `busy`,
`traveling`, `at_work`, or future custom statuses are supported. The evaluate
endpoint returns the status and the prompt-ready context derived from it:

```json
{
  "current_status": {
    "status": "busy finishing a project"
  },
  "context": [
    "The user's current status is: busy finishing a project"
  ]
}
```

PCM does not make execution or delivery decisions. `/style/process` exposes
`send_allowed`, `risk_approval.required`, and `handling_status` through the
separate risk-approval flow. `handling_status` is `ready_to_send` or
`awaiting_approval`.

Example response:

```json
{
  "date": "2026-05-22",
  "summary": {
    "messages_received": 4,
    "messages_sent": 3,
    "automatic_actions": 2,
    "approved_actions": 1,
    "rejected_actions": 0,
    "pending_approvals": 1,
    "high_risk_alerts": 1,
    "reminders_created": 1,
    "scheduled_messages": 1,
    "rag_files_accessed": 2
  },
  "detected_action_categories": [
    {
      "category": "request_to_send_message",
      "count": 2
    }
  ],
  "automatic_actions": [],
  "user_approved_actions": [],
  "rejected_actions": [],
  "pending_approvals": [],
  "high_risk_alerts": [],
  "reminders": [],
  "scheduled_messages": [],
  "rag_file_access": [],
  "needs_attention": []
}
```
