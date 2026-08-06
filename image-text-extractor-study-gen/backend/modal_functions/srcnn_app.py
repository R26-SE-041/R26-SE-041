"""
SRCNN Super-Resolution — Modal Serverless Function

Workflow:
  1. Receive low-quality image bytes via POST
  2. Convert to YCbCr, extract Y channel
  3. Bicubic upscale (4x) → SRCNN forward pass → sharpen
  4. Merge back Cb/Cr channels and return enhanced PNG bytes

Deploy:
  modal deploy modal_functions/srcnn_app.py
"""

import io
import modal

# ---------------------------------------------------------------------------
# Container image — all heavy deps baked in at build time
# ---------------------------------------------------------------------------
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.3.1",
        "torchvision==0.18.1",
        "pillow==10.3.0",
        "numpy==1.26.4",
        "requests==2.32.3",
        "scipy==1.13.1",
        "fastapi[standard]",
    )
    .run_commands(
        # Download pretrained SRCNN x4 weights at build time so cold starts are fast.
        # Using requests so GitHub's redirect (302 → raw content) is followed correctly.
        "mkdir -p /weights && "
        "python -c \""
        "import requests; "
        "r = requests.get("
        "  'https://www.dropbox.com/s/pd5b2ketm0oamhj/srcnn_x4.pth?dl=1',"
        "  allow_redirects=True"
        "); "
        "open('/weights/srcnn_x4.pth', 'wb').write(r.content); "
        "print('SRCNN weights downloaded, size:', len(r.content), 'bytes')"
        "\""
    )
)

app = modal.App("srcnn-super-resolution", image=image)

SCALE_FACTOR = 4
WEIGHTS_PATH = "/weights/srcnn_x4.pth"


# ---------------------------------------------------------------------------
# SRCNN architecture (matches yjn870/SRCNN-pytorch)
# ---------------------------------------------------------------------------
def _build_srcnn():
    import torch.nn as nn

    class SRCNN(nn.Module):
        def __init__(self, num_channels: int = 1):
            super().__init__()
            self.conv1 = nn.Conv2d(num_channels, 64, kernel_size=9, padding=9 // 2)
            self.conv2 = nn.Conv2d(64, 32, kernel_size=5, padding=5 // 2)
            self.conv3 = nn.Conv2d(32, num_channels, kernel_size=5, padding=5 // 2)
            self.relu = nn.ReLU(inplace=True)

        def forward(self, x):
            x = self.relu(self.conv1(x))
            x = self.relu(self.conv2(x))
            return self.conv3(x)

    return SRCNN


# ---------------------------------------------------------------------------
# Modal class — model loaded once per container via @modal.enter
# ---------------------------------------------------------------------------
@app.cls(gpu="T4", scaledown_window=60)
class SRCNNEnhancer:
    @modal.enter()
    def load_model(self):
        import torch

        SRCNN = _build_srcnn()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = SRCNN(num_channels=1).to(self.device)

        # weights_only=False needed for older .pth files that include non-tensor objects
        state = torch.load(WEIGHTS_PATH, map_location=self.device, weights_only=False)
        self.model.load_state_dict(state)
        self.model.eval()
        print(f"[SRCNN] Model loaded on {self.device}")

    @modal.fastapi_endpoint(method="POST")
    def enhance(self, request: dict) -> dict:
        """
        Accepts JSON: {"image_b64": "<base64-encoded image>"}
        Returns JSON: {"enhanced_b64": "<base64-encoded PNG>"}
        """
        import base64
        import numpy as np
        import torch
        from PIL import Image
        from scipy.ndimage import gaussian_filter

        # Decode input
        image_bytes = base64.b64decode(request["image_b64"])
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # --- Pre-process: RGB → YCbCr, work on Y channel only ---
        img_ycbcr = img.convert("YCbCr")
        y, cb, cr = img_ycbcr.split()

        # Bicubic upscale
        new_w = img.width * SCALE_FACTOR
        new_h = img.height * SCALE_FACTOR
        y_up = y.resize((new_w, new_h), Image.BICUBIC)
        cb_up = cb.resize((new_w, new_h), Image.BICUBIC)
        cr_up = cr.resize((new_w, new_h), Image.BICUBIC)

        # Normalise Y to [0, 1] tensor
        y_arr = np.array(y_up, dtype=np.float32) / 255.0
        y_tensor = (
            torch.from_numpy(y_arr)
            .unsqueeze(0)
            .unsqueeze(0)
            .to(self.device)
        )

        # --- SRCNN inference ---
        with torch.no_grad():
            y_out = self.model(y_tensor)

        # Clamp and convert back to uint8
        y_out_arr = y_out.squeeze().cpu().numpy()
        y_out_arr = np.clip(y_out_arr, 0.0, 1.0)

        # Slight unsharp mask for crisp edges
        blurred = gaussian_filter(y_out_arr, sigma=0.5)
        y_sharp = y_out_arr + 0.3 * (y_out_arr - blurred)
        y_sharp = np.clip(y_sharp, 0.0, 1.0)

        y_enhanced = Image.fromarray((y_sharp * 255).astype(np.uint8))

        # Merge enhanced Y back with Cb, Cr
        enhanced_ycbcr = Image.merge("YCbCr", [y_enhanced, cb_up, cr_up])
        enhanced_rgb = enhanced_ycbcr.convert("RGB")

        # Encode to PNG bytes → base64
        buf = io.BytesIO()
        enhanced_rgb.save(buf, format="PNG", optimize=False)
        enhanced_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return {"enhanced_b64": enhanced_b64}
