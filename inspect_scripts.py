import re

path = r'C:\Users\marco\.gemini\antigravity\brain\ab31648f-bca8-4dce-b958-4b8a8ba8c2d5\.system_generated\steps\770\content.md'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

scripts = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
print(f'Total script tags: {len(scripts)}')

for i, s in enumerate(scripts):
    print(f'Script {i}: length {len(s)}')
    # Check if there is data
    if 'AF_initDataCallback' in s:
        print(f'  -> Found AF_initDataCallback in script {i}')
        # print first 500 chars
        print(s[:500])
    elif 'data:' in s or 'WIZ' in s:
        print(f'  -> Script {i} has WIZ or data')
