begin;
-- Preserve existing documents and passages, independently of their original chat.
alter table public.koji_documents drop constraint if exists koji_documents_user_id_chat_id_fkey;
alter table public.koji_documents alter column chat_id drop not null;
alter table public.koji_documents drop constraint if exists koji_documents_user_id_fkey;
alter table public.koji_documents add constraint koji_documents_user_id_fkey
    foreign key(user_id) references auth.users(id) on delete cascade;
update public.koji_documents set chat_id=null where chat_id is not null;
update public.koji_jobs set payload=payload-'chat_id'
    where kind='document_index' and payload ? 'chat_id';
create index if not exists koji_documents_workspace on public.koji_documents(user_id,created_at,id);
commit;
