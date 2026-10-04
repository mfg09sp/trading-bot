import requests
import json
import re

url = 'https://gemini.google.com/share/d398d222545c?skid=480cdba3-b2f4-4a0f-a184-fb6fd695f4de'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8'
}
r = requests.get(url, headers=headers)
html = r.text

print('HTML length:', len(html))

# Let's search for "d398d222545c" in html
print('d398d222545c count:', html.count('d398d222545c'))

# In Gemini share pages, the payload is often in AF_initDataCallback with data
# Let's find all AF_initDataCallback
callbacks = re.findall(r'AF_initDataCallback\((.*?)\);', html, re.DOTALL)
print('Callbacks count:', len(callbacks))

for i, cb in enumerate(callbacks):
    print(f'Callback {i}: length {len(cb)}')
    if len(cb) > 200:
        # Check if contains strings of conversation
        # Find all strings
        strs = re.findall(r'"([^"\\]{20,})"', cb)
        print(f'  Strings > 20: {len(strs)}')
        for s in strs[:10]:
            print('   ->', s[:100])
