"""The LuCI strings and the zh_Hans / zh_Hant catalogs: every message the page
uses is translated, the %s placeholders survive, and no msgstr is empty."""
import json
import re
import unittest
from pathlib import Path

TOP = Path(__file__).resolve().parents[1]
VIEW = TOP / 'htdocs' / 'luci-static' / 'resources' / 'view' / 'simswitch' / 'overview.js'
LANGS = ('zh_Hans', 'zh_Hant')


def messages():
    text = VIEW.read_text()
    out = []
    for msgid in re.findall(r"_\(\s*'([^']*)'\s*\)", text):
        if msgid not in out:
            out.append(msgid)
    return out


def entries(lang):
    path = TOP / 'po' / lang / 'simswitch.po'
    out = {}
    msgid = None
    for line in path.read_text().splitlines():
        if line.startswith('msgid '):
            msgid = json.loads(line[6:])
        elif line.startswith('msgstr '):
            out[msgid] = json.loads(line[7:])
    return out


class I18n(unittest.TestCase):
    def test_every_message_is_translated(self):
        ids = messages()
        self.assertTrue(ids)
        for lang in LANGS:
            with self.subTest(lang=lang):
                table = entries(lang)
                missing = [m for m in ids if not table.get(m)]
                self.assertEqual(missing, [])
                for msgid in ids:
                    self.assertEqual(table[msgid].count('%s'), msgid.count('%s'),
                                     f'{lang}: placeholders differ in {msgid!r}')

    def test_catalogs_have_the_same_keys(self):
        a = set(entries(LANGS[0]))
        b = set(entries(LANGS[1]))
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
