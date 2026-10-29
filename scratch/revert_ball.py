with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\joints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('1.35 * ends[k][3]', '1.0 * ends[k][3]')

with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\joints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Reverted query_ball_point to 1.0')
