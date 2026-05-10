-- Run this in Supabase SQL editor.
-- It creates the core app tables for profiles, subscriptions, assistant history,
-- payments, and application tracking.

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text default '',
  target_role text default '',
  skills text[] default '{}',
  experience_level text default '',
  plan text not null default 'basic' check (plan in ('basic', 'pro')),
  plan_status text not null default 'inactive',
  stripe_customer_id text,
  manual_pro_access boolean not null default false,
  manual_pro_granted_at timestamptz,
  application_profile jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles
  add column if not exists application_profile jsonb not null default '{}'::jsonb;
alter table public.profiles
  add column if not exists plan text not null default 'basic';
alter table public.profiles
  add column if not exists plan_status text not null default 'inactive';
alter table public.profiles
  add column if not exists stripe_customer_id text;
alter table public.profiles
  add column if not exists manual_pro_access boolean not null default false;
alter table public.profiles
  add column if not exists manual_pro_granted_at timestamptz;

create table if not exists public.payments (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  stripe_session_id text not null unique,
  stripe_payment_intent_id text,
  price_id text,
  mode text,
  status text not null default 'pending',
  amount_total bigint,
  currency text,
  created_at timestamptz not null default now()
);

alter table public.payments
  add column if not exists stripe_payment_intent_id text;
alter table public.payments
  add column if not exists price_id text;
alter table public.payments
  add column if not exists mode text;

create table if not exists public.subscriptions (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  stripe_customer_id text,
  stripe_subscription_id text not null unique,
  stripe_price_id text,
  status text not null default 'active',
  current_period_start timestamptz,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
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

create table if not exists public.assistant_threads (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'Career Assistant',
  mode text not null default 'job_search_planning',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.assistant_messages (
  id bigserial primary key,
  thread_id bigint not null references public.assistant_threads(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_payments_user_id on public.payments(user_id);
create index if not exists idx_subscriptions_user_id on public.subscriptions(user_id);
create index if not exists idx_applications_user_id on public.applications(user_id);
create index if not exists idx_assistant_threads_user_id on public.assistant_threads(user_id);
create index if not exists idx_assistant_messages_user_id on public.assistant_messages(user_id);
create index if not exists idx_assistant_messages_thread_id on public.assistant_messages(thread_id);

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

drop trigger if exists trg_subscriptions_updated_at on public.subscriptions;
create trigger trg_subscriptions_updated_at
before update on public.subscriptions
for each row execute function public.set_updated_at();

drop trigger if exists trg_assistant_threads_updated_at on public.assistant_threads;
create trigger trg_assistant_threads_updated_at
before update on public.assistant_threads
for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.payments enable row level security;
alter table public.subscriptions enable row level security;
alter table public.applications enable row level security;
alter table public.assistant_threads enable row level security;
alter table public.assistant_messages enable row level security;

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

drop policy if exists "Users can read own subscriptions" on public.subscriptions;
create policy "Users can read own subscriptions"
on public.subscriptions
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

drop policy if exists "Users can read own assistant threads" on public.assistant_threads;
create policy "Users can read own assistant threads"
on public.assistant_threads
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can insert own assistant threads" on public.assistant_threads;
create policy "Users can insert own assistant threads"
on public.assistant_threads
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "Users can update own assistant threads" on public.assistant_threads;
create policy "Users can update own assistant threads"
on public.assistant_threads
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "Users can read own assistant messages" on public.assistant_messages;
create policy "Users can read own assistant messages"
on public.assistant_messages
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can insert own assistant messages" on public.assistant_messages;
create policy "Users can insert own assistant messages"
on public.assistant_messages
for insert
to authenticated
with check (auth.uid() = user_id);
