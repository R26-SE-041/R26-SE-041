"""CPU-only Studio API for Render or any ASGI host."""
from __future__ import annotations
import os
from datetime import datetime
from uuid import UUID, uuid4
import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from studio.repository import Repository
from studio.storage import Storage
from studio.schemas import JobRequest, HistoryPatch, Interaction, HistoryImport, ChatEvent, ChatPatch
from studio.pipeline import configured_endpoints, required_services

load_dotenv()
app = FastAPI(title="Koji Interactive Studio",version="2.0.0")
app.add_middleware(CORSMiddleware,
    allow_origins=[s.strip() for s in os.getenv("CORS_ORIGINS","http://localhost:8081,http://localhost:8091").split(",") if s.strip()],
    allow_methods=["GET","POST","PATCH","DELETE"],allow_headers=["Authorization","Content-Type"])
repo = Repository()

@app.middleware("http")
async def private_api_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/studio/", "/agents/")):
        response.headers["Cache-Control"] = "private, no-store"
    return response

def require_identity(request: Request):
    authorization = request.headers.get("authorization","")
    if not authorization.lower().startswith("bearer ") or not authorization[7:].strip():
        raise HTTPException(401,"Sign in to use cloud jobs and history")
    url,key = os.getenv("SUPABASE_URL"),os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise HTTPException(503,"Supabase authentication is not configured")
    try:
        response = requests.get(url.rstrip("/")+"/auth/v1/user",headers={"apikey":key,"Authorization":authorization},timeout=10)
        if response.status_code in {401,403}:
            raise HTTPException(401,"Session expired. Please sign in again")
        response.raise_for_status()
        user = response.json()
        return {"id":str(UUID(user["id"])), "email":user.get("email"),
                "name":(user.get("user_metadata") or {}).get("full_name"),
                "emailVerified":bool(user.get("email_confirmed_at"))}
    except HTTPException:
        raise
    except (requests.RequestException,ValueError,KeyError,TypeError):
        raise HTTPException(503,"Unable to verify your session") from None

def require_user(request: Request):
    return require_identity(request)["id"]

@app.get("/studio/account")
def account(identity=Depends(require_identity)):
    return identity

def public_job(row):
    return {key:row.get(key) for key in ("id","kind","generation_id","status","stage","result","error","created_at","updated_at")}

def history_item(row,assets=False):
    item = {**row["metadata"],"id":str(row["id"]),"createdAt":row["created_at"].isoformat(),"imageBase64":""}
    storage = Storage()
    if assets:
        events=repo.get_interactions(str(row["user_id"]),str(row["id"]))
        item["interactions"]=list({turn["id"]:turn for turn in [*item.get("interactions",[]),*events]}.values())
        item["imageBase64"] = storage.download(row["image_path"])
        if row.get("glb_path"):
            item["glbBase64"] = storage.download(row["glb_path"])
    else:
        item["imageUrl"] = storage.signed_url(row.get("thumbnail_path") or row["image_path"])
        item["hasThreeD"] = bool(row.get("glb_path"))
    return item

@app.get("/health")
def health():
    return {"status":"ok","service":"koji-studio"}

@app.get("/ready")
def ready():
    missing=[key for key in ("DATABASE_URL","SUPABASE_URL","SUPABASE_ANON_KEY","SUPABASE_SERVICE_ROLE_KEY") if not os.getenv(key)]
    if missing:
        raise HTTPException(503,"Configure backend settings: "+", ".join(missing))
    from studio.repository import connection
    with connection() as conn,conn.cursor() as cur:
        cur.execute("select 1 from koji_chats limit 1")
    return {"status":"ok"}

@app.post("/studio/jobs",status_code=202)
def start_job(body: JobRequest,user_id: str=Depends(require_user)):
    payload = body.model_dump(mode="json")
    endpoints = configured_endpoints()
    missing = required_services(payload)-endpoints.keys()
    if missing:
        raise HTTPException(503,"Required model services are not configured: "+", ".join(sorted(missing)))
    try:
        job = repo.create_job(user_id,payload,endpoints)
    except LookupError:
        raise HTTPException(404,"Source generation not found")
    except OverflowError as exc:
        raise HTTPException(429,str(exc))
    except ValueError as exc:
        raise HTTPException(409,str(exc))
    if body.kind == "labels" and job["status"] in {"queued","running"}:
        repo.patch_history(user_id,str(body.generation_id),{"annotationsEdited":False})
    if body.kind == "threed" and job["status"] in {"queued","running"}:
        repo.patch_history(user_id,str(body.generation_id),{"threeDJob":{"status":"converting","requestId":str(job["id"])}})
    return public_job(job)

@app.get("/studio/jobs")
def list_jobs(user_id: str=Depends(require_user)):
    return [public_job(row) for row in repo.list_jobs(user_id)]

@app.get("/studio/jobs/{job_id}")
def get_job(job_id: UUID,user_id: str=Depends(require_user)):
    row = repo.get_job(user_id,str(job_id))
    if not row:
        raise HTTPException(404,"Job not found")
    return public_job(row)

@app.post("/studio/jobs/{job_id}/retry",status_code=202)
def retry_job(job_id: UUID,user_id: str=Depends(require_user)):
    old = repo.get_job(user_id,str(job_id))
    if not old:
        raise HTTPException(404,"Job not found")
    if old["status"] != "failed":
        raise HTTPException(409,"Only failed jobs can be retried")
    payload = {**old["payload"],"request_id":str(uuid4())}
    if payload["kind"]=="analysis":
        payload["analysis"]={**payload["analysis"],"id":"question."+str(uuid4())}
    return start_job(JobRequest.model_validate(payload),user_id)

@app.get("/studio/history")
def list_history(before: datetime | None=Query(default=None),user_id: str=Depends(require_user)):
    return [history_item(row) for row in repo.list_history(user_id,before)]

@app.get("/studio/history/{generation_id}")
def get_history(generation_id: UUID,model_event: str | None=Query(default=None,max_length=160),user_id: str=Depends(require_user)):
    row = repo.get_history(user_id,str(generation_id))
    if not row:
        raise HTTPException(404,"Generation not found")
    if model_event:
        path=repo.model_path(user_id,str(generation_id),model_event)
        if not path:
            raise HTTPException(404,"3D model version not found")
        row={**row,"glb_path":path}
    return history_item(row,assets=True)

@app.patch("/studio/history/{generation_id}")
def patch_history(generation_id: UUID,body: HistoryPatch,user_id: str=Depends(require_user)):
    try:
        repo.patch_history(user_id,str(generation_id),{**body.model_dump(mode="json",exclude_none=True),**({"annotationsEdited":True} if body.anatomyAnnotations is not None else {})})
    except LookupError:
        raise HTTPException(404,"Generation not found")
    return {"status":"saved"}

@app.post("/studio/history/{generation_id}/interactions")
def append_interaction(generation_id: UUID,body: Interaction,user_id: str=Depends(require_user)):
    if not repo.get_history(user_id,str(generation_id)):
        raise HTTPException(404,"Generation not found")
    repo.append_interaction(user_id,str(generation_id),body.model_dump())
    return {"status":"saved"}

@app.delete("/studio/history/{generation_id}")
def delete_history(generation_id: UUID,user_id: str=Depends(require_user)):
    row = repo.get_history(user_id,str(generation_id))
    if not row:
        raise HTTPException(404,"Generation not found")
    try:
        repo.delete_history(user_id,str(generation_id),before_delete=lambda: Storage().remove(repo.asset_paths(user_id,str(generation_id))))
    except ValueError as exc:
        raise HTTPException(409,str(exc))
    return {"status":"deleted"}


@app.post("/studio/import",status_code=201)
def import_history(body: HistoryImport,user_id: str=Depends(require_user)):
    from uuid import uuid5, NAMESPACE_URL
    generation_id = str(uuid5(NAMESPACE_URL,user_id+":"+body.legacy_id))
    existing = repo.get_history(user_id,generation_id)
    if existing:
        if body.glb_base64 and not existing.get("glb_path"):
            path = Storage().upload(f"{user_id}/{generation_id}/model.glb",body.glb_base64,"model/gltf-binary")
            repo.patch_history(user_id,generation_id,{},glb_path=path)
            existing={**existing,"glb_path":path}
        if existing.get("glb_path"):
            repo.append_chat_event(user_id,existing["metadata"].get("chatId") or generation_id,generation_id+":import3d","threed",
                {"glbPath":existing["glb_path"],"imported":True},generation_id)
        return {"id":generation_id}
    storage = Storage()
    path = storage.upload(f"{user_id}/{generation_id}/image.png",body.image_base64,"image/png")
    # Keep only app metadata; never accept owner, paths or job controls from an import.
    allowed = {"prompt","enhancedPrompt","mode","speedMode","sketchStrokes","sketchMetadata",
        "sketchStrength","chatId","version","interactions","anatomy","anatomyAnnotations","evaluation","glbSizeKb","enhancedPayload"}
    metadata = {key:value for key,value in body.metadata.items() if key in allowed}
    thumbnail_path=storage.upload_thumbnail(f"{user_id}/{generation_id}/thumbnail.png",body.image_base64)
    repo.save_history(user_id,generation_id,metadata,path,created_at=body.created_at,thumbnail_path=thumbnail_path)
    repo.append_chat_event(user_id,metadata.get("chatId") or generation_id,generation_id+":image","image",
        {"mode":metadata.get("mode"),"prompt":metadata.get("prompt"),"enhancedPrompt":metadata.get("enhancedPrompt")},generation_id)
    for interaction in metadata.get("interactions",[]):
        repo.append_interaction(user_id,generation_id,interaction)
    if body.glb_base64:
        glb_path = storage.upload(f"{user_id}/{generation_id}/model.glb",body.glb_base64,"model/gltf-binary")
        repo.patch_history(user_id,generation_id,{},glb_path=glb_path)
        repo.append_chat_event(user_id,metadata.get("chatId") or generation_id,generation_id+":import3d","threed",
            {"glbPath":glb_path,"imported":True},generation_id)
    return {"id":generation_id}


@app.get("/studio/chats")
def list_chats(before: datetime | None=Query(default=None),before_id: str=Query(default="",max_length=128),
               query: str=Query(default="",max_length=100),user_id: str=Depends(require_user)):
    return repo.list_chats(user_id,before,before_id,query.strip())

@app.post("/studio/chats/{chat_id}/events",status_code=201)
def add_chat_event(chat_id: str,body: ChatEvent,user_id: str=Depends(require_user)):
    if not chat_id or len(chat_id)>128:
        raise HTTPException(422,"Invalid conversation ID")
    try:
        repo.append_chat_event(user_id,chat_id,body.id,body.kind,body.data)
    except ValueError as exc:
        raise HTTPException(409,str(exc))
    return {"status":"saved"}

@app.get("/studio/chats/{chat_id}/events")
def get_chat_events(chat_id: str,before: datetime | None=Query(default=None),
                    before_id: str=Query(default="",max_length=160),user_id: str=Depends(require_user)):
    if not repo.get_chat(user_id,chat_id):
        raise HTTPException(404,"Conversation not found")
    result=[]
    storage=Storage()
    for row in repo.list_chat_events(user_id,chat_id,before,before_id):
        event={"id":row["id"],"kind":row["kind"],"generationId":str(row["generation_id"]) if row["generation_id"] else None,
               "data":row["data"],"createdAt":row["created_at"].isoformat()}
        if row["kind"]=="image" and row.get("image_path"):
            event["imageUrl"]=storage.signed_url(row.get("thumbnail_path") or row["image_path"])
            event["hasThreeD"]=bool(row.get("glb_path"))
        result.append(event)
    return result

@app.patch("/studio/chats/{chat_id}")
def rename_chat(chat_id: str,body: ChatPatch,user_id: str=Depends(require_user)):
    if not body.title.strip():
        raise HTTPException(422,"Conversation title cannot be blank")
    try:
        repo.rename_chat(user_id,chat_id,body.title.strip())
    except LookupError:
        raise HTTPException(404,"Conversation not found")
    return {"status":"saved"}

@app.delete("/studio/chats/{chat_id}")
def delete_chat(chat_id: str,user_id: str=Depends(require_user)):
    if not repo.get_chat(user_id,chat_id):
        raise HTTPException(404,"Conversation not found")
    try:
        repo.delete_chat(user_id,chat_id,Storage().remove)
    except ValueError as exc:
        raise HTTPException(409,str(exc))
    return {"status":"deleted"}

ALLOWED_ROUTES = {"prompt":{"enhance"},"interactive":{"analyze","auto-labels"}}
@app.get("/agents/{service}/{path}")
def proxy(service: str,path: str,request: Request,user_id: str=Depends(require_user)):
    if request.method == "GET" and path != "health" or request.method == "POST" and path not in ALLOWED_ROUTES.get(service,set()):
        raise HTTPException(404,"Route not found")
    url = configured_endpoints().get(service)
    if not url:
        raise HTTPException(503,"Service is not configured")
    # POST parsing is handled by the dedicated async endpoint below.
    if request.method == "POST":
        raise HTTPException(405,"Use the POST agent route")
    response = requests.get(url+"/"+path,timeout=10)
    return JSONResponse(response.json(),status_code=response.status_code)

# Separate async handler reads the request without blocking the event loop for I/O.
@app.post("/agents/{service}/{path}")
async def proxy_post(service: str,path: str,request: Request,user_id: str=Depends(require_user)):
    if path not in ALLOWED_ROUTES.get(service,set()):
        raise HTTPException(404,"Route not found")
    url = configured_endpoints().get(service)
    if not url:
        raise HTTPException(503,"Service is not configured")
    body = await request.body()
    if len(body)>20*1024*1024:
        raise HTTPException(413,"Request is too large")
    from starlette.concurrency import run_in_threadpool
    response = await run_in_threadpool(requests.post,url+"/"+path,data=body,headers={"Content-Type":"application/json"},timeout=(15,600))
    return JSONResponse(response.json(),status_code=response.status_code)

@app.api_route("/{path:path}",methods=["GET","POST","DELETE"])
async def legacy_feedback(path: str,request: Request):
    if path not in {"feedback","memory/context","memory/settings","memory/preferences","memory/clear"} and not path.startswith("memory/preferences/"):
        raise HTTPException(404,"Route not found")
    url = os.getenv("ORCHESTRATOR_URL","").rstrip("/")
    if not url:
        raise HTTPException(503,"Feedback service is not configured")
    from starlette.concurrency import run_in_threadpool
    body = await request.body()
    if len(body)>64*1024:
        raise HTTPException(413,"Request is too large")
    response = await run_in_threadpool(requests.request,request.method,url+"/"+path,
        data=body,params=dict(request.query_params),headers={"Content-Type":"application/json","Authorization":request.headers.get("authorization","")},timeout=(10,90))
    return JSONResponse(response.json(),status_code=response.status_code)

@app.exception_handler(Exception)
async def unexpected_error(request: Request,exc: Exception):
    import logging
    logging.getLogger(__name__).exception("Studio request failed")
    return JSONResponse({"error":"Studio service temporarily unavailable. Please retry."},status_code=503)
