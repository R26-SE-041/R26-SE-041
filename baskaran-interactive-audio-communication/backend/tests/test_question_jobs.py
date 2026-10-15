import asyncio
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.services.question_jobs import QuestionJobs

@pytest.mark.asyncio
async def test_disconnect_retry_reuses_job_and_completed_result_without_duplicate_generation():
    jobs=QuestionJobs(); started=asyncio.Event(); finish=asyncio.Event(); calls=0
    async def generate():
        nonlocal calls
        calls+=1; started.set(); await finish.wait()
        return {'answer':'A grounded answer','references':[]}
    request=str(uuid4()); payload={'transcript':'Question','language':'english'}
    first=jobs.start('alice',request,payload,generate)
    await started.wait()
    assert jobs.start('alice',request,payload,generate)['job_id']==first['job_id']
    assert jobs.read('alice',first['job_id'])['status']=='pending'
    finish.set(); await asyncio.gather(*jobs.tasks)
    assert jobs.start('alice',request,payload,generate)['job_id']==first['job_id']
    assert jobs.read('alice',first['job_id'])['result']['answer']=='A grounded answer'
    assert calls==1
    with pytest.raises(HTTPException) as denied: jobs.read('bob',first['job_id'])
    assert denied.value.status_code==404
    with pytest.raises(HTTPException) as mismatch: jobs.start('alice',request,{'transcript':'Other'},generate)
    assert mismatch.value.status_code==409

@pytest.mark.asyncio
async def test_queue_bounds_timeout_and_expiry():
    now=[0]; jobs=QuestionJobs(limit=1,ttl=5,timeout=.01,clock=lambda:now[0])
    async def slow(): await asyncio.sleep(60)
    first=jobs.start('alice',str(uuid4()),{},slow)
    with pytest.raises(HTTPException) as full: jobs.start('bob',str(uuid4()),{},slow)
    assert full.value.status_code==503
    await asyncio.gather(*jobs.tasks)
    assert jobs.read('alice',first['job_id'])['status']=='failed'
    now[0]=6
    with pytest.raises(HTTPException) as expired: jobs.read('alice',first['job_id'])
    assert expired.value.status_code==404
    second=jobs.start('bob',str(uuid4()),{},slow)
    assert second['job_id']!=first['job_id'] and len(jobs.jobs)==1
    await asyncio.gather(*jobs.tasks)

@pytest.mark.asyncio
async def test_routes_keep_job_status_owner_scoped(monkeypatch):
    from fastapi import FastAPI
    import httpx
    from app.api.v1.routes import documents
    from app.core.security import get_current_user
    from app.services import question_jobs as module
    jobs=QuestionJobs(); monkeypatch.setattr(module,'question_jobs',jobs)
    async def answer(*args):return {'answer':'Done','references':[]}
    monkeypatch.setattr(documents,'ask_question',answer)
    app=FastAPI();app.include_router(documents.router,prefix='/api/v1')
    app.dependency_overrides[get_current_user]=lambda:{'sub':'alice'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        headers={'Idempotency-Key':str(uuid4())}
        response=await client.post('/api/v1/documents/ask-jobs',headers=headers,json={'transcript':'Question'})
        assert response.status_code==202
        await asyncio.gather(*jobs.tasks)
        path='/api/v1/documents/ask-jobs/'+response.json()['job_id']
        assert (await client.get(path)).json()['result']['answer']=='Done'
        app.dependency_overrides[get_current_user]=lambda:{'sub':'bob'}
        assert (await client.get(path)).status_code==404
