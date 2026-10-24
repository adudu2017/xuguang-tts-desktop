import tempfile
import unittest
from qwen_runtime import attention_mode


class RuntimeTests(unittest.TestCase):
    def test_new_task_defaults_on_and_resumes_same_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            r=dict(output=folder, config={}, skip=[])
            self.assertTrue(attention_mode(r))
            r['skip']=['0']
            self.assertTrue(attention_mode(r))
            r['config']['qwen_expanded_kv']=False
            with self.assertRaises(ValueError):attention_mode(r)

    def test_legacy_resume_preserves_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            r=dict(output=folder, config={}, skip=['0'])
            self.assertFalse(attention_mode(r))
            r['config']['qwen_expanded_kv']=True
            with self.assertRaises(ValueError):attention_mode(r)

    def test_explicit_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(attention_mode(dict(output=folder,config={'qwen_expanded_kv':False},skip=[])))
