"""Local still-background MP4 export with burned-in bilingual captions."""
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import wave
from PIL import Image, ImageOps, ImageFont


class ExportCancelled(Exception):
    pass


def caption_lines(text, font, width=1640):
    # Keep English words whole; allow CJK line breaks. Never interpret ASS tags.
    text = str(text).replace('\\', '＼').replace('{', '｛').replace('}', '｝')
    units = re.findall(r'[\u3400-\u9fff]|[^\s\u3400-\u9fff]+|\s+', text)
    lines, line = [], ''
    for unit in units:
        if font.getlength(line + unit) > width and line.strip():
            lines.append(line.strip()); line = ''
        if font.getlength(unit) > width:
            for char in unit:
                if font.getlength(line + char) > width:
                    lines.append(line.strip()); line = ''
                line += char
        else:
            line += unit
    if line.strip(): lines.append(line.strip())
    return lines


def ass_time(seconds):
    cs = round(seconds * 100)
    seconds, cs = divmod(cs, 100); minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours}:{minutes:02}:{seconds:02}.{cs:02}'


def write_ass(path, cues, duration, font_path):
    from subtitle_quality import validate_cues
    validate_cues(cues)
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,40,&H00FFFFFF,&H00FFFFFF,&H00231321,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,140,140,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []; previous = 0
    for cue in cues:
        start, end = float(cue['start']), min(duration, float(cue['end']))
        if not all(map(math.isfinite, (start, end))) or start < previous - .02 or end <= start:
            raise ValueError('字幕时间轴无效，请重新生成字幕后导出。')
        previous = end
        text = cue.get('text', '').strip(); translation = cue.get('translation', '').strip()
        if not text: continue
        for size in range(40, 19, -2):
            font = ImageFont.truetype(str(font_path), size)
            first = caption_lines(text, font)
            second = caption_lines(translation, font) if translation else []
            if (len(first) + len(second)) * size * 1.45 <= 340: break
        else:
            raise ValueError('一条字幕过长，无法清晰显示；请缩短分段后重试。')
        body = '{\\fs' + str(size) + '}' + '\\N'.join(first)
        if second: body += '\\N{\\c&HBADEF4&}' + '\\N'.join(second)
        events.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{body}')
    if not events: raise ValueError('当前音频没有可用的时间轴字幕，无法导出字幕视频。')
    Path(path).write_text(header + '\n'.join(events) + '\n', encoding='utf-8-sig')


def export_mp4(audio, cues, background, target, base, cancel=None, progress=None):
    cancel = cancel or threading.Event(); progress = progress or (lambda x: None)
    base, audio, target = Path(base), Path(audio).resolve(), Path(target).resolve()
    ffmpeg = base / 'tools/ffmpeg.exe'
    if not ffmpeg.is_file():
        found = shutil.which('ffmpeg')
        if not found: raise FileNotFoundError('未找到 FFmpeg，请检查软件 tools 文件夹。')
        ffmpeg = Path(found)
    font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc'
    if not font_path.exists(): raise FileNotFoundError('未找到微软雅黑字体，无法保证中文字幕显示。')
    if target == audio or target == Path(background).resolve(): raise ValueError('视频不能覆盖源音频或背景图片。')
    with wave.open(str(audio)) as src: duration = src.getnframes() / src.getframerate()
    if duration <= 0: raise ValueError('音频为空。')
    with tempfile.TemporaryDirectory(prefix='voicedesk-video-', dir=target.parent) as tmp:
        folder = Path(tmp)
        with Image.open(background) as src:
            frame = ImageOps.exif_transpose(src).convert('RGBA')
            backdrop = Image.new('RGBA', frame.size, '#211323'); backdrop.alpha_composite(frame)
            backdrop.convert('RGB').save(folder / 'background.png')
        write_ass(folder / 'captions.ass', cues, duration, font_path)
        command = [str(ffmpeg), '-hide_banner', '-nostdin', '-y', '-loop', '1', '-framerate', '24',
            '-i', 'background.png', '-i', str(audio), '-vf',
            'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x211323,setsar=1,drawbox=x=0:y=650:w=iw:h=430:color=black@0.22:t=fill,ass=captions.ass',
            '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'stillimage',
            '-crf', '23', '-threads', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
            '-t', f'{duration:.6f}', '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', 'video.mp4']
        if cancel.is_set(): raise ExportCancelled('已取消导出')
        with open(folder / 'ffmpeg.log', 'w', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=folder, stdout=subprocess.PIPE, stderr=log,
                text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            lines = queue.Queue()
            def read_progress():
                for line in process.stdout: lines.put(line.strip())
            reader = threading.Thread(target=read_progress, daemon=True); reader.start()
            try:
                while process.poll() is None:
                    if cancel.wait(.1): raise ExportCancelled('已取消导出；原有文件未改变。')
                    while not lines.empty():
                        line = lines.get_nowait()
                        if line.startswith('out_time_us='):
                            try: progress(min(.99, max(0, int(line.split('=', 1)[1]) / 1e6 / duration)))
                            except ValueError: pass
                if cancel.is_set(): raise ExportCancelled('已取消导出；原有文件未改变。')
                if process.returncode:
                    raise RuntimeError((folder / 'ffmpeg.log').read_text(encoding='utf-8')[-2200:])
            finally:
                if process.poll() is None: process.kill(); process.wait()
                reader.join(timeout=2); process.stdout.close()
        if not (folder / 'video.mp4').is_file(): raise RuntimeError('未生成视频文件。')
        os.replace(folder / 'video.mp4', target)
        progress(1.0)
    return target
