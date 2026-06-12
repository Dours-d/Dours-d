"""Unit tests for the Hijri-date README updater."""

import json
import os
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

from scripts.update_hijri import (
    API_URL,
    END_TAG,
    START_TAG,
    fetch_hijri_date,
    format_date_string,
    replace_date_in_lines,
    update_readme,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_HIJRI = {
    "day": "15",
    "month": {"en": "Ramadan", "ar": "\u0631\u0645\u0636\u0627\u0646"},
    "year": "1446",
}

SAMPLE_API_RESPONSE = json.dumps({"data": {"hijri": SAMPLE_HIJRI}}).encode()

SAMPLE_README = (
    "# Hello\n"
    " [//]: # (HIJRI_START)\n"
    "### old content\n"
    " [//]: # (HIJRI_END)\n"
    "More text\n"
)

README_NO_TAGS = "# Just a heading\nSome content\n"


# ---------------------------------------------------------------------------
# format_date_string
# ---------------------------------------------------------------------------


class TestFormatDateString(TestCase):
    def test_basic_output_structure(self):
        result = format_date_string(SAMPLE_HIJRI)
        lines = result.split("\n")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("### "))
        self.assertTrue(lines[1].startswith("### "))

    def test_contains_day_month_year(self):
        result = format_date_string(SAMPLE_HIJRI)
        self.assertIn("15", result)
        self.assertIn("Ramadan", result)
        self.assertIn("1446", result)

    def test_contains_arabic_month(self):
        result = format_date_string(SAMPLE_HIJRI)
        self.assertIn("\u0631\u0645\u0636\u0627\u0646", result)

    def test_contains_bismillah(self):
        result = format_date_string(SAMPLE_HIJRI)
        self.assertIn("\ufdfd", result)

    def test_contains_salawat(self):
        result = format_date_string(SAMPLE_HIJRI)
        self.assertIn("\ufdfa", result)

    def test_contains_crescent_moon(self):
        result = format_date_string(SAMPLE_HIJRI)
        self.assertIn("\U0001f319", result)

    def test_different_dates(self):
        hijri = {
            "day": "1",
            "month": {"en": "Muharram", "ar": "\u0645\u062d\u0631\u0645"},
            "year": "1448",
        }
        result = format_date_string(hijri)
        self.assertIn("1", result)
        self.assertIn("Muharram", result)
        self.assertIn("1448", result)
        self.assertIn("\u0645\u062d\u0631\u0645", result)


# ---------------------------------------------------------------------------
# replace_date_in_lines
# ---------------------------------------------------------------------------


class TestReplaceDateInLines(TestCase):
    def _lines(self, text):
        return text.splitlines(keepends=True)

    def test_replaces_content_between_tags(self):
        lines = self._lines(SAMPLE_README)
        new_lines, found = replace_date_in_lines(lines, "NEW DATE")
        self.assertTrue(found)
        joined = "".join(new_lines)
        self.assertIn("NEW DATE", joined)
        self.assertNotIn("old content", joined)

    def test_preserves_surrounding_content(self):
        lines = self._lines(SAMPLE_README)
        new_lines, _ = replace_date_in_lines(lines, "X")
        joined = "".join(new_lines)
        self.assertIn("# Hello", joined)
        self.assertIn("More text", joined)

    def test_preserves_marker_lines(self):
        lines = self._lines(SAMPLE_README)
        new_lines, _ = replace_date_in_lines(lines, "X")
        joined = "".join(new_lines)
        self.assertIn(START_TAG, joined)
        self.assertIn(END_TAG, joined)

    def test_returns_false_when_no_tags(self):
        lines = self._lines(README_NO_TAGS)
        new_lines, found = replace_date_in_lines(lines, "X")
        self.assertFalse(found)
        self.assertEqual("".join(new_lines), README_NO_TAGS)

    def test_empty_input(self):
        new_lines, found = replace_date_in_lines([], "X")
        self.assertFalse(found)
        self.assertEqual(new_lines, [])

    def test_only_start_tag_no_end(self):
        lines = self._lines(f" {START_TAG}\nold\n")
        new_lines, found = replace_date_in_lines(lines, "X")
        self.assertTrue(found)
        joined = "".join(new_lines)
        self.assertNotIn("old", joined)
        self.assertIn("X", joined)

    def test_multiple_lines_between_tags(self):
        readme = (
            f" {START_TAG}\n"
            "line1\n"
            "line2\n"
            "line3\n"
            f" {END_TAG}\n"
        )
        lines = self._lines(readme)
        new_lines, found = replace_date_in_lines(lines, "REPLACED")
        self.assertTrue(found)
        joined = "".join(new_lines)
        self.assertNotIn("line1", joined)
        self.assertNotIn("line2", joined)
        self.assertNotIn("line3", joined)
        self.assertIn("REPLACED", joined)

    def test_date_string_appended_with_newline(self):
        lines = self._lines(SAMPLE_README)
        new_lines, _ = replace_date_in_lines(lines, "DATE")
        # The injected line should end with \n
        date_line = [l for l in new_lines if "DATE" in l]
        self.assertTrue(all(l.endswith("\n") for l in date_line))


# ---------------------------------------------------------------------------
# fetch_hijri_date (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchHijriDate(TestCase):
    def test_parses_valid_response(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = SAMPLE_API_RESPONSE
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("scripts.update_hijri.urllib.request.urlopen", return_value=mock_resp):
            hijri = fetch_hijri_date()

        self.assertEqual(hijri["day"], "15")
        self.assertEqual(hijri["month"]["en"], "Ramadan")
        self.assertEqual(hijri["year"], "1446")

    def test_raises_on_bad_json(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"NOT JSON"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("scripts.update_hijri.urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(json.JSONDecodeError):
                fetch_hijri_date()

    def test_raises_on_missing_key(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": {}}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("scripts.update_hijri.urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(KeyError):
                fetch_hijri_date()

    def test_raises_on_network_error(self):
        with patch(
            "scripts.update_hijri.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            with self.assertRaises(OSError):
                fetch_hijri_date()


# ---------------------------------------------------------------------------
# update_readme (integration-style, still mocked HTTP)
# ---------------------------------------------------------------------------


class TestUpdateReadme(TestCase):
    def _mock_urlopen(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = SAMPLE_API_RESPONSE
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_updates_readme_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_README)
            tmp_path = f.name

        try:
            with patch(
                "scripts.update_hijri.urllib.request.urlopen",
                return_value=self._mock_urlopen(),
            ):
                update_readme(readme_path=tmp_path)

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("Ramadan", content)
            self.assertIn("1446", content)
            self.assertNotIn("old content", content)
            self.assertIn(START_TAG, content)
            self.assertIn(END_TAG, content)
        finally:
            os.unlink(tmp_path)

    def test_exits_when_no_tags(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(README_NO_TAGS)
            tmp_path = f.name

        try:
            with patch(
                "scripts.update_hijri.urllib.request.urlopen",
                return_value=self._mock_urlopen(),
            ):
                with self.assertRaises(SystemExit) as ctx:
                    update_readme(readme_path=tmp_path)
                self.assertEqual(ctx.exception.code, 1)
        finally:
            os.unlink(tmp_path)

    def test_preserves_text_outside_tags(self):
        readme = (
            "Header line\n"
            f" {START_TAG}\n"
            "old date\n"
            f" {END_TAG}\n"
            "Footer line\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(readme)
            tmp_path = f.name

        try:
            with patch(
                "scripts.update_hijri.urllib.request.urlopen",
                return_value=self._mock_urlopen(),
            ):
                update_readme(readme_path=tmp_path)

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("Header line", content)
            self.assertIn("Footer line", content)
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    main()
