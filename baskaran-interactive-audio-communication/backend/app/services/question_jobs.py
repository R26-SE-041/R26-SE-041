"""Bounded, owner-scoped in-flight answers for mobile-safe short HTTP polling.

Operational state only: final history persistence is unchanged. One backend
worker is required. A restart loses these temporary jobs, never saved history.
"""
import asyncio
import hashlib
import json
import logging
import time
from uuid import uuid4
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class QuestionJobs:
    def __init__(self, *, limit=64, ttl=900, timeout=600, clock=time.monotonic):
        self.limit, self.ttl, self.timeout, self.clock = limit, ttl, timeout, clock
        self.jobs = {}
        self.requests = {}
        self.tasks = set()

    def start(self, owner, request_id, payload, generate):
        now = self.clock()
        for job_id, job in list(self.jobs.items()):
            if job['status'] != 'pending' and now - job['finished'] > self.ttl:
                self.requests.pop((job['owner'], job['request_id']), None)
                del self.jobs[job_id]
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        key = (owner, str(request_id))
        existing = self.requests.get(key)
        if existing:
            if self.jobs[existing]['fingerprint'] != fingerprint:
                raise HTTPException(409, 'This request ID belongs to a different question.')
            return {'job_id': existing, 'status': self.jobs[existing]['status']}
        if len(self.jobs) >= self.limit:
            raise HTTPException(503, 'The answer queue is full. Please retry shortly.')
        if sum(j['owner'] == owner and j['status'] == 'pending' for j in self.jobs.values()) >= 2:
            raise HTTPException(429, 'Two answers are already being prepared. Please wait before asking again.')
        job_id = str(uuid4())
        self.jobs[job_id] = {'owner': owner, 'request_id': str(request_id), 'fingerprint': fingerprint,
                             'status': 'pending', 'finished': None, 'result': None, 'error': None}
        self.requests[key] = job_id
        task = asyncio.create_task(self._run(job_id, generate))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return {'job_id': job_id, 'status': 'pending'}

    async def _run(self, job_id, generate):
        job = self.jobs[job_id]
        try:
            result = await asyncio.wait_for(generate(), timeout=self.timeout)
            result = result.model_dump(mode='json') if hasattr(result, 'model_dump') else result
            if len(json.dumps(result).encode()) > 262144:
                raise HTTPException(502, 'The generated answer is too large. Please ask a shorter question.')
            job.update(status='complete', result=result)
        except HTTPException as exc:
            job.update(status='failed', error=str(exc.detail), error_status=exc.status_code)
        except (TimeoutError, asyncio.CancelledError):
            job.update(status='failed', error='Answer preparation timed out or the server restarted. Please retry.', error_status=504)
        except Exception:
            logger.exception('Answer job failed: %s', job_id)
            job.update(status='failed', error='The answer could not be prepared. Please retry.', error_status=503)
        finally:
            job['finished'] = self.clock()

    def read(self, owner, job_id):
        job = self.jobs.get(job_id)
        if not job or job['owner'] != owner or (job['finished'] is not None and self.clock() - job['finished'] > self.ttl):
            raise HTTPException(404, 'Answer request expired or the server restarted. Please retry your question.')
        return {'job_id': job_id, 'status': job['status'], 'result': job['result'], 'error': job['error'],
                'error_status': job.get('error_status')}

question_jobs = QuestionJobs()
