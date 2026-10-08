"""Deploy API and worker at the checked commit and wait for Render results."""
import os
import time
import requests
BASE="https://api.render.com/v1"
HEADERS={"Authorization":"Bearer "+os.environ["RENDER_API_KEY"],"Content-Type":"application/json"}

def deploy(service_id):
    response=requests.post(BASE+"/services/"+service_id+"/deploys",headers=HEADERS,
        json={"clearCache":"do_not_clear","commitId":os.environ["GITHUB_SHA"]},timeout=30)
    response.raise_for_status()
    deploy_id=response.json()["id"]
    deadline=time.monotonic()+1200
    while time.monotonic()<deadline:
        response=requests.get(BASE+"/services/"+service_id+"/deploys/"+deploy_id,headers=HEADERS,timeout=30)
        response.raise_for_status()
        status=response.json()["status"]
        print("Render deployment:",status,flush=True)
        if status=="live":
            return
        if status in {"build_failed","update_failed","canceled","deactivated"}:
            raise SystemExit("Render deployment failed: "+status)
        time.sleep(10)
    raise SystemExit("Render deployment exceeded 20 minutes")

if __name__=="__main__":
    # Deploy sequentially: durable queue keeps jobs safe while worker restarts.
    deploy(os.environ["RENDER_API_SERVICE_ID"])
    deploy(os.environ["RENDER_WORKER_SERVICE_ID"])
