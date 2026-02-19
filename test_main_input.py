import unittest

from src.main import _read_topic_input


class _StubReader:
    def __init__(self, lines):
        self._lines = list(lines)
        self._idx = 0

    def __call__(self, prompt=""):
        if self._idx >= len(self._lines):
            return ""
        value = self._lines[self._idx]
        self._idx += 1
        return value


class MainInputComposerTests(unittest.TestCase):
    def test_single_line_message_submits_on_double_blank(self):
        reader = _StubReader(["hello feasibility check", "", ""])
        value = _read_topic_input(read_line=reader, print_line=lambda _: None)
        self.assertEqual(value, "hello feasibility check")

    def test_multiline_message_is_preserved(self):
        reader = _StubReader(
            [
                "Project brief line one",
                "",
                "Project brief line two",
                "",
                "",
            ]
        )
        value = _read_topic_input(read_line=reader, print_line=lambda _: None)
        self.assertIn("Project brief line one", value)
        self.assertIn("Project brief line two", value)
        self.assertIn("\n\n", value)

    def test_paste_mode_collects_until_end_marker(self):
        reader = _StubReader(
            [
                ":paste",
                "Line A",
                "Line B",
                ":end",
            ]
        )
        value = _read_topic_input(read_line=reader, print_line=lambda _: None)
        self.assertEqual(value, "Line A\nLine B")


if __name__ == "__main__":
    unittest.main()
