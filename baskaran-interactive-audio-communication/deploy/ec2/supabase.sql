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
commit;
