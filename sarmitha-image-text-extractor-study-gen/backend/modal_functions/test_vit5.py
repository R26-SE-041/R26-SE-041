import modal

app = modal.App("test-processor5")
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

    feature_extractor = ViTImageProcessor(
        do_normalize=True,
        do_rescale=True,
        do_resize=True,
        image_mean=[0.5, 0.5, 0.5],
        image_std=[0.5, 0.5, 0.5],
        resample=2,
        rescale_factor=0.00392156862745098,
        size={"height": 384, "width": 384}
    )
    
    b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    image_bytes = base64.b64decode(b64)
    nparr = np.frombuffer(image_bytes, np.uint8)
    cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    cl = clahe.apply(gray)
    denoised = cv2.fastNlMeansDenoising(cl, None, h=15, templateWindowSize=7, searchWindowSize=21)
    gaussian = cv2.GaussianBlur(denoised, (0, 0), 2.0)
    sharpened = cv2.addWeighted(denoised, 1.5, gaussian, -0.5, 0)
    img_rgb = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
    img_processed = Image.fromarray(img_rgb)
    lines = [img_processed]

    print("Image mode:", img_processed.mode)
    res = feature_extractor(images=lines, return_tensors='pt', input_data_format='channels_last')
    print("Pixel values shape:", res.pixel_values.shape)

@app.local_entrypoint()
def main():
    test_processor.remote()
