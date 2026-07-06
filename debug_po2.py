import sys
sys.path.insert(0, '.')
from scripts.compile_messages import _parse_po

entries = _parse_po('locale/en/LC_MESSAGES/django.po')
print(f"Total entries: {len(entries)}")
for i, (msgid, msgstr) in enumerate(entries):
    print(f"\n--- Entry {i} ---")
    print(f"  msgid: {repr(msgid[:60])}")
    print(f"  msgstr: {repr(msgstr[:60])}")
