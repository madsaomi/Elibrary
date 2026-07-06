"""Compile .po files to .mo without gettext tools."""
import os
import re
import struct

LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'locale')


def _parse_po(po_path):
    """Parse .po file into list of (msgid, msgstr) tuples."""
    with open(po_path, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = []
    current_id = []
    current_str = []
    in_id = False
    in_str = False

    for line in content.split('\n'):
        if line.startswith('msgid "'):
            if current_id or current_str:
                entries.append((''.join(current_id), ''.join(current_str)))
            current_id = []
            current_str = []
            val = line[7:-1]  # Extract value between quotes
            current_id.append(val)
            in_id = True
            in_str = False
        elif line.startswith('msgstr "'):
            in_id = False
            in_str = True
            val = line[8:-1]
            current_str.append(val)
        elif in_id and line.startswith('"'):
            current_id.append(line[1:-1])
        elif in_str and line.startswith('"'):
            current_str.append(line[1:-1])
        elif not line.startswith('"') and not line.startswith('#'):
            in_id = False
            in_str = False

    if current_id or current_str:
        entries.append((''.join(current_id), ''.join(current_str)))
    # Unescape C-style escapes (\\n -> \n, \\" -> \", \\\\ -> \\)
    unescaped = []
    for msgid, msgstr in entries:
        msgid = msgid.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
        msgstr = msgstr.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
        unescaped.append((msgid, msgstr))
    return unescaped


def po_to_mo(po_path, mo_path):
    entries = _parse_po(po_path)
    if not entries:
        print(f'No entries found in {po_path}')
        return

    # Ensure empty msgid is first (catalog metadata)
    empty_entry = None
    non_empty = []
    for msgid, msgstr in entries:
        if msgid == '':
            empty_entry = (msgid, msgstr)
        else:
            non_empty.append((msgid, msgstr))
    ordered = ([empty_entry] if empty_entry else []) + non_empty

    ids = [msgid for msgid, _ in ordered]
    strs = [msgstr for _, msgstr in ordered]
    count = len(ids)

    id_bytes = [k.encode('utf-8') for k in ids]
    str_bytes = [v.encode('utf-8') for v in strs]
    id_lengths = [len(b) for b in id_bytes]
    str_lengths = [len(b) for b in str_bytes]

    # .mo format (little-endian):
    # Header: magic(4) + version(4) + count(4) + orig_offset(4) + trans_offset(4) = 20 bytes
    HEADER_SIZE = 20
    orig_table_offset = HEADER_SIZE
    trans_table_offset = orig_table_offset + count * 8
    str_data_offset = trans_table_offset + count * 8

    le = '<'
    with open(mo_path, 'wb') as f:
        # Magic number (little-endian)
        f.write(struct.pack(le + 'I', 0x950412de))
        # Version, count, orig_offset, trans_offset
        f.write(struct.pack(le + '4I', 0, count, orig_table_offset, trans_table_offset))

        # Original strings table: each entry = (length, offset)
        offset = str_data_offset
        for length in id_lengths:
            f.write(struct.pack(le + 'II', length, offset))
            offset += length

        # Translated strings table
        offset = str_data_offset + sum(id_lengths)
        for length in str_lengths:
            f.write(struct.pack(le + 'II', length, offset))
            offset += length

        # Raw string data
        for b in id_bytes:
            f.write(b)
        for b in str_bytes:
            f.write(b)
        # Trailing null byte to ensure tend < buflen for last entry
        f.write(b'\x00')

    print(f'Compiled {count} messages: {po_path} -> {mo_path}')


def main():
    for lang in ['uz', 'kaa', 'en']:
        po = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES', 'django.po')
        mo = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES', 'django.mo')
        if os.path.exists(po):
            po_to_mo(po, mo)


if __name__ == '__main__':
    main()
