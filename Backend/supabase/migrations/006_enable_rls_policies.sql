-- Enable row level security for app tables.
-- The backend service role bypasses RLS, but authenticated clients should not
-- access unrestricted tables directly.

do $$
declare
  table_name text;
  table_names text[] := array[
    'personal_context_rules',
    'approvals',
    'style_profiles',
    'user_statuses',
    'current_status',
    'style_learning_retry_queue',
    'draft_messages',
    'deferred_messages',
    'daily_reports',
    'message_logs',
    'agent_activity_logs',
    'approval_logs',
    'high_risk_alerts',
    'reminder_logs',
    'scheduled_messages',
    'scheduled_message_logs',
    'rag_access_logs',
    'personal_context_decision_logs'
  ];
begin
  foreach table_name in array table_names loop
    if to_regclass(format('public.%I', table_name)) is not null then
      execute format('alter table public.%I enable row level security', table_name);

      if not exists (
        select 1
        from pg_policies
        where schemaname = 'public'
          and tablename = table_name
          and policyname = 'Allow authenticated read'
      ) then
        execute format(
          'create policy "Allow authenticated read" on public.%I for select to authenticated using (true)',
          table_name
        );
      end if;

      if not exists (
        select 1
        from pg_policies
        where schemaname = 'public'
          and tablename = table_name
          and policyname = 'Allow authenticated insert'
      ) then
        execute format(
          'create policy "Allow authenticated insert" on public.%I for insert to authenticated with check (true)',
          table_name
        );
      end if;

      if not exists (
        select 1
        from pg_policies
        where schemaname = 'public'
          and tablename = table_name
          and policyname = 'Allow authenticated update'
      ) then
        execute format(
          'create policy "Allow authenticated update" on public.%I for update to authenticated using (true)',
          table_name
        );
      end if;
    end if;
  end loop;
end;
$$;
