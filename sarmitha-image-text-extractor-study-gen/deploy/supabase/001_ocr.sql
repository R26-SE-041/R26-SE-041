begin;

create table if not exists public.ocr_runs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  extracted_text text not null,
  extracted_text_ta text not null default '',
  extracted_text_en text not null default '',
  lines jsonb not null default '[]'::jsonb
);

create table if not exists public.ocr_feedback (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  object_path text not null unique,
  corrected_text text not null check (length(trim(corrected_text)) between 1 and 10000)
);

alter table public.ocr_runs enable row level security;
alter table public.ocr_feedback enable row level security;
revoke all on public.ocr_runs, public.ocr_feedback from anon, authenticated;
grant select, insert, update, delete on public.ocr_runs, public.ocr_feedback to service_role;

-- No browser access policies: only the EC2 backend's service role can access data.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('ocr-feedback', 'ocr-feedback', false, 10485760, array['image/jpeg'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

commit;
