-- Additive migration: existing tables and pipelines remain intact.
begin;
create table if not exists public.koji_generations (
    id uuid primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    metadata jsonb not null default '{}'::jsonb,
    image_path text not null,
    glb_path text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists koji_generations_owner_created on public.koji_generations(user_id, created_at desc);
create table if not exists public.koji_jobs (
    id uuid primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    request_id uuid not null,
    kind text not null check (kind in ('generate','sketch','labels','threed')),
    generation_id uuid references public.koji_generations(id) on delete cascade,
    status text not null default 'queued' check (status in ('queued','running','completed','failed')),
    stage text not null default 'queued',
    payload jsonb not null,
    endpoints jsonb not null,
    state jsonb not null default '{}'::jsonb,
    result jsonb,
    error text,
    lease_token uuid,
    lease_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(user_id, request_id)
);
create index if not exists koji_jobs_queue on public.koji_jobs(status, lease_until, created_at);
create index if not exists koji_jobs_owner_created on public.koji_jobs(user_id, created_at desc);
alter table public.koji_generations enable row level security;
alter table public.koji_jobs enable row level security;
drop policy if exists koji_generations_read_own on public.koji_generations;
create policy koji_generations_read_own on public.koji_generations for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists koji_jobs_read_own on public.koji_jobs;
create policy koji_jobs_read_own on public.koji_jobs for select to authenticated using ((select auth.uid()) = user_id);
revoke all on public.koji_generations, public.koji_jobs from anon, authenticated;
grant select on public.koji_generations, public.koji_jobs to authenticated;
insert into storage.buckets(id, name, public, file_size_limit, allowed_mime_types)
values ('koji-generations', 'koji-generations', false, 104857600, array['image/png','model/gltf-binary'])
on conflict(id) do nothing;
drop policy if exists koji_assets_read_own on storage.objects;
create policy koji_assets_read_own on storage.objects for select to authenticated
using (bucket_id = 'koji-generations' and (storage.foldername(name))[1] = (select auth.uid())::text);
commit;
