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
 def test_sentence_recovery_and_cues(self):
  import numpy as np
  from qwen_quality import generate_with_recovery
  calls=[]
  def synth(text):
   calls.append(text)
   if len(calls)==1:raise RuntimeError('QWEN_GENERATION_GUARD: timeout')
   return np.ones(100),100
  audio,rate,cues=generate_with_recovery('Hello. Next.',synth)
  self.assertEqual(calls,['Hello. Next.','Hello.','Next.'])
  self.assertEqual(len(audio),200)
  self.assertEqual(cues[1]['start'],1)
 def test_retry_failure_propagates_without_partial_result(self):
  from qwen_quality import generate_with_recovery
  calls=[]
  def synth(text):
   calls.append(text)
   raise RuntimeError('QWEN_GENERATION_GUARD: timeout')
  with self.assertRaises(RuntimeError):generate_with_recovery('Hello. Next.',synth)
  self.assertEqual(len(calls),2)
 def test_other_errors_not_retried(self):
  from qwen_quality import generate_with_recovery
  def synth(text):raise RuntimeError('CUDA error')
  with self.assertRaisesRegex(RuntimeError,'CUDA error'):generate_with_recovery('Hello. Next.',synth)
 def test_risky_short_cluster_isolated_without_text_loss(self):
  text='她慢慢走进安静的房间。咚。咚。咚。门外传来了一个熟悉的声音。'
  segments=prepare_segments(text)
  self.assertEqual(sum(p=='咚。' for p in segments),3)
  self.assertEqual(''.join(segments),text)
 def test_normal_sentences_still_pack(self):
  self.assertEqual(len(prepare_segments('The little rabbit found a seed. She planted it in her garden.')),1)
if __name__=='__main__':unittest.main()
