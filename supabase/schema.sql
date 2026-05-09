-- Run this in Supabase SQL editor.
-- It creates app tables for profile + payments.

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text default '',
  target_role text default '',
  skills text[] default '{}',
  experience_level text default '',
  application_profile jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles
  add column if not exists application_profile jsonb not null default '{}'::jsonb;

create table if not exists public.payments (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  stripe_session_id text not null unique,
  status text not null default 'pending',
  amount_total bigint,
  currency text,
  created_at timestamptz not null default now()
);

create table if not exists public.applications (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  job_url text not null,
  company text,
  title text,
  location text,
  status text not null default 'queued_auto_apply',
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists idx_payments_user_id on public.payments(user_id);
create index if not exists idx_applications_user_id on public.applications(user_id);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.payments enable row level security;
alter table public.applications enable row level security;

drop policy if exists "Users can read own profile" on public.profiles;
create policy "Users can read own profile"
on public.profiles
for select
to authenticated
using (auth.uid() = id);

drop policy if exists "Users can insert own profile" on public.profiles;
create policy "Users can insert own profile"
on public.profiles
for insert
to authenticated
with check (auth.uid() = id);

drop policy if exists "Users can update own profile" on public.profiles;
create policy "Users can update own profile"
on public.profiles
for update
to authenticated
using (auth.uid() = id)
with check (auth.uid() = id);

drop policy if exists "Users can read own payments" on public.payments;
create policy "Users can read own payments"
on public.payments
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can read own applications" on public.applications;
create policy "Users can read own applications"
on public.applications
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can insert own applications" on public.applications;
create policy "Users can insert own applications"
on public.applications
for insert
to authenticated
with check (auth.uid() = user_id);
