-- Mind Masters AI Answer Verification — Supabase schema (reference copy)
-- Canonical version: ../../supabase/migrations/20261016120000_create_verifications.sql, applied with the
-- Supabase CLI from the ai-answer-verification folder. Kept so the SQL can also be reviewed or run manually.
--
-- Security model:
--   * The backend calls the Data API with the project's anon/publishable key plus the
--     signed-in user's JWT, so every query runs as role "authenticated" and RLS applies.
--   * Each row is owned by the user who created it (user_id defaults to auth.uid()).
--   * The "anon" role (not signed in) has no access at all.

-- gen_random_uuid() is built into Postgres 13+, so no extension is required.
create table if not exists public.verifications (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  payload     jsonb not null,
  constraint verifications_payload_is_object check (jsonb_typeof(payload) = 'object')
);

comment on table public.verifications is
  'AI Answer Verification records. One row per verification; details are stored in payload (jsonb).';

create index if not exists verifications_user_created_idx
  on public.verifications (user_id, created_at desc);

-- Table privileges: explicit, so the app works whether or not the project auto-exposes new tables.
revoke all on table public.verifications from anon;
grant select, insert, update, delete on table public.verifications to authenticated;

-- Row Level Security: users can only see and change their own rows.
alter table public.verifications enable row level security;

drop policy if exists "verifications_select_own" on public.verifications;
drop policy if exists "verifications_insert_own" on public.verifications;
drop policy if exists "verifications_update_own" on public.verifications;
drop policy if exists "verifications_delete_own" on public.verifications;

create policy "verifications_select_own" on public.verifications
  for select to authenticated
  using (user_id = (select auth.uid()));

create policy "verifications_insert_own" on public.verifications
  for insert to authenticated
  with check (user_id = (select auth.uid()));

create policy "verifications_update_own" on public.verifications
  for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy "verifications_delete_own" on public.verifications
  for delete to authenticated
  using (user_id = (select auth.uid()));
