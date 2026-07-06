import re
with open('locale/en/LC_MESSAGES/django.po', 'r', encoding='utf-8') as f:
    content = f.read()

# Try a simpler approach: find all msgid/msgstr pairs
pattern = re.compile(r'msgid "(.*?)"\nmsgstr "(.*?)"', re.DOTALL)
matches = pattern.findall(content)
print(f"Simple regex found {len(matches)} pairs")
for msgid, msgstr in matches[:3]:
    print(f"  ID: {msgid[:40]}")
    print(f"  STR: {msgstr[:40]}")

# Try another approach
parts = re.split(r'\n(?=msgid )', content)
print(f"\nSplit found {len(parts)} parts")
for i, p in enumerate(parts):
    if p.strip():
        first_line = p.split('\n')[0]
        print(f"  Part {i}: {first_line[:60]}")
