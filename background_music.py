"""Fixed local music library and voice-first mixing."""
from pathlib import Path

TRACKS = {'关闭背景音乐': None, '背景音乐 1 · 1989154383': '1989154383.mp3', '背景音乐 2 · 2150746620': '2150746620.mp3'}

def music_path(base, choice):
    if choice not in TRACKS: raise ValueError('请选择内置背景音乐')
    name = TRACKS[choice]
    if name is None: return None
    path = Path(base) / 'assets' / 'music' / name
    if not path.is_file(): raise FileNotFoundError('这首背景音乐尚未安装，请选择其他音乐或关闭背景音乐。')
    return path

def mix_filter(duration, voice='1:a', music='2:a'):
    # Normalize each source independently; music stays 12 LU below speech,
    # then duck it further while speech is present. Limit final peaks.
    if duration <= 0: raise ValueError('音频时长必须大于零')
    fade = min(2., duration / 2)
    return (f'[{voice}]loudnorm=I=-18:TP=-2:LRA=11,aresample=48000,asplit=2[voice][side];'
            f'[{music}]loudnorm=I=-30:TP=-8:LRA=7,aresample=48000,atrim=duration={duration:.6f},'
            f'afade=t=in:d={fade:.6f},afade=t=out:st={duration-fade:.6f}:d={fade:.6f}[music];'
            '[music][side]sidechaincompress=threshold=0.025:ratio=6:attack=20:release=400[ducked];'
            '[voice][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.891:level=false:latency=true[mixed]')
