begin;
create extension if not exists vector;
set local search_path = public, extensions;
alter table public.koji_jobs drop constraint if exists koji_jobs_kind_check;
alter table public.koji_jobs add constraint koji_jobs_kind_check
    check(kind in ('generate','sketch','labels','threed','analysis','enhance','document_index'));

create table if not exists public.koji_documents (
    id uuid primary key,
    user_id uuid not null,
    chat_id text not null,
    filename text not null,
    storage_path text not null,
    size_bytes bigint not null check(size_bytes > 0),
    status text not null default 'processing' check(status in ('processing','ready','failed')),
    error text,
    page_count integer,
    skipped_pages integer not null default 0,
    job_id uuid references public.koji_jobs(id) on delete set null,
    created_at timestamptz not null default now(),
    unique(user_id,id),
    foreign key(user_id,chat_id) references public.koji_chats(user_id,id) on delete cascade
);
create index if not exists koji_documents_chat on public.koji_documents(user_id,chat_id,created_at);
create table if not exists public.koji_document_chunks (
    id bigserial primary key,
    user_id uuid not null,
    document_id uuid not null,
    page integer not null check(page > 0),
    content text not null,
    embedding vector(384) not null,
    fts tsvector generated always as (to_tsvector('english',content)) stored,
    foreign key(user_id,document_id) references public.koji_documents(user_id,id) on delete cascade
);
create index if not exists koji_document_chunks_scope on public.koji_document_chunks(user_id,document_id);
create index if not exists koji_document_chunks_fts on public.koji_document_chunks using gin(fts);
-- Exact vector search within the selected PDFs keeps small student libraries simple.
alter table public.koji_documents enable row level security;
alter table public.koji_document_chunks enable row level security;
drop policy if exists koji_documents_read_own on public.koji_documents;
create policy koji_documents_read_own on public.koji_documents for select to authenticated
    using((select auth.uid())=user_id);
drop policy if exists koji_document_chunks_read_own on public.koji_document_chunks;
create policy koji_document_chunks_read_own on public.koji_document_chunks for select to authenticated
    using((select auth.uid())=user_id);
revoke all on public.koji_documents,public.koji_document_chunks from anon,authenticated;
grant select on public.koji_documents,public.koji_document_chunks to authenticated;
update storage.buckets set allowed_mime_types = array['image/png','model/gltf-binary','application/pdf']
    where id='koji-generations';
commit;
