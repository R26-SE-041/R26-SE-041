begin;

alter table public.ocr_runs add column if not exists user_id uuid references auth.users(id) on delete cascade;
alter table public.ocr_runs add column if not exists filename text not null default 'Untitled image';
alter table public.ocr_feedback add column if not exists user_id uuid references auth.users(id) on delete cascade;
create index if not exists ocr_runs_user_created_idx on public.ocr_runs (user_id, created_at desc, id desc);

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '' check (length(display_name) <= 100),
  created_at timestamptz not null default now()
);
create table if not exists public.auth_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  event_type text not null check (event_type in ('sign_up', 'sign_in', 'sign_out')),
  created_at timestamptz not null default now()
);
create index if not exists auth_events_user_created_idx on public.auth_events (user_id, created_at desc);
alter table public.profiles enable row level security;
alter table public.auth_events enable row level security;

revoke all on public.profiles, public.auth_events from anon, authenticated;
grant select on public.profiles, public.auth_events to authenticated;
grant update (display_name) on public.profiles to authenticated;
grant all on public.profiles, public.auth_events to service_role;
grant select, insert, delete on public.ocr_runs to authenticated;
grant select on public.ocr_feedback to authenticated;

drop policy if exists "Read own profile" on public.profiles;
create policy "Read own profile" on public.profiles for select to authenticated using ((select auth.uid()) = id);
drop policy if exists "Update own name" on public.profiles;
create policy "Update own name" on public.profiles for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
drop policy if exists "Read own account events" on public.auth_events;
create policy "Read own account events" on public.auth_events for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "Read own OCR runs" on public.ocr_runs;
create policy "Read own OCR runs" on public.ocr_runs for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "Insert own OCR runs" on public.ocr_runs;
create policy "Insert own OCR runs" on public.ocr_runs for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists "Delete own OCR runs" on public.ocr_runs;
create policy "Delete own OCR runs" on public.ocr_runs for delete to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "Read own feedback" on public.ocr_feedback;
create policy "Read own feedback" on public.ocr_feedback for select to authenticated using ((select auth.uid()) = user_id);

create or replace function public.handle_new_sarmitha_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, left(coalesce(new.raw_user_meta_data ->> 'display_name', ''), 100));
  insert into public.auth_events (user_id, event_type) values (new.id, 'sign_up');
  return new;
end;
$$;
revoke all on function public.handle_new_sarmitha_user() from public, anon, authenticated;
drop trigger if exists on_sarmitha_user_created on auth.users;
create trigger on_sarmitha_user_created after insert on auth.users
for each row execute function public.handle_new_sarmitha_user();

insert into public.profiles (id, display_name)
select id, left(coalesce(raw_user_meta_data ->> 'display_name', ''), 100) from auth.users
on conflict (id) do nothing;

commit;
