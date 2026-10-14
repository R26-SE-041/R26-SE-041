"""Copy owned SQLite history/revisions to Supabase; keep original files intact.

Run with production Supabase credentials in the environment. --guest-owner is
only for an explicitly approved legacy guest library; it must be an auth UUID.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import action_store, history_store, local_document_store, cloud_user_store as cloud
from app.services.storage import _content_type


def rows(path, table, apply, snapshot=False):
    if not path.exists():
        return []
    # A backup snapshot is immutable and may be mounted read-only. SQLite must
    # not try to create WAL/shm sidecars next to that isolated copy.
    with (sqlite3.connect('file:' + path.as_posix() + '?immutable=1', uri=True) if snapshot else sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        result = [dict(row) for row in db.execute('SELECT * FROM ' + table)]
        if apply and not snapshot:
            # SQLite's backup API preserves a consistent snapshot including WAL.
            backup = path.with_name(path.stem + '-before-cloud.sqlite3')
            if not backup.exists():
                with sqlite3.connect(backup) as copy:
                    db.backup(copy)
        return result


def migrate(apply=False, guest_owner=None, source_root=None):
    if source_root:
        source = Path(source_root).resolve()
        action_store.root = lambda: source / 'actions'
        history_store._root = lambda: source / 'history'
        local_document_store._root = lambda: source / 'documents'
    if guest_owner:
        guest_owner = str(uuid.UUID(guest_owner))
    cloud.request('GET', '/rest/v1/saved_actions', params={'select': 'id', 'limit': 0})
    cloud.request('GET', '/rest/v1/study_history', params={'select': 'id', 'limit': 0})
    report = {'actions': 0, 'history': 0, 'documents': 0, 'skipped_guest': 0, 'active_actions': 0, 'applied': apply}
    actions = rows(action_store.root() / 'actions.sqlite3', 'actions', apply, bool(source_root))
    histories = rows(history_store._root() / 'history.sqlite3', 'history', apply, bool(source_root))
    documents = rows(local_document_store._root() / 'documents.sqlite3', 'documents', apply, bool(source_root))
    def owner(row):
        if row['user_id'] == 'guest':
            if not guest_owner:
                report['skipped_guest'] += 1
                return None
            return guest_owner
        return str(uuid.UUID(row['user_id']))
    for row in actions:
        data = json.loads(row['data'])
        if data['status'] not in {'complete', 'partial', 'failed', 'cancelled'} and row['expires'] > time.time():
            report['active_actions'] += 1
    if report['active_actions']:
        raise RuntimeError('Active generation jobs exist; wait before migrating')
    for row in actions:
        user_id = owner(row)
        if not user_id:
            continue
        data = json.loads(row['data'])
        if not data.get('saved'):
            continue
        record = {**row, 'user_id': user_id, 'data': data}
        if data.get('created_at'):
            record['created_at'] = data['created_at']
        if apply:
            existing = cloud.request('GET', '/rest/v1/saved_actions', params={'id': 'eq.' + row['id'], 'select': 'user_id'})
            if existing and existing[0]['user_id'] != user_id:
                raise RuntimeError('Revision belongs to a different cloud account; refusing to reassign it')
            action_store.publish_artifacts({**record, **data})
            cloud.request('POST', '/rest/v1/saved_actions', json=record,
                          headers={'Prefer': 'resolution=merge-duplicates,return=representation'})
            remote = cloud.request('GET', '/rest/v1/saved_actions', params={'id': 'eq.' + row['id'], 'user_id': 'eq.' + user_id})
            if not remote or remote[0]['data'] != data:
                raise RuntimeError('Revision metadata verification failed')
            for identifier, extension in action_store._artifacts(data):
                path = action_store.artifact(identifier, extension)
                if cloud.download('revisions', cloud.owner_path(user_id, path.name)) != path.read_bytes():
                    raise RuntimeError('Revision file verification failed')
        report['actions'] += 1
    for row in histories:
        user_id = owner(row)
        if not user_id:
            continue
        record = {'id': row['id'], 'user_id': user_id, 'question': row['question'],
                  'answer': row['answer'], 'language': row['language'],
                  'references': json.loads(row['references_json']), 'created_at': row['created_at'],
                  'source_id': 'server:' + row['id'], 'document_grounded': True,
                  'has_audio': bool(row['audio_filename']), 'has_question_audio': False}
        if apply:
            if row['audio_filename']:
                path = history_store._root() / 'audio' / (str(uuid.UUID(row['id'])) + '.wav')
                cloud.upload('study-history', cloud.owner_path(user_id, row['id'] + '-answer.audio'), path.read_bytes(), 'application/octet-stream')
            cloud.request('POST', '/rest/v1/study_history', json=record,
                          headers={'Prefer': 'resolution=merge-duplicates,return=representation'})
        report['history'] += 1
    for row in documents:
        user_id = owner(row)
        if not user_id:
            continue
        if apply:
            identifier = str(uuid.UUID(row['document_id']))
            existing = cloud.request('GET', '/rest/v1/documents', params={'id': 'eq.' + identifier, 'select': 'user_id'})
            if existing and existing[0]['user_id'] != user_id:
                raise RuntimeError('Document belongs to a different cloud account')
            # Derive the generated filename rather than interpreting a Windows
            # relative path on Linux (legacy SQLite rows use backslashes).
            path = local_document_store._root() / 'files' / (identifier + Path(row['filename']).suffix.lower())
            content = path.read_bytes()
            key = cloud.owner_path(user_id, identifier + Path(row['filename']).suffix.lower())
            cloud.upload('documents', key, content, _content_type(row['filename']))
            cloud.request('POST', '/rest/v1/documents', json={
                'id': identifier, 'user_id': user_id, 'filename': row['filename'], 'file_type': row['file_type'],
                'storage_path': key, 'chunk_count': row['chunk_count'], 'created_at': row['uploaded_at']},
                headers={'Prefer': 'resolution=merge-duplicates,return=representation'})
            if cloud.download('documents', key) != content:
                raise RuntimeError('Document byte verification failed')
        report['documents'] += 1
    print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--guest-owner')
    parser.add_argument('--source-root', type=Path, help='Isolated snapshot containing actions/ and history/')
    args = parser.parse_args()
    migrate(args.apply, args.guest_owner, args.source_root)
