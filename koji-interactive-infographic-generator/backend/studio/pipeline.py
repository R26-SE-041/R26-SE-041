"""Model orchestration shared by the durable worker; GPU services stay on Modal."""
from __future__ import annotations
import os
import math
import time
from urllib.parse import urlparse
from uuid import UUID, uuid5, NAMESPACE_URL
import requests
from studio.repository import Repository
from studio.storage import Storage

SERVICES = {"prompt":"PROMPT_AGENT_URL","image":"IMAGE_AGENT_URL","sketch":"SKETCH_AGENT_URL",
    "interactive":"INTERACTIVE_AGENT_URL","evaluation":"EVAL_AGENT_URL","threed":"THREED_AGENT_URL"}

def configured_endpoints():
    result = {}
    for name,env in SERVICES.items():
        url = os.getenv(env, "").rstrip("/")
        parsed = urlparse(url)
        if url and (parsed.scheme not in {"https","http"} or not parsed.netloc or parsed.username or parsed.password):
            raise ValueError(f"Invalid {env}")
        if url:
            result[name] = url
    return result

def required_services(payload):
    kind = payload["kind"]
    return {"prompt"} if kind == "enhance" else {"sketch"} if kind == "sketch" else {"image"} if kind == "generate" else {"interactive"} if kind in {"labels","analysis"} else {"threed"}

def quality_rank(value):
    return value["visualScore"] + value["pedagogicalScore"] - (20 if value["anatomyHardFailures"] else 0)

def evaluation_result(data):
    visual = data.get("visual_score", data.get("vlm_score"))
    educational = data.get("pedagogical_score", data.get("vlm_score"))
    if not isinstance(visual,(int,float)) or not isinstance(educational,(int,float)) or not math.isfinite(visual) or not math.isfinite(educational):
        raise ValueError("Evaluation scores unavailable")
    return {"clipScore":data.get("clip_score"),"vlmScore":data.get("vlm_score"),
        "visualScore":visual,"pedagogicalScore":educational,"feedback":data.get("vlm_feedback") or "",
        "anatomyHardFailures":data.get("anatomy_hard_failures") or []}

class Pipeline:
    def __init__(self,repo=None,storage=None):
        self.repo = repo or Repository()
        self.storage = storage or Storage()

    def checkpoint(self,job,**changes):
        self.repo.update_job(job,state={**job["state"],**changes})

    def invoke(self,job,service,path,payload,key):
        responses = job["state"].get("responses",{})
        if key in responses:
            return responses[key]
        if job["state"].get("inflight") == key:
            # A synchronous model call cannot be safely replayed after a crash:
            # its response may have been lost, but the GPU may already have run.
            raise RuntimeError("Worker interrupted during a model call. Retry to create a new job.")
        self.checkpoint(job,inflight=key)
        url = job["endpoints"].get(service)
        if not url:
            raise RuntimeError(f"{service} service is not configured")
        try:
            response = requests.post(url+path,json=payload,timeout=(15,600))
            response.raise_for_status()
            data = response.json()
            if data.get("error"):
                raise RuntimeError(str(data["error"])[:500])
        except requests.RequestException:
            raise RuntimeError(f"{service} request failed. Check service availability and retry.") from None
        self.checkpoint(job,inflight=None,responses={**responses,key:data})
        return data

    def async_model(self,job,service,payload):
        handle = job["state"].get("call_id")
        if not handle:
            route = "/convert/start" if service == "threed" else "/generate/start"
            data = self.invoke(job,service,route,payload,"start")
            handle = data.get("call_id")
            if not handle:
                raise RuntimeError("Model service returned no job ID")
            self.checkpoint(job,call_id=handle,call_started=time.time())
        max_wait = 55*60 if service == "threed" else 10*60
        route = "/convert/result/" if service == "threed" else "/generate/result/"
        while time.time() - job["state"]["call_started"] < max_wait:
            response = requests.get(job["endpoints"][service]+route+handle,timeout=(10,90))
            if response.status_code == 202:
                time.sleep(3)
                continue
            response.raise_for_status()
            data = response.json()
            if data.get("error"):
                raise RuntimeError(str(data["error"])[:500])
            return data
        raise RuntimeError("Model generation timed out. Retry from history.")

    def run(self,job):
        kind = job["kind"]
        if kind=="enhance":
            self.repo.update_job(job,stage="enhancing")
            p=job["payload"]
            data=self.invoke(job,"prompt","/enhance",{"raw_prompt":p["prompt"],"speed_mode":p["speed_mode"],
                **p.get("enhancement_context",{})},"enhance")
            payload=data.get("enhanced_prompt_json") or {}
            final_prompt=payload.get("final_prompt") or data.get("enhanced_prompt")
            if not isinstance(final_prompt,str) or not final_prompt.strip():
                raise RuntimeError("Prompt service returned no enhanced instruction")
            if not self.repo.heartbeat(job):
                raise RuntimeError("Job lease lost before saving enhancement")
            chat_id=p.get("chat_id") or str(job["id"])
            self.repo.append_chat_event(str(job["user_id"]),chat_id,str(job["id"])+":enhancement","enhancement",
                {"prompt":final_prompt,"payload":payload,"originalPrompt":p.get("raw_prompt") or p["prompt"],
                 "mode":p["mode"],"speedMode":p["speed_mode"],"jobId":str(job["id"])})
            return {"chat_id":chat_id,"enhancement":data}
        self.repo.update_job(job,stage="converting" if kind=="threed" else "analyzing" if kind=="analysis" else "labeling" if kind=="labels" else "generating")
        if kind in {"labels","threed","analysis"}:
            return self.process_source(job)
        return self.generate(job)

    def generate(self,job):
        p = job["payload"]
        anatomy = p.get("anatomy") or {"is_anatomy":False}
        payload = p.get("enhanced_payload")
        final_prompt = p["prompt"]
        evaluation = None
        warning = None
        retries = 0
        if job["kind"] == "sketch":
            output = self.async_model(job,"sketch",p["sketch"])
            image = output.get("image_base64")
            final_prompt = output.get("prompt") or final_prompt
            metadata = output.get("generation_metadata")
        else:
            best = None
            feedback = p.get("feedback")
            attempts = 3 if p["mode"] == "anatomy" else 1
            for attempt in range(attempts):
                self.repo.update_job(job,stage="generating" if attempt==0 else f"retrying ({attempt}/2)")
                try:
                    output = self.invoke(job,"image","/generate",{
                        "prompt":final_prompt,"enhanced_prompt_json":payload,"domain":"anatomy" if anatomy.get("is_anatomy") else "generic",
                        "organ":anatomy.get("organ"),"view":anatomy.get("view"),"speed_mode":p["speed_mode"],
                        "regeneration_feedback":feedback},f"image-{attempt}")
                except Exception:
                    if best is None:
                        raise
                    image,evaluation,metadata = best
                    warning = "Quality retry unavailable; showing the best completed image."
                    break
                image = output.get("base_image_base64") or output.get("image_base64")
                if not image:
                    raise RuntimeError("Model returned no image")
                metadata = output.get("generation_metadata")
                if attempts == 1:
                    break
                self.repo.update_job(job,stage="evaluating")
                try:
                    evaluated = self.invoke(job,"evaluation","/evaluate",{
                        "image_base64":image,"enhanced_prompt":final_prompt,"raw_prompt":p.get("raw_prompt") or final_prompt,
                        "anatomy_spec":anatomy,"enable_anatomy_critic":bool(anatomy.get("is_anatomy"))},f"evaluation-{attempt}")
                    evaluation = evaluation_result(evaluated)
                except Exception:
                    warning = "Quality evaluation unavailable; generated image preserved."
                    # An evaluator failure should not discard a valid image.
                    break
                if best is None or quality_rank(evaluation)>quality_rank(best[1]):
                    best = (image,evaluation,metadata)
                retries = attempt
                if evaluation["visualScore"]>=7 and evaluation["pedagogicalScore"]>=7 and not evaluation["anatomyHardFailures"]:
                    break
                feedback = ("Improve clarity and factual accuracy. "+evaluation["feedback"]+". Correct: "+"; ".join(evaluation["anatomyHardFailures"]))[:2000]
                if attempt == 2:
                    image,evaluation,metadata = best
                    warning = "Quality threshold not reached; showing the best of three attempts."
        if not image:
            raise RuntimeError("Model returned no image")
        generation_id = str(job["id"])
        image_path = self.storage.upload(f"{job['user_id']}/{generation_id}/image.png",image,"image/png")
        thumbnail_path = self.storage.upload_thumbnail(f"{job['user_id']}/{generation_id}/thumbnail.png",image)
        record = {"prompt":p.get("raw_prompt") or p["prompt"],"enhancedPrompt":final_prompt,
            "mode":p["mode"],"speedMode":p["speed_mode"],"chatId":p.get("chat_id") or generation_id,
            "anatomy":anatomy,"evaluation":evaluation,"evaluationRetries":retries,"evaluationWarning":warning,
            "enhancedPayload":payload,"anatomyAnnotations":[],"interactions":[],"modelEndpoints":job["endpoints"],
            "generationMetadata":metadata}
        if job["kind"] == "sketch":
            record.update(sketchStrokes=p["sketch"]["strokes"],sketchMetadata=metadata,
                sketchStrength=p["sketch"]["control_strength"])
        if not self.repo.heartbeat(job):
            raise RuntimeError("Worker lease lost")
        self.repo.save_history(str(job["user_id"]),generation_id,record,image_path,thumbnail_path=thumbnail_path)
        self.repo.append_chat_event(str(job["user_id"]),record["chatId"],generation_id+":image","image",
            {"mode":p["mode"],"prompt":record["prompt"],"enhancedPrompt":final_prompt,
             "jobId":generation_id,"generationMetadata":metadata},generation_id)
        self.repo.update_job(job,generation_id=generation_id)
        label_job_id = None
        if p.get("auto_label",True) and (job["kind"]=="sketch" or anatomy.get("is_anatomy")):
            try:
                followup = {**p,"kind":"labels","generation_id":generation_id,
                    "request_id":str(uuid5(NAMESPACE_URL,generation_id+":labels"))}
                child = self.repo.create_job(str(job["user_id"]),followup,job["endpoints"])
                label_job_id = str(child["id"])
            except Exception:
                self.repo.patch_history(str(job["user_id"]),generation_id,{"labelingError":"Automatic labeling could not be queued. Use Label image to retry."})
        return {"history_id":generation_id,"label_job_id":label_job_id}

    def process_source(self,job):
        p = job["payload"]
        source = self.repo.get_history(str(job["user_id"]),str(p["generation_id"]))
        if not source:
            raise RuntimeError("Source image no longer exists")
        image = self.storage.download(source["image_path"])
        if job["kind"] == "analysis":
            a=p["analysis"]
            data=self.invoke(job,"interactive","/analyze",
                {"image_base64":image,"speed_mode":p["speed_mode"],
                 **{key:value for key,value in a.items() if key!="id"}},"analysis")
            answer=data.get("response_text")
            if not isinstance(answer,str) or not answer.strip():
                raise RuntimeError("Analysis returned no answer")
            if not self.repo.heartbeat(job):
                raise RuntimeError("Worker lease lost")
            self.repo.append_interaction(str(job["user_id"]),str(p["generation_id"]),
                {"id":a["id"],"mode":a["mode"],"question":a.get("question") or
                    ("Identify selected object" if a["mode"]=="identify" else "Explain selected region"),
                 "answer":answer,"selection":a["interaction"],"structureId":a.get("structure_id"),
                 "status":"completed","jobId":str(job["id"])})
            return {"history_id":str(p["generation_id"]),"interaction_id":a["id"]}
        if job["kind"] == "labels":
            anatomy = source["metadata"].get("anatomy") or {}
            data = self.invoke(job,"interactive","/auto-labels",{
                "image_base64":image,"domain":"anatomy" if anatomy.get("is_anatomy") else "generic",
                "organ":anatomy.get("organ") or "subject","view":anatomy.get("view_description") or anatomy.get("view") or "",
                "speed_mode":p["speed_mode"]},"labels")
            from studio.schemas import Annotation
            labels = [Annotation.model_validate(item).model_dump() for item in data.get("annotations",[])]
            if not self.repo.heartbeat(job):
                raise RuntimeError("Worker lease lost")
            self.repo.save_auto_labels(str(job["user_id"]),str(p["generation_id"]),labels)
        else:
            data = self.async_model(job,"threed",{"image_base64":image,"speed_mode":p["speed_mode"],"request_id":str(job["id"]),"texture":True,"num_inference_steps":30})
            glb = data.get("glb_base64")
            if not glb:
                raise RuntimeError("3D model returned no GLB")
            path = self.storage.upload(f"{job['user_id']}/{p['generation_id']}/{job['id']}.glb",glb,"model/gltf-binary")
            if not self.repo.heartbeat(job):
                raise RuntimeError("Worker lease lost")
            self.repo.patch_history(str(job["user_id"]),str(p["generation_id"]),{
                "glbSizeKb":data.get("size_kb") or data.get("glb_size_kb"),
                "threeDJob":{"status":"done","requestId":str(job["id"]),"callId":job["state"].get("call_id")}},glb_path=path)
        if job["kind"]=="threed":
            self.repo.append_chat_event(str(job["user_id"]),source["metadata"].get("chatId") or str(source["id"]),
                str(job["id"])+":threed","threed",{"jobId":str(job["id"]),"prompt":source["metadata"].get("prompt"),
                    "input":"generated 2D image","speedMode":p["speed_mode"],"texture":True,"steps":30,
                    "modelEndpoint":job["endpoints"].get("threed"),"glbPath":path},str(source["id"]))
        return {"history_id":str(p["generation_id"])}
