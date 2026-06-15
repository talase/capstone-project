-- Remove legacy PCM rule evaluation and decision logging.

begin;

drop table if exists public.personal_context_decision_logs;
drop table if exists public.personal_context_rules;

commit;
