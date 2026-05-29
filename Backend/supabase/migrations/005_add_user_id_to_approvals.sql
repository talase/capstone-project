-- Ensure daily reports can filter the approvals table by user.
-- Older Supabase databases may have approvals without user_id.

do $$
begin
  if to_regclass('public.approvals') is not null then
    execute 'alter table public.approvals add column if not exists user_id text default ''default_user''';
    execute 'alter table public.approvals alter column user_id set default ''default_user''';
    execute 'update public.approvals set user_id = ''default_user'' where user_id is null';
    execute 'create index if not exists approvals_user_idx on public.approvals (user_id)';
  end if;
end;
$$;
