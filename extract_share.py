import re
import json

path = r'C:\Users\marco\.gemini\antigravity\brain\ab31648f-bca8-4dce-b958-4b8a8ba8c2d5\.system_generated\steps\770\content.md'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

print('File length:', len(content))

# Look for share data or conversation text
# In Gemini shared chats, the conversation is often embedded in AF_initDataCallback or WIZ_global_data or JSON strings
patterns = [
    r'AF_initDataCallback\({key:\s*\'ds:.*?\);',
    r'WIZ_global_data',
    r'\"r_[a-zA-Z0-9_]+\"',
    r'c_[a-zA-Z0-9_]+'
]

# Let's search for Spanish words or prompts
sp_words = ['para', 'hola', 'quiero', 'trading', 'bot', 'mercado', 'acciones', 'estrategia', 'ganar', 'perdida', 'dinero']
found = []
for p in re.finditer(r'([A-Za-zÁÉÍÓÚáéíóúñÑ0-9\s,\.\?\!\:\;\-\(\)\"\']{30,})', content):
    s = p.group(1).strip()
    words = [w for w in sp_words if w in s.lower()]
    if len(words) >= 2 and len(s) > 50:
        found.append(s)

print(f'Found {len(found)} candidate segments.')
for i, f_text in enumerate(found[:20]):
    print(f'--- Segment {i+1} ---')
    print(f_text[:300])
