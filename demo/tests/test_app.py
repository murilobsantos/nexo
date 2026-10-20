import unittest
from app import media


class MediaTests(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(media([]))

    def test_pair(self):
        self.assertEqual(media([2, 4]), 3)
