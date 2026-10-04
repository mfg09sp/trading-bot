import re

path = r'C:\Users\marco\.gemini\antigravity\brain\ab31648f-bca8-4dce-b958-4b8a8ba8c2d5\.system_generated\steps\770\content.md'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

scripts = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
for i in [4, 9, 10, 11, 14]:
    print(f'=== Script {i} ===')
    print(scripts[i][:1000])
