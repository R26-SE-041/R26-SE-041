import modal

app = modal.App("test-processor6")
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch==2.3.1",
    "torchvision==0.18.1",
    "transformers==4.41.2",
    "pillow==10.3.0",
    "opencv-python-headless==4.10.0.84",
)

@app.function(image=image)
def test_processor():
    import base64
    import numpy as np
    import cv2
    from PIL import Image
    from transformers import ViTImageProcessor

    feature_extractor1 = ViTImageProcessor(
        do_normalize=True,
        do_rescale=True,
        do_resize=True,
        image_mean=[0.5, 0.5, 0.5],
        image_std=[0.5, 0.5, 0.5],
        resample=2,
        rescale_factor=0.00392156862745098,
        size={"height": 384, "width": 384}
    )
    
    feature_extractor2 = ViTImageProcessor.from_pretrained("hasindu-k/sinhala-handwritten-notes-v3")

    print("Extractor 1 mean:", feature_extractor1.image_mean)
    print("Extractor 2 mean:", feature_extractor2.image_mean)

@app.local_entrypoint()
def main():
    test_processor.remote()
