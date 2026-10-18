"""Download the official multilingual checkpoint into this application's cache."""
import os
from pathlib import Path

os.environ.setdefault("HF_HOME", str(Path(__file__).parent / "models"))
from huggingface_hub import snapshot_download

if __name__ == "__main__":
    path = snapshot_download("convaiinnovations/laya", allow_patterns=["multilingual/*"])
    (Path(__file__).parent / "model_revision.txt").write_text(Path(path).name, encoding="utf-8")
    print(path)
