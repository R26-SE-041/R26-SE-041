begin;
alter table public.koji_chats add column if not exists deleted_at timestamptz;
create index if not exists koji_chats_owner_bin_updated
    on public.koji_chats(user_id, (deleted_at is not null), updated_at desc, id);
commit;
