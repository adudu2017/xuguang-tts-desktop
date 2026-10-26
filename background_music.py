"""Fixed local music library and voice-first mixing."""
from pathlib import Path

TRACKS = {'关闭背景音乐': None, '背景音乐 1': '1989154383.mp3'}

def music_path(base, choice):
    if choice == '背景音乐 1 · 1989154383': choice = '背景音乐 1'
    if choice not in TRACKS: raise ValueError('请选择内置背景音乐')
    name = TRACKS[choice]
    if name is None: return None
    path = Path(base) / 'assets' / 'music' / name
    if not path.is_file(): raise FileNotFoundError('这首背景音乐尚未安装，请选择其他音乐或关闭背景音乐。')
    return path

MUSIC_INTRO_SECONDS = 2.0

def shift_cues(cues, seconds):
    return [dict(c, start=c['start']+seconds, end=c['end']+seconds) for c in cues]

def mix_filter(duration, voice='1:a', music='2:a', intro_seconds=MUSIC_INTRO_SECONDS):
    # duration includes the intro; delay voice and its sidechain equally.
    if duration <= 0: raise ValueError('音频时长必须大于零')
    if intro_seconds < 0: raise ValueError("Invalid intro duration")
    delay = round(intro_seconds * 1000)
    fade = min(2., duration / 2)
    return (f'[{voice}]loudnorm=I=-21:TP=-2:LRA=11,aresample=48000,adelay={delay}:all=1,asplit=2[voice][side];'
            f'[{music}]loudnorm=I=-26:TP=-8:LRA=7,aresample=48000,atrim=duration={duration:.6f},'
            f'afade=t=in:d={fade:.6f},afade=t=out:st={duration-fade:.6f}:d={fade:.6f}[music];'
            '[music][side]sidechaincompress=threshold=0.04:ratio=2:attack=20:release=400[ducked];'
            '[voice][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.891:level=false:latency=true[mixed]')
