create extension if not exists pgcrypto;

create table if not exists public.labyrinth_sessions (
  id uuid primary key default gen_random_uuid(),
  join_code text not null unique,
  leader_user_id uuid not null references auth.users(id) on delete cascade,
  leader_character_name text not null,
  mode text not null,
  status text not null default 'lobby',
  controller_user_id uuid references auth.users(id) on delete set null,
  floor integer not null default 1,
  grid_size integer not null default 7,
  current_x integer not null default 0,
  current_y integer not null default 0,
  tile_states jsonb not null default '{}'::jsonb,
  pending_encounter jsonb not null default '{}'::jsonb,
  reward_options jsonb not null default '[]'::jsonb,
  modifier_stack jsonb not null default '[]'::jsonb,
  recent_events jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_labyrinth_sessions_join_code on public.labyrinth_sessions (join_code);
create index if not exists idx_labyrinth_sessions_status_updated on public.labyrinth_sessions (status, updated_at desc);

create table if not exists public.labyrinth_session_members (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.labyrinth_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  character_name text not null,
  mode text not null,
  slot_index integer not null,
  player_class text not null,
  level integer not null default 1,
  current_hp integer not null default 1,
  max_hp integer not null default 1,
  current_mana integer not null default 0,
  max_mana integer not null default 0,
  current_xp integer not null default 0,
  xp_to_next integer not null default 100,
  is_downed boolean not null default false,
  last_resolution_sequence integer not null default 0,
  last_resolution_status text not null default '',
  resolution_note text not null default '',
  profile_snapshot jsonb not null default '{}'::jsonb,
  joined_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint labyrinth_session_members_unique_member unique (session_id, user_id, mode, slot_index)
);

create index if not exists idx_labyrinth_session_members_session_joined
  on public.labyrinth_session_members (session_id, joined_at);

create index if not exists idx_labyrinth_session_members_user_updated
  on public.labyrinth_session_members (user_id, updated_at desc);

create table if not exists public.labyrinth_session_votes (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.labyrinth_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  floor integer not null,
  choice_index integer not null,
  character_name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint labyrinth_session_votes_unique_vote unique (session_id, user_id, floor)
);

create index if not exists idx_labyrinth_session_votes_session_floor
  on public.labyrinth_session_votes (session_id, floor, updated_at desc);

alter table public.labyrinth_sessions enable row level security;
alter table public.labyrinth_session_members enable row level security;
alter table public.labyrinth_session_votes enable row level security;

drop policy if exists "Authenticated users can read labyrinth sessions" on public.labyrinth_sessions;
create policy "Authenticated users can read labyrinth sessions"
on public.labyrinth_sessions
for select
to authenticated
using (true);

drop policy if exists "Authenticated leaders can create labyrinth sessions" on public.labyrinth_sessions;
create policy "Authenticated leaders can create labyrinth sessions"
on public.labyrinth_sessions
for insert
to authenticated
with check (
  (select auth.uid()) = leader_user_id
);

drop policy if exists "Session members can update labyrinth sessions" on public.labyrinth_sessions;
create policy "Session members can update labyrinth sessions"
on public.labyrinth_sessions
for update
to authenticated
using (
  (select auth.uid()) = leader_user_id
  or exists (
    select 1
    from public.labyrinth_session_members m
    where m.session_id = labyrinth_sessions.id
      and m.user_id = (select auth.uid())
  )
)
with check (
  (select auth.uid()) = leader_user_id
  or exists (
    select 1
    from public.labyrinth_session_members m
    where m.session_id = labyrinth_sessions.id
      and m.user_id = (select auth.uid())
  )
);

drop policy if exists "Authenticated users can read labyrinth members" on public.labyrinth_session_members;
create policy "Authenticated users can read labyrinth members"
on public.labyrinth_session_members
for select
to authenticated
using (true);

drop policy if exists "Users can insert their own labyrinth member row" on public.labyrinth_session_members;
create policy "Users can insert their own labyrinth member row"
on public.labyrinth_session_members
for insert
to authenticated
with check (
  (select auth.uid()) = user_id
);

drop policy if exists "Users can update their own labyrinth member row" on public.labyrinth_session_members;
create policy "Users can update their own labyrinth member row"
on public.labyrinth_session_members
for update
to authenticated
using (
  (select auth.uid()) = user_id
)
with check (
  (select auth.uid()) = user_id
);

drop policy if exists "Users can delete their own labyrinth member row" on public.labyrinth_session_members;
create policy "Users can delete their own labyrinth member row"
on public.labyrinth_session_members
for delete
to authenticated
using (
  (select auth.uid()) = user_id
);

drop policy if exists "Authenticated users can read labyrinth votes" on public.labyrinth_session_votes;
create policy "Authenticated users can read labyrinth votes"
on public.labyrinth_session_votes
for select
to authenticated
using (true);

drop policy if exists "Users can insert their own labyrinth votes" on public.labyrinth_session_votes;
create policy "Users can insert their own labyrinth votes"
on public.labyrinth_session_votes
for insert
to authenticated
with check (
  (select auth.uid()) = user_id
);

drop policy if exists "Users can update their own labyrinth votes" on public.labyrinth_session_votes;
create policy "Users can update their own labyrinth votes"
on public.labyrinth_session_votes
for update
to authenticated
using (
  (select auth.uid()) = user_id
)
with check (
  (select auth.uid()) = user_id
);
