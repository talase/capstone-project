-- Align existing Personal Context Memory tables with the backend rule model.
-- This migration is additive and preserves legacy columns and existing rows.

begin;

alter table public.personal_context_rules
  add column if not exists rule_name text,
  add column if not exists priority integer,
  add column if not exists contact_id text,
  add column if not exists topic text,
  add column if not exists action text;

-- Existing installations may already contain unnamed rules. Give each one a
-- stable readable name before enforcing the backend's required field.
update public.personal_context_rules
set rule_name = concat(
  initcap(replace(coalesce(nullif(trim(rule_type), ''), 'Personal context'), '_', ' ')),
  ' #',
  id
)
where rule_name is null or trim(rule_name) = '';

update public.personal_context_rules
set priority = 0
where priority is null;

alter table public.personal_context_rules
  alter column rule_name set not null,
  alter column priority set default 0,
  alter column priority set not null;

create index if not exists personal_context_rules_user_idx
  on public.personal_context_rules (user_id);

create index if not exists personal_context_rules_active_idx
  on public.personal_context_rules (is_active);

create index if not exists personal_context_rules_priority_idx
  on public.personal_context_rules (priority);

commit;
