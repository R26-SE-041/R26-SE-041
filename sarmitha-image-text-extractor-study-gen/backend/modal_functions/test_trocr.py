import modal
import base64

app = modal.App.lookup("sinhala-trocr-ocr-service")

@modal.local_entrypoint()
def main():
    Cls = modal.Cls.lookup("sinhala-trocr-ocr-service", "SinhalaTrOCRExtractor")
    inst = Cls()
    # 1x1 black image
    b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    try:
        res = inst.extract_text.remote({"image_b64": b64})
        print("Success:", res)
    except Exception as e:
        print("Error:", repr(e))
