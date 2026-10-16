begin;

alter table public.ocr_runs add column if not exists original_image_path text;
alter table public.ocr_runs add column if not exists enhanced_image_path text;

-- Images remain private. Only the backend service role uploads/signs/deletes;
-- history endpoints verify ownership through the user's token and table RLS.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('ocr-history', 'ocr-history', false, 52428800,
        array['image/png', 'image/jpeg', 'image/webp', 'image/bmp'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

notify pgrst, 'reload schema';
commit;
