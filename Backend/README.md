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
SUPABASE_KEY=your_supabase_service_or_anon_key
```

## Endpoints

- `GET /` - backend status message
- `GET /health` - health check
- `POST /style/process` - generate a style-adapted response and evaluate PCM
- `POST /calendar/process` - process a calendar request
- `POST /personal-context/rules` - create a PCM rule
- `GET /personal-context/rules` - list PCM rules
- `GET /personal-context/rules/active` - list active PCM rules
- `PUT /personal-context/rules/{rule_id}` - update a PCM rule
- `DELETE /personal-context/rules/{rule_id}` - delete a PCM rule
- `PATCH /personal-context/rules/{rule_id}/activate` - activate a PCM rule
- `PATCH /personal-context/rules/{rule_id}/deactivate` - deactivate a PCM rule
- `POST /personal-context/approvals` - create a pending approval request
- `GET /personal-context/approvals` - list approval requests
- `GET /personal-context/approvals/{approval_id}` - get one approval request
- `POST /personal-context/approvals/{approval_id}/approve` - approve a request
- `POST /personal-context/approvals/{approval_id}/reject` - reject a request
- `POST /personal-context/status` - set current user status
- `GET /personal-context/status` - get current user status
- `PATCH /personal-context/status` - update current user status
- `DELETE /personal-context/status` - clear current user status

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

Run `Backend/supabase/migrations/001_personal_context_memory.sql` in Supabase
before using PCM rule, status, or approval endpoints.
