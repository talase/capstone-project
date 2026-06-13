-- Simplify Personal Context Memory to context plus auto_reply/defer decisions.
-- Approval and risk workflow tables remain separate and are not removed.

begin;

-- Custom statuses such as at_work or on_vacation must be accepted.
alter table public.user_statuses
  drop constraint if exists user_statuses_status_check;

-- Preserve legacy workflow rules for audit, but prevent new PCM evaluations
-- from treating them as context decisions.
update public.personal_context_rules
set is_active = false
where lower(trim(rule_type)) in (
  'require_approval',
  'approval_required',
  'needs_approval',
  'approval',
  'contact_requires_approval',
  'draft_only',
  'work_hours_draft',
  'blocked',
  'block',
  'no_auto_send',
  'topic_requires_approval',
  'money_requires_approval'
);

alter table public.personal_context_decision_logs
  drop column if exists final_action;

commit;
