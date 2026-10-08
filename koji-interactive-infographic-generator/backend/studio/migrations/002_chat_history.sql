-- Conversation events are separate rows: long chats do not rewrite image metadata.
begin;
alter table public.koji_generations add column if not exists thumbnail_path text;
alter table public.koji_jobs drop constraint if exists koji_jobs_kind_check;
alter table public.koji_jobs add constraint koji_jobs_kind_check
    check(kind in ('generate','sketch','labels','threed','analysis','enhance'));
create table if not exists public.koji_chats (
    user_id uuid not null references auth.users(id) on delete cascade,
    id text not null,
    title text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key(user_id,id)
);
create table if not exists public.koji_chat_events (
    user_id uuid not null,
    id text not null,
    chat_id text not null,
    kind text not null check(kind in ('prompt','enhancement','image','interaction','labels','threed','error')),
    generation_id uuid references public.koji_generations(id) on delete cascade,
    data jsonb not null,
    created_at timestamptz not null default now(),
    primary key(user_id,id),
    foreign key(user_id,chat_id) references public.koji_chats(user_id,id) on delete cascade
);
create index if not exists koji_chats_owner_updated on public.koji_chats(user_id,updated_at desc,id);
create index if not exists koji_chat_events_timeline on public.koji_chat_events(user_id,chat_id,created_at,id);
create index if not exists koji_chat_events_generation on public.koji_chat_events(user_id,generation_id,kind);
alter table public.koji_chats enable row level security;
alter table public.koji_chat_events enable row level security;
drop policy if exists koji_chats_read_own on public.koji_chats;
create policy koji_chats_read_own on public.koji_chats for select to authenticated using((select auth.uid())=user_id);
drop policy if exists koji_chat_events_read_own on public.koji_chat_events;
create policy koji_chat_events_read_own on public.koji_chat_events for select to authenticated using((select auth.uid())=user_id);
revoke all on public.koji_chats,public.koji_chat_events from anon,authenticated;
grant select on public.koji_chats,public.koji_chat_events to authenticated;

-- Bring existing cloud generations into conversations without changing assets.
insert into public.koji_chats(user_id,id,title,created_at,updated_at)
select user_id,coalesce(metadata->>'chatId',id::text),
    left(coalesce(nullif(min(metadata->>'prompt'),''),'Saved creation'),80),min(created_at),max(updated_at)
from public.koji_generations group by user_id,coalesce(metadata->>'chatId',id::text)
on conflict(user_id,id) do nothing;
insert into public.koji_chat_events(user_id,id,chat_id,kind,generation_id,data,created_at)
select user_id,id::text||':image',coalesce(metadata->>'chatId',id::text),'image',id,
    jsonb_build_object('mode',metadata->>'mode','version',metadata->'version',
        'prompt',metadata->>'prompt','enhancedPrompt',metadata->>'enhancedPrompt'),created_at
from public.koji_generations on conflict(user_id,id) do nothing;
insert into public.koji_chat_events(user_id,id,chat_id,kind,generation_id,data,created_at)
select g.user_id,coalesce(nullif(turn.value->>'id',''),g.id::text||':question:'||turn.ordinality),
    coalesce(g.metadata->>'chatId',g.id::text),'interaction',g.id,
    turn.value || jsonb_build_object('id',coalesce(nullif(turn.value->>'id',''),g.id::text||':question:'||turn.ordinality),
        'status',coalesce(turn.value->>'status','completed')),
    coalesce(nullif(turn.value->>'createdAt','')::timestamptz,g.created_at)
from public.koji_generations g cross join lateral jsonb_array_elements(
    case when jsonb_typeof(g.metadata->'interactions')='array' then g.metadata->'interactions' else '[]'::jsonb end
) with ordinality turn(value,ordinality)
on conflict(user_id,id) do nothing;
insert into public.koji_chat_events(user_id,id,chat_id,kind,generation_id,data,created_at)
select user_id,id::text||':import3d',coalesce(metadata->>'chatId',id::text),'threed',id,
    jsonb_build_object('glbPath',glb_path,'prompt',metadata->>'prompt','input','saved 2D image'),updated_at
from public.koji_generations where glb_path is not null
on conflict(user_id,id) do nothing;
commit;
