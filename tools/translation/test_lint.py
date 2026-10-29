#!/usr/bin/env python3
"""Tests for the translation linter. Uses made-up messages, never game text.

    python3 -m unittest tools/translation/test_lint.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lint import Linter  # noqa: E402

VANILLA = """\
#message:18:(Test_0000) {
	[Style right]
	Hello there, friend.[BR]
	How are you?[BR]
	[Wait][End]
}

#message:18:(Test_0001) {
	[Style sign]
	You got [Var 0]![BR]
	[Wait][End]
}

#message:18:(Test_0002) {
	...[End]
}
"""


class LintTest(unittest.TestCase):
    def lint(self, translated: str, raw: bytes = None, complete=False, added=()):
        with tempfile.TemporaryDirectory() as tmp:
            vanilla = Path(tmp) / "vanilla"
            ours = Path(tmp) / "ours"
            vanilla.mkdir()
            ours.mkdir()
            (vanilla / "18_Test.msg").write_text(VANILLA, encoding="utf-8")
            target = ours / "18_Test.msg"
            if raw is not None:
                target.write_bytes(raw)
            else:
                target.write_text(translated, encoding="utf-8")
            linter = Linter(vanilla, ours, complete=complete, added=set(added))
            linter.run()
            return linter

    def errors(self, linter):
        return [f.text for f in linter.findings if f.level == "error"]

    def test_clean_translation(self):
        linter = self.lint(
            "#message:18:(Test_0000) {\n\t[Style right]\n\tHola, amic.[BR]\n\tCom estàs?[BR]\n\t[Wait][End]\n}\n"
        )
        self.assertEqual(self.errors(linter), [])
        self.assertEqual(linter.stats["18_Test.msg"].translated, 1)

    def test_partial_file_is_info_unless_complete(self):
        text = "#message:18:(Test_0000) {\n\t[Style right]\n\tHola.[BR]\n\tCom va?[BR]\n\t[Wait][End]\n}\n"
        self.assertEqual(self.errors(self.lint(text)), [])
        self.assertTrue(any("not translated yet" in e for e in self.errors(self.lint(text, complete=True))))

    def test_control_code_mismatch(self):
        linter = self.lint("#message:18:(Test_0000) {\n\t[Style right]\n\tHola, amic. Com estàs?[BR]\n\t[Wait][End]\n}\n")
        self.assertTrue(any("control codes differ" in e for e in self.errors(linter)))

    def test_middle_dot(self):
        linter = self.lint(
            "#message:18:(Test_0000) {\n\t[Style right]\n\tCol·lega.[BR]\n\tCom va?[BR]\n\t[Wait][End]\n}\n"
        )
        self.assertTrue(any("write l.l" in e for e in self.errors(linter)))

    def test_unknown_duplicate_and_order(self):
        body = "\t[Style sign]\n\tHas aconseguit [Var 0]![BR]\n\t[Wait][End]\n}\n"
        first = "#message:18:(Test_0000) {\n\t[Style right]\n\tHola.[BR]\n\tCom va?[BR]\n\t[Wait][End]\n}\n"
        linter = self.lint(
            "#message:18:(Test_0001) {\n" + body + first + "#message:18:(Test_0001) {\n" + body
            + "#message:18:(Test_00FF) {\n\tx[End]\n}\n"
        )
        errors = self.errors(linter)
        self.assertTrue(any("out of vanilla order" in e for e in errors))
        self.assertTrue(any("appears twice" in e for e in errors))
        self.assertTrue(any("no vanilla message has this ID" in e for e in errors))

    def test_added_messages(self):
        first = "#message:18:(Test_0000) {\n\t[Style right]\n\tHola.[BR]\n\tCom va?[BR]\n\t[Wait][End]\n}\n"
        extra = "#message:18:(Test_Extra) {\n\tUn missatge nou.[End]\n}\n"

        linter = self.lint(first + extra, added=["Test_Extra"])
        self.assertEqual(self.errors(linter), [])

        linter = self.lint(extra + first, added=["Test_Extra"])
        self.assertTrue(any("added messages go after every vanilla one" in e for e in self.errors(linter)))

        linter = self.lint(first + extra)
        self.assertTrue(any("no vanilla message has this ID" in e for e in self.errors(linter)))

    def test_overflow(self):
        linter = self.lint(
            "#message:18:(Test_0000) {\n\t[Style right]\n\tAquesta línia és massa llarga per a la bombolla de diàleg.[BR]"
            "\n\tCom va?[BR]\n\t[Wait][End]\n}\n"
        )
        self.assertTrue(any("over the 252 px right box" in e for e in self.errors(linter)))

    def test_var_allowance(self):
        # 200 px of text plus a variable doesn't fit a 245 px sign
        long = "Has aconseguit un objecte molt especial: [Var 0]![BR]"
        linter = self.lint(f"#message:18:(Test_0001) {{\n\t[Style sign]\n\t{long}\n\t[Wait][End]\n}}\n")
        self.assertTrue(any("[Var]" in e for e in self.errors(linter)))

    def test_header_portability(self):
        linter = self.lint("#message:18:(Test_0002){\n\t...[End]\n}\n")
        self.assertTrue(any("isn't portable" in e for e in self.errors(linter)))

    def test_comments_and_crlf(self):
        text = "#message:18:(Test_0002) {\n\t// note\n\t...[End]\n}\n"
        self.assertTrue(any("comment" in e for e in self.errors(self.lint(text))))
        crlf = b"#message:18:(Test_0002) {\r\n\t...[End]\r\n}\r\n"
        self.assertTrue(any("CR line endings" in e for e in self.errors(self.lint("", raw=crlf))))

    def test_identical_text_is_not_translated(self):
        linter = self.lint(
            "#message:18:(Test_0000) {\n\t[Style right]\n\tHello there, friend.[BR]\n\tHow are you?[BR]\n\t[Wait][End]\n}\n"
        )
        self.assertEqual(linter.stats["18_Test.msg"].translated, 0)


if __name__ == "__main__":
    unittest.main()
