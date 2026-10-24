import tempfile
import unittest
from pathlib import Path
from video_export import write_ass, caption_lines
from PIL import ImageFont


class CaptionTests(unittest.TestCase):
    font=Path('C:/Windows/Fonts/msyh.ttc')

    def test_bilingual_wrap_and_tag_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'captions.ass'
            write_ass(p,[dict(start=0,end=3,text='Hello {world} \\pos(0,0)',translation='你好，世界。')],3,self.font)
            s=p.read_text(encoding='utf-8-sig')
            self.assertIn('｛world｝',s); self.assertNotIn('\\pos(0,0)',s)
            self.assertIn('你好',s); self.assertIn('0:00:03.00',s)

    def test_reject_empty_and_invalid_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'captions.ass'
            for cues in ([],[dict(start=3,end=1,text='bad')],[dict(start=float('nan'),end=2,text='bad')]):
                with self.assertRaises(ValueError):write_ass(p,cues,5,self.font)

    def test_long_tokens_remain_within_width(self):
        f=ImageFont.truetype(str(self.font),40)
        text='Hello ' + 'A'*180+' 中文字幕测试。'
        lines=caption_lines(text,f,400)
        self.assertTrue(all(f.getlength(line)<=400 for line in lines))
        self.assertEqual(''.join(lines).replace(' ',''),text.replace(' ',''))
