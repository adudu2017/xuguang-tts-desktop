"""Explicit model download, separate from offline inference."""
import sys
from pathlib import Path
from modelscope import snapshot_download

name, root = sys.argv[1], Path(sys.argv[2])
if name == 'Qwen':
    snapshot_download('Qwen/Qwen3-TTS-12Hz-0.6B-Base', local_dir=str(root / 'Qwen3-TTS-12Hz-0.6B-Base'))
else:
    snapshot_download('inclusionAI/Ming-3.0-tts-0.5b', local_dir=str(root / 'Ming-3.0-tts-0.5b'))
