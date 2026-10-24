"""Pin the attention mode across resumed jobs, including pre-optimization jobs."""
import json
from pathlib import Path


def attention_mode(request):
    path = Path(request['output']) / 'qwen_runtime.json'
    configured = request['config'].get('qwen_expanded_kv')
    if request.get('skip'):
        previous = json.loads(path.read_text(encoding='utf-8'))['expanded_kv'] if path.exists() else False
        if configured is not None and bool(configured) != previous:
            raise ValueError('Qwen 注意力设置已改变，请新建任务，避免混合不同推理方式的音频。')
        enabled = previous
    else:
        enabled = True if configured is None else bool(configured)
    path.write_text(json.dumps({'expanded_kv': enabled}), encoding='utf-8')
    return enabled
