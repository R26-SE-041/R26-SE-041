import copy
import uuid

import pytest

from app.services import action_store as actions, history_store as history, cloud_user_store as cloud

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'


@pytest.fixture
def remote(monkeypatch, tmp_path):
    tables = {'saved_actions': {}, 'study_history': {}}
    objects = {}

    def request(method, path, params=None, json=None, **kwargs):
        if path.endswith('/rpc/patch_saved_action'):
            row = tables['saved_actions'][json['ticket']]
            row['data'].update(json['patch'])
            return [copy.deepcopy(row)]
        table = tables[path.rsplit('/', 1)[-1]]
        if method == 'POST':
            row = copy.deepcopy(json)
            row.setdefault('created_at', row.get('data', {}).get('created_at', '2026-10-14T00:00:00Z'))
            table[row['id']] = row
            return [copy.deepcopy(row)]
        def matches(row):
            for key, value in (params or {}).items():
                if key in {'select', 'order'}:
                    continue
                actual = row.get('data', {}).get('saved', False) if key == 'saved' else row.get(key)
                actual = str(actual).lower() if isinstance(actual, bool) else str(actual)
                if value.startswith('eq.') and actual != value[3:]: return False
                if value.startswith('neq.') and actual == value[4:]: return False
            return True
        rows = [row for row in table.values() if matches(row)]
        if method == 'PATCH':
            for row in rows: row.update(json)
        elif method == 'DELETE':
            for row in rows: del table[row['id']]
        return copy.deepcopy(rows)

    def upload(bucket, path, content, mime): objects[(bucket, path)] = content
    def download(bucket, path): return objects[(bucket, path)]
    def remove(bucket, paths):
        for path in paths: objects.pop((bucket, path), None)
    monkeypatch.setattr(cloud, 'enabled', lambda: True)
    monkeypatch.setattr(cloud, 'request', request)
    monkeypatch.setattr(cloud, 'upload', upload)
    monkeypatch.setattr(cloud, 'download', download)
    monkeypatch.setattr(cloud, 'remove', remove)
    monkeypatch.setattr(actions, 'root', lambda: tmp_path)
    monkeypatch.setattr(history, '_root', lambda: tmp_path)
    return tables, objects


def test_saved_revision_restores_from_cloud_after_cache_loss_and_is_owner_scoped(remote):
    ticket = actions.create(A, 'session', 'document', 'audio_revision')
    summary, audio = uuid.uuid4().hex, uuid.uuid4().hex
    actions.update(ticket, summary='Cloud summary', summary_id=summary, audio_id=audio)
    actions.artifact(summary).write_text('Cloud summary')
    actions.artifact(audio, 'wav').write_bytes(b'RIFF-test')
    actions.update(ticket, saved=True, audio_saved=True, status='complete')
    actions.artifact(summary).unlink(); actions.artifact(audio, 'wav').unlink()
    assert actions.get(ticket, A)['saved']
    assert actions.artifact(audio, 'wav').read_bytes() == b'RIFF-test'
    with pytest.raises(ValueError): actions.get(ticket, B)
    assert actions.saved_actions(B) == []
    assert len(actions.saved_actions(A)) == 1


def test_failed_upload_never_marks_a_revision_saved(remote, monkeypatch):
    ticket = actions.create(A, 'session', 'document', 'summarize')
    identifier = uuid.uuid4().hex
    actions.update(ticket, summary_id=identifier)
    actions.artifact(identifier).write_text('summary')
    def fail(*args): raise OSError('Cloud storage unavailable')
    monkeypatch.setattr(cloud, 'upload', fail)
    with pytest.raises(OSError): actions.update(ticket, saved=True)
    assert not actions.get(ticket, A)['saved']


def test_deleting_shared_summary_preserves_other_revision(remote):
    identifier = uuid.uuid4().hex
    actions.artifact(identifier).write_text('shared summary')
    tickets = [actions.create(A, 'session', 'document', 'summarize') for _ in range(2)]
    for ticket in tickets:
        actions.update(ticket, summary_id=identifier, summary='shared summary')
        actions.update(ticket, saved=True, status='complete')
    actions.delete_saved(tickets[0], A)
    assert actions.get(tickets[1], A)['saved']
    assert remote[1][('revisions', A + '/' + identifier + '.txt')] == b'shared summary'
    actions.delete_saved(tickets[1], A)
    assert not remote[1]


def test_history_text_both_recordings_import_and_edit_are_cloud_scoped(remote):
    item = history.create_history(A, 'question', 'answer', 'tamil', [], b'RIFF-answer', b'question-webm',
                                  False, 'old-device-record', '2026-10-13T10:00:00Z')
    assert history.list_history(A)[0]['created_at'] == '2026-10-13T10:00:00Z'
    assert history.get_history(B, item['id']) is None
    assert history.list_history(B) == []
    assert history.get_audio_path(A, item['id'], 'question').read_bytes() == b'question-webm'
    assert history.get_audio_path(A, item['id']).read_bytes() == b'RIFF-answer'
    again = history.create_history(A, 'question', 'answer', 'tamil', [], None, source_id='old-device-record')
    assert again['id'] == item['id']
    assert len(history.list_history(A)) == 1
    assert history.update_answer(B, item['id'], 'unauthorized') is None
    assert history.update_answer(A, item['id'], 'edited')['has_audio'] is False
    assert history.get_audio_path(A, item['id']) is None
    assert history.attach_audio(B, item['id'], b'foreign') is None
    assert history.attach_audio(A, item['id'], b'regenerated')['has_audio']


def test_clear_history_cannot_delete_another_users_audio_or_rows(remote):
    first = history.create_history(A, 'a', 'answer', 'english', [], b'A')
    second = history.create_history(B, 'b', 'answer', 'english', [], b'B')
    assert not history.delete_history(B, first['id'])
    history.delete_history(A)
    assert history.list_history(A) == []
    assert history.get_history(B, second['id'])
    assert history.get_audio_path(B, second['id']).read_bytes() == b'B'


def test_cloud_object_paths_require_uuid_owners_and_safe_names():
    with pytest.raises(ValueError): cloud.owner_path('guest', 'file.wav')
    with pytest.raises(ValueError): cloud.owner_path(A, '../foreign.wav')


def test_cloud_document_failure_is_not_reported_as_a_successful_local_save(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.api.v1.routes import documents
    monkeypatch.setattr(documents, 'get_settings', lambda: SimpleNamespace(cloud_user_storage=True))
    def fail(*args, **kwargs): raise OSError('Cloud unavailable')
    monkeypatch.setattr(cloud, 'upload', fail)
    monkeypatch.setattr(cloud, 'request', fail)
    with pytest.raises(HTTPException) as error:
        asyncio.run(documents._try_supabase_storage(A, 'notes.txt', b'notes'))
    assert error.value.status_code == 503
    with pytest.raises(HTTPException) as error:
        asyncio.run(documents._try_supabase_insert(str(uuid.uuid4()), A, 'notes.txt', 'txt', A + '/notes.txt', 1))
    assert error.value.status_code == 503
    with pytest.raises(HTTPException) as error:
        asyncio.run(documents.list_documents({'sub': A}))
    assert error.value.status_code == 503
