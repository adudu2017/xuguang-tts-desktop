import unittest,re
from unittest.mock import patch
from qwen_quality import split_sentences,prepare_segments,GenerationGuard
class QualityTests(unittest.TestCase):
 def test_boundaries(self):
  self.assertEqual(split_sentences('Dr. Smith has 3.14 apples. “Hello!” Next.'),['Dr. Smith has 3.14 apples.','“Hello!”','Next.'])
 def test_preserve_words(self):
  text='One small rabbit found a seed. She planted it. '*20
  self.assertEqual(re.sub(r'\s','',text),re.sub(r'\s','',''.join(prepare_segments(text,12))))
  self.assertTrue(all(p.endswith('.') for p in prepare_segments(text,12)))
 def test_markdown(self):self.assertEqual(prepare_segments('# Title\n---\n**Hello.**'),['Title Hello.'])
 def test_chinese(self):self.assertGreater(len(prepare_segments('小兔子在森林里散步。'*20)),1)
 def test_guard_failure(self):
  g=GenerationGuard('Hello',max_frames=2);self.assertFalse(g(None,None))
  with self.assertRaisesRegex(RuntimeError,'QWEN_GENERATION_GUARD'):g(None,None)
 def test_timeout(self):
  g=GenerationGuard('Hello',timeout=1);g.started-=2
  with self.assertRaisesRegex(RuntimeError,'QWEN_GENERATION_GUARD'):g(None,None)
if __name__=='__main__':unittest.main()
