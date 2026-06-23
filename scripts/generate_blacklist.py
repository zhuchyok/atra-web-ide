import re

def extract_platforms(text):
    # Regex for domains and app IDs
    domain_pattern = r'[a-zA-Z0-9.-]+\.[a-z]{2,}'
    app_id_pattern = r'com\.[a-zA-Z0-9._-]+'

    platforms = set()
    for line in text.split('\n'):
        line = line.strip()
        if not line or '|' in line or '---' in line or ':' in line:
            # Try to extract from table-like structures
            matches = re.findall(r'([a-zA-Z0-9.-]+\.[a-z]{2,}|com\.[a-zA-Z0-9._-]+)', line)
            platforms.update(matches)
            continue

        if re.match(domain_pattern, line) or re.match(app_id_pattern, line):
            platforms.add(line)

    return platforms

# Read existing
with open('docs/marketing/rsya_blacklist_final.txt', 'r') as f:
    final_list = extract_platforms(f.read())

# Read web results
web_files = [
    '/Users/bikos/.cursor/projects/Users-bikos-Documents-atra-web-ide/agent-tools/35d76d43-a54d-47d3-8e42-e0366ba87cb0.txt',
    '/Users/bikos/.cursor/projects/Users-bikos-Documents-atra-web-ide/agent-tools/12dd9f95-064f-4f51-8a31-c294dec40772.txt'
]

for wf in web_files:
    try:
        with open(wf, 'r') as f:
            final_list.update(extract_platforms(f.read()))
    except:
        pass

# Sort and filter
sorted_platforms = sorted(list(final_list))
# Filter out some common false positives
exclude_keywords = ['yandex.ru', 'google.com', 'mail.ru', 'vk.com', 'ok.ru', 'avito.ru', 'youtube.com', 'yandex.net']
filtered_platforms = [p for p in sorted_platforms if not any(k in p for k in exclude_keywords)]

# Take exactly 900
result_900 = filtered_platforms[:900]

with open('docs/marketing/rsya_blacklist_900_new.txt', 'w') as f:
    f.write('\n'.join(result_900))

print(f"Generated 900 platforms in docs/marketing/rsya_blacklist_900_new.txt. Total unique found: {len(filtered_platforms)}")
