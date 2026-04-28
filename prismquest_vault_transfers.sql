create extension if not exists pgcrypto;

create table if not exists public.player_vault_transfers (
  id uuid primary key default gen_random_uuid(),
  sender_user_id uuid not null references auth.users(id) on delete cascade,
  sender_character_name text not null,
  sender_mode text not null,
  sender_slot_index integer not null,
  recipient_user_id uuid not null references auth.users(id) on delete cascade,
  recipient_character_name text not null,
  recipient_mode text not null,
  recipient_slot_index integer not null,
  recipient_vault_code text not null,
  item_payload jsonb not null,
  item_summary text not null,
  item_tier integer not null default 0,
  item_rarity text not null default '',
  status text not null default 'pending',
  created_at timestamptz not null default now(),
  claimed_at timestamptz
);

create index if not exists idx_player_vault_transfers_recipient_pending
  on public.player_vault_transfers (recipient_user_id, recipient_mode, recipient_slot_index, status, created_at);

create index if not exists idx_player_vault_transfers_sender_created
  on public.player_vault_transfers (sender_user_id, created_at desc);

alter table public.player_vault_transfers enable row level security;

drop policy if exists "Authenticated users can view relevant vault transfers" on public.player_vault_transfers;
create policy "Authenticated users can view relevant vault transfers"
on public.player_vault_transfers
for select
to authenticated
using (
  (select auth.uid()) = sender_user_id
  or (select auth.uid()) = recipient_user_id
);

drop policy if exists "Users can insert outgoing vault transfers" on public.player_vault_transfers;
create policy "Users can insert outgoing vault transfers"
on public.player_vault_transfers
for insert
to authenticated
with check (
  (select auth.uid()) = sender_user_id
  and status = 'pending'
);

drop policy if exists "Recipients can update vault transfer claims" on public.player_vault_transfers;
create policy "Recipients can update vault transfer claims"
on public.player_vault_transfers
for update
to authenticated
using (
  (select auth.uid()) = recipient_user_id
)
with check (
  (select auth.uid()) = recipient_user_id
);
