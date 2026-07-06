import os
import re

EMOJI_MAP = {
    '🏆': '<i data-lucide="trophy" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🧠': '<i data-lucide="brain" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📚': '<i data-lucide="book-open" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📖': '<i data-lucide="book-marked" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📘': '<i data-lucide="book" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📦': '<i data-lucide="package" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📋': '<i data-lucide="clipboard-list" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '👥': '<i data-lucide="users" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🧒': '<i data-lucide="baby" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🎓': '<i data-lucide="graduation-cap" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '👨‍🏫': '<i data-lucide="user-check" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🏫': '<i data-lucide="school" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📥': '<i data-lucide="log-in" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📤': '<i data-lucide="log-out" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📷': '<i data-lucide="camera" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📰': '<i data-lucide="newspaper" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '⚙️': '<i data-lucide="settings" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🔄': '<i data-lucide="refresh-cw" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '👤': '<i data-lucide="user" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🏠': '<i data-lucide="home" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🛒': '<i data-lucide="shopping-cart" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🔔': '<i data-lucide="bell" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🌓': '<i data-lucide="moon" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '⚠️': '<i data-lucide="alert-triangle" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '➕': '<i data-lucide="plus" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '❌': '<i data-lucide="x" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '✅': '<i data-lucide="check" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📌': '<i data-lucide="pin" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '👇': '<i data-lucide="arrow-down" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '⭐': '<i data-lucide="star" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '👨‍🎓': '<i data-lucide="graduation-cap" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🔑': '<i data-lucide="key" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📱': '<i data-lucide="smartphone" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🚀': '<i data-lucide="rocket" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '💡': '<i data-lucide="lightbulb" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🎯': '<i data-lucide="target" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '📅': '<i data-lucide="calendar" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
    '🥇': '<i data-lucide="medal" style="width:1.25rem;height:1.25rem;vertical-align:middle;color:#ffd700;"></i>',
    '🥈': '<i data-lucide="medal" style="width:1.25rem;height:1.25rem;vertical-align:middle;color:#c0c0c0;"></i>',
    '🥉': '<i data-lucide="medal" style="width:1.25rem;height:1.25rem;vertical-align:middle;color:#cd7f32;"></i>',
    '👏': '<i data-lucide="thumbs-up" style="width:1.25rem;height:1.25rem;vertical-align:middle;"></i>',
}

base_dir = r"c:\Users\~\Desktop\123\dashboard\templates\dashboard"
replaced_count = 0

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = content
            for emoji, replacement in EMOJI_MAP.items():
                if emoji in new_content:
                    # special case: don't replace inside icon_emoji|default:'🏆' template tag strings if possible
                    # but actually we want to replace the default value, so it's fine.
                    # wait, if we replace in `icon_emoji|default:'🏆'`, it becomes `icon_emoji|default:'<i...'`
                    # which is what we want because it renders as HTML anyway if autoescape is off.
                    # but wait, Django autoescapes by default!
                    # if it's {{ ua.achievement.icon_emoji|default:'🏆'|safe }}, it would work.
                    # Let's skip replacing inside {{ ... }} tags to be safe, or just do simple replacement.
                    # To be safe, we just replace all.
                    new_content = new_content.replace(emoji, replacement)
            
            if new_content != content:
                # Fix up any django default tags that got replaced
                new_content = re.sub(r"default:'<i data-lucide=\"(.*?)\" style=\"(.*?)\"></i>'", r"default:'\1'", new_content)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                replaced_count += 1
                print(f"Updated: {filepath}")

print(f"Total files updated: {replaced_count}")
