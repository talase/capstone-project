-- Allow Personal Context Memory rules to resolve conflicts explicitly.

alter table personal_context_rules
  add column if not exists priority integer not null default 0;

create index if not exists personal_context_rules_priority_idx
  on personal_context_rules (priority);
