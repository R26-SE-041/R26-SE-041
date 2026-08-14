import modal

app = modal.App("test-processor3")
image = modal.Image.debian_slim().pip_install("transformers", "pillow", "numpy", "torch", "torchvision", "opencv-python-headless")

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

    cv_img_rgb = np.array(img_processed)
    cv_img_gray = cv2.cvtColor(cv_img_rgb, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(cv_img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    img_h, img_w = cv_img_rgb.shape[:2]
    kernel_width = max(40, img_w // 25)
    kernel_height = max(5, img_h // 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, kernel_height))
    dilated = cv2.dilate(thresh, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    lines = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > max(30, img_w * 0.05) and h > max(20, img_h * 0.02):
            padding = max(10, int(h * 0.15))
            y1 = max(0, y - padding)
            y2 = min(img_h, y + h + padding)
            line_crop = cv_img_rgb[y1:y2, x:x+w]
            lines.append(Image.fromarray(line_crop))

    if len(lines) == 0:
        lines = [img_processed]

    res = feature_extractor(images=lines, return_tensors='pt')
    print("Pixel values shape:", res.pixel_values.shape)

@app.local_entrypoint()
def main():
    test_processor.remote()
