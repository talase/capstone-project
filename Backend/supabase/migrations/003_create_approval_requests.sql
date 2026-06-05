-- Active approval records used by Personal Context Memory and n8n.
-- approval_logs remains the append-only audit/history table.

create extension if not exists pgcrypto;

create table if not exists approvals (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  contact_id text,
  original_message text not null,
  generated_reply text not null,
  decision text not null default 'require_approval',
  reason text,
  matched_rules jsonb not null default '[]'::jsonb,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Keep this migration safe to run against databases that already have a
-- partial approvals table.
alter table approvals add column if not exists user_id text;
alter table approvals add column if not exists contact_id text;
alter table approvals add column if not exists original_message text;
alter table approvals add column if not exists generated_reply text;
alter table approvals add column if not exists decision text default 'require_approval';
alter table approvals add column if not exists reason text;
alter table approvals add column if not exists matched_rules jsonb not null default '[]'::jsonb;
alter table approvals add column if not exists status text default 'pending';
alter table approvals add column if not exists created_at timestamptz not null default now();
alter table approvals add column if not exists updated_at timestamptz not null default now();

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'approvals'
      and column_name = 'id'
      and data_type = 'uuid'
  ) then
    alter table approvals alter column id set default gen_random_uuid();
  end if;
end;
$$;

create index if not exists approvals_user_idx
  on approvals (user_id);

create index if not exists approvals_status_idx
  on approvals (status);

create index if not exists approvals_created_at_idx
  on approvals (created_at);

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists approvals_updated_at
  on approvals;

create trigger approvals_updated_at
before update on approvals
for each row execute function set_updated_at();
