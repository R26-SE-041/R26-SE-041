"""Run separately from the web API so browser/server restarts do not stop jobs."""
from __future__ import annotations
import logging
import signal
import threading
import time
from studio.repository import Repository
from studio.pipeline import Pipeline
from dotenv import load_dotenv

log = logging.getLogger(__name__)

def process_job(repo, pipeline, job):
    stopped = threading.Event()
    def keep_lease():
        while not stopped.wait(20):
            try:
                if not repo.heartbeat(job):
                    return
            except Exception:
                log.exception("Job heartbeat failed")
    heart = threading.Thread(target=keep_lease,daemon=True)
    heart.start()
    try:
        result = pipeline.run(job)
        repo.update_job(job,status="completed",stage="completed",result=result,state={})
    except Exception as exc:
        log.exception("Job %s failed",job["id"])
        message = str(exc)[:500] if isinstance(exc,(RuntimeError,ValueError)) else "Generation service unavailable. Retry from history."
        try:
            repo.update_job(job,status="failed",stage="failed",error=message)
            if job["kind"]=="analysis":
                a=job["payload"]["analysis"]
                repo.append_interaction(str(job["user_id"]),str(job["generation_id"]),
                    {"id":a["id"],"mode":a["mode"],"question":a.get("question") or
                        ("Identify selected object" if a["mode"]=="identify" else "Explain selected region"),
                     "answer":"","selection":a["interaction"],"structureId":a.get("structure_id"),
                     "status":"failed","error":message,"jobId":str(job["id"])})
            if job["kind"] in {"generate","sketch","enhance"}:
                repo.append_chat_event(str(job["user_id"]),job["payload"].get("chat_id") or str(job["id"]),
                    str(job["id"])+":error","error",{"message":message,"jobId":str(job["id"])})
            if job.get("generation_id"):
                patch = {"labelingError":message} if job["kind"]=="labels" else {"threeDJob":{"status":"failed","requestId":str(job["id"]),"error":message}} if job["kind"]=="threed" else {}
                if patch:
                    repo.patch_history(str(job["user_id"]),str(job["generation_id"]),patch)
        except Exception:
            log.exception("Unable to persist job failure")
    finally:
        stopped.set()
        heart.join(timeout=2)

def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    shutdown = threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:shutdown.set())
    signal.signal(signal.SIGINT,lambda *_:shutdown.set())
    repo = Repository()
    pipeline = Pipeline(repo=repo)
    while not shutdown.is_set():
        try:
            job = repo.claim()
            if job:
                process_job(repo,pipeline,job)
            else:
                shutdown.wait(2)
        except Exception:
            log.exception("Worker could not access queue")
            shutdown.wait(5)

if __name__ == "__main__":
    main()
