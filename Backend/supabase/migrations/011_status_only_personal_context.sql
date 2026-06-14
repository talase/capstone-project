-- Keep PCM data and decision logging status-only.

begin;

alter table public.user_statuses
  drop column if exists status_reason;

alter table public.personal_context_decision_logs
  drop column if exists matched_rules;

alter table public.personal_context_decision_logs
  add column if not exists final_action text;

commit;
