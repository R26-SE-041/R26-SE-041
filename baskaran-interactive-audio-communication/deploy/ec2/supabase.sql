-- Run only against the dedicated VoiceLearn project.
begin;
create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  filename text not null,
  file_type text not null default 'pdf',
  storage_path text not null,
  chunk_count integer default 0,
  created_at timestamptz default now()
);
create table if not exists public.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  language text not null default 'english',
  created_at timestamptz default now()
);
alter table public.documents enable row level security;
alter table public.sessions enable row level security;
create index if not exists documents_user_id_idx on public.documents(user_id);
create index if not exists sessions_user_id_idx on public.sessions(user_id);
do $$ begin
  if not exists(select 1 from pg_policies where schemaname='public' and tablename='documents' and policyname='Users see own documents') then
    create policy "Users see own documents" on public.documents for all to authenticated
      using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
  end if;
  if not exists(select 1 from pg_policies where schemaname='public' and tablename='sessions' and policyname='Users see own sessions') then
    create policy "Users see own sessions" on public.sessions for all to authenticated
      using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
  end if;
end $$;
insert into storage.buckets (id,name,public,file_size_limit,allowed_mime_types)
values ('documents','documents',false,52428800,array[
 'application/pdf','application/vnd.openxmlformats-officedocument.presentationml.presentation',
 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','text/plain','text/markdown']),
 ('audio','audio',false,10485760,array['audio/wav','audio/mpeg','audio/webm'])
on conflict(id) do nothing;
create table if not exists public.study_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  question text not null, answer text not null, language text not null,
  "references" jsonb not null default '[]', document_grounded boolean not null default true,
  has_audio boolean not null default false, has_question_audio boolean not null default false,
  created_at timestamptz not null default now(), source_id text,
  unique(user_id, source_id)
);
create table if not exists public.saved_actions (
  id text primary key, user_id uuid not null references auth.users(id),
  session_id text not null, document_id text not null, intent text not null,
  expires double precision not null, data jsonb not null,
  saved boolean generated always as (coalesce((data->>'saved')::boolean, false)) stored,
  created_at timestamptz not null default now()
);
alter table public.study_history enable row level security;
alter table public.saved_actions enable row level security;
create index if not exists study_history_owner_date on public.study_history(user_id,created_at desc);
create index if not exists saved_actions_owner_date on public.saved_actions(user_id,saved,created_at desc);
revoke all on public.study_history,public.saved_actions from anon,authenticated;
grant select on public.study_history,public.saved_actions to authenticated;
grant all on public.study_history,public.saved_actions to service_role;
do $$ begin
  if not exists(select 1 from pg_policies where schemaname='public' and tablename='study_history' and policyname='Read own history') then
    create policy "Read own history" on public.study_history for select to authenticated using ((select auth.uid())=user_id);
  end if;
  if not exists(select 1 from pg_policies where schemaname='public' and tablename='saved_actions' and policyname='Read own saved actions') then
    create policy "Read own saved actions" on public.saved_actions for select to authenticated using ((select auth.uid())=user_id);
  end if;
end $$;
create or replace function public.patch_saved_action(ticket text, patch jsonb)
returns setof public.saved_actions language sql security invoker set search_path=public as $$
  update public.saved_actions set data=data || patch where id=ticket returning *;
$$;
revoke all on function public.patch_saved_action(text,jsonb) from public,anon,authenticated;
grant execute on function public.patch_saved_action(text,jsonb) to service_role;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values ('revisions','revisions',false,52428800,array['text/plain','application/json','audio/wav']),
       ('study-history','study-history',false,52428800,array['audio/wav','audio/webm','audio/ogg','audio/mp4','audio/mpeg','application/octet-stream'])
on conflict(id) do nothing;
-- Downloads go through authenticated backend ownership checks, not public links.
commit;
