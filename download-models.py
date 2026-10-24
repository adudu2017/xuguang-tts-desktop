"""Download model weights from ModelScope; never silently fall back to HF."""
import argparse
from pathlib import Path

MODELS = {
    'Qwen': ('Qwen/Qwen3-TTS-12Hz-0.6B-Base', 'Qwen3-TTS-12Hz-0.6B-Base'),
    'Ming': ('inclusionAI/Ming-3.0-tts-0.5b', 'Ming-3.0-tts-0.5b'),
    'Translation': ('Helsinki-NLP/opus-mt-en-zh', 'opus-mt-en-zh'),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', choices=[*MODELS, 'All'])
    parser.add_argument('root', nargs='?', default=str(Path(__file__).resolve().parent / 'models'))
    parser.add_argument('--list', action='store_true', help='Print URLs and destinations without downloading')
    args = parser.parse_args()
    for name in MODELS if args.model == 'All' else [args.model]:
        model_id, folder = MODELS[name]
        target = Path(args.root).resolve() / folder
        print(f'{name}: https://modelscope.cn/models/{model_id} -> {target}', flush=True)
        if not args.list:
            from modelscope import snapshot_download
            kwargs = dict(model_id=model_id, local_dir=str(target))
            if name == 'Translation':
                # The client uses PyTorch, not TensorFlow/Flax/Rust weights.
                kwargs['ignore_patterns'] = ['flax_model.msgpack', 'tf_model.h5', 'rust_model.ot']
            snapshot_download(**kwargs)

if __name__ == '__main__':
    main()
