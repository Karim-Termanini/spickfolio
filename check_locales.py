#!/usr/bin/env python3
"""Verify de.json, en.json, and ar.json share the same keys."""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALES = ('de', 'en', 'ar')


def load_keys(lang):
    path = os.path.join(BASE_DIR, f'{lang}.json')
    with open(path, encoding='utf-8') as f:
        return set(json.load(f).keys())


def main():
    keys_by_lang = {lang: load_keys(lang) for lang in LOCALES}
    baseline = keys_by_lang['en']
    failed = False

    for lang in LOCALES:
        if lang == 'en':
            continue
        missing = baseline - keys_by_lang[lang]
        extra = keys_by_lang[lang] - baseline
        if missing:
            failed = True
            print(f'{lang}.json missing keys ({len(missing)}):', sorted(missing))
        if extra:
            failed = True
            print(f'{lang}.json extra keys ({len(extra)}):', sorted(extra))

    if failed:
        sys.exit(1)

    print(f'Locale parity OK — {len(baseline)} keys in {", ".join(LOCALES)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
