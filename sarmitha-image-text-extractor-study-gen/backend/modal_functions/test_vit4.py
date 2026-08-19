import modal

app = modal.App("test-processor4")
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
    
    img1 = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
    img2 = Image.fromarray(np.zeros((50, 150, 3), dtype=np.uint8))
    lines = [img1, img2]

    res = feature_extractor(images=lines, return_tensors='pt')
    print("Pixel values shape:", res.pixel_values.shape)

@app.local_entrypoint()
def main():
    test_processor.remote()
