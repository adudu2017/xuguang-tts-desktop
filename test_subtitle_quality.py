import unittest
from subtitle_quality import detect_language, validate_language, translation_error, validate_cues

class SubtitleQualityTests(unittest.TestCase):
    def test_mismatch_is_rejected(self):
        with self.assertRaises(ValueError): validate_language('今天的天气很好，阳光透过窗户。', 'English')
        with self.assertRaises(ValueError): validate_language('The rabbit found a seed in the forest.', 'Chinese')
    def test_short_and_mixed_text_not_forced(self):
        self.assertIsNone(detect_language('Hi!'))
        validate_language('今天 Alice 来了。', 'Chinese')
    def test_bad_translation_rejected(self):
        for text in (','*450, 'Hello' + ','*40, 'go '*20, ''):
            self.assertIsNotNone(translation_error(text))
        with self.assertRaises(ValueError): validate_cues([dict(text='今天的天气很好', translation=','*450)])
    def test_valid_both_directions_and_original_only(self):
        self.assertIsNone(translation_error('The weather is nice today.', 'Chinese'))
        self.assertIsNone(translation_error('今天天气很好。', 'English'))
        validate_cues([dict(text='你好')])
    def test_wrong_target_language(self):
        self.assertIsNotNone(translation_error('今天天气很好', 'Chinese'))
        self.assertIsNotNone(translation_error('Hello there', 'English'))
