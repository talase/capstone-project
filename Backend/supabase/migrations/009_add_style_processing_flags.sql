-- Track independent global and per-contact style-learning consumption.

alter table public.messages
  add column if not exists global_style_processed boolean not null default false;

alter table public.messages
  add column if not exists contact_style_processed boolean not null default false;

create index if not exists messages_pending_global_style_idx
  on public.messages (created_at, id)
  where global_style_processed = false
    and direction in ('outgoing', 'sent', 'outbound');

create index if not exists messages_pending_contact_style_idx
  on public.messages (contact_id, created_at, id)
  where contact_style_processed = false
    and direction in ('outgoing', 'sent', 'outbound');

create index if not exists messages_conversation_style_idx
  on public.messages (created_at, id);
