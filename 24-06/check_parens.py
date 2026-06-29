from pathlib import Path
p=Path(r'c:\Users\adeha\Downloads\Final UI 2\24-06\main.py')
s=p.read_text()
lines=s.splitlines()
op=ob=oc=0
for idx,l in enumerate(lines, start=1):
    for ch in l:
        if ch=='(':
            op+=1
        elif ch==')':
            op-=1
        elif ch=='[':
            ob+=1
        elif ch==']':
            ob-=1
        elif ch=='{':
            oc+=1
        elif ch=='}':
            oc-=1
    if op<0 or ob<0 or oc<0:
        print('Negative at line',idx)
        break
    if idx==532:
        print('counts at line 532',op,ob,oc)
        break
print('final counts',op,ob,oc)
