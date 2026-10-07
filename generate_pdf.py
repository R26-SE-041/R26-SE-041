import os
import subprocess
import time
from pathlib import Path

HERE = Path(r"c:\Users\Koji\Desktop\pro\R26-SE-041")
HTML_PATH = HERE / "research_paper.html"
PDF_PATH = HERE / "research_paper.pdf"

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(edge_path):
    edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

file_uri = HTML_PATH.as_uri()

cmd = [
    edge_path,
    "--headless",
    "--disable-gpu",
    "--run-all-compositor-stages-before-draw",
    f"--print-to-pdf={PDF_PATH}",
    "--no-pdf-header-footer",
    "--virtual-time-budget=6000",
    file_uri,
]

print(f"Converting HTML to PDF via Edge: {cmd}")
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
print("Edge return code:", proc.returncode)

if PDF_PATH.exists():
    size = PDF_PATH.stat().st_size
    print(f"SUCCESS: Generated PDF at {PDF_PATH} (size: {size} bytes)")
else:
    print("FAILED to generate PDF")
