"""Make one small request to the DEPLOYED GPU before a demonstration.

Explicit opt-in: python -m scripts.warm_modal
This consumes Modal credits. It has no polling loop or repeated keep-alive calls.
"""
import argparse
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=120, help="Cold-start wait budget in seconds")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    from app.services import llm_service

    # Only this explicit warm-up can wait for a cold start; learner-facing
    # question generation retains its existing shared 15-second budget.
    llm_service.MODAL_REQUEST_TIMEOUT_SEC = args.timeout
    started = time.perf_counter()
    try:
        result = llm_service.QwenModalService(generation_budget_sec=args.timeout).call_json(
            'Return exactly this JSON object: {"ready":true}', max_new_tokens=64
        )
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"Warm-up failed: {exc}\n")
    if result.get("ready") is not True:
        parser.exit(1, "Endpoint responded, but the warm-up JSON was unexpected.\n")
    print(f"Deployed GPU responded in {time.perf_counter() - started:.1f}s.")
    print("Start the demo now; the GPU may scale down again after the idle window.")


if __name__ == "__main__":
    main()
