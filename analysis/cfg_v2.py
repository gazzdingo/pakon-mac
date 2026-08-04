"""Control-flow analysis of nm0506.HEX, seeded from ALL entry points.

v1 seeded only the reset vector at 0x400 and concluded "MSSP init is on every
path to the blink routine". That result was VACUOUS: 0x1682 had no incoming
edge at all, so the claim was trivially true for an unreachable node.

This app is bootloader-relocated, so its vectors are at 0x400 (reset),
0x408 (high-priority ISR) and 0x418 (low-priority ISR). A timer-driven blink
lives in an ISR and is invisible to a graph seeded only from reset.
"""
import json, sys
HEX="/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX"
mem={};ext=0
for l in open(HEX):
    l=l.strip()
    if not l.startswith(":"):continue
    b=bytes.fromhex(l[1:]);n,a,t=b[0],(b[1]<<8)|b[2],b[3]
    if t==0:
        for i,v in enumerate(b[4:4+n]):mem[ext+a+i]=v
    elif t==4:ext=((b[4]<<8)|b[5])<<16
    elif t==1:break
def w(a):return mem.get(a,0xff)|(mem.get(a+1,0xff)<<8)
LO=0x400; HI=max(k for k in mem if k<0x30000)+1
edges={}
def add(a,t,k): edges.setdefault(a,[]).append((t,k))
a=LO
while a<HI:
    v=w(a); nxt=a+2; sz=2
    if (v&0xFF00)==0xEF00 and (w(a+2)&0xF000)==0xF000:
        add(a,(((w(a+2)&0xFFF)<<8)|(v&0xFF))*2,'GOTO'); sz=4; nxt=None
    elif (v&0xFE00)==0xEC00 and (w(a+2)&0xF000)==0xF000:
        add(a,(((w(a+2)&0xFFF)<<8)|(v&0xFF))*2,'CALL'); sz=4; nxt=a+4
    elif (v&0xF800)==0xD000:
        o=v&0x7FF; o=o-2048 if o>1023 else o; add(a,a+2+2*o,'BRA'); nxt=None
    elif (v&0xF800)==0xD800:
        o=v&0x7FF; o=o-2048 if o>1023 else o; add(a,a+2+2*o,'RCALL')
    elif (v&0xF800)==0xE000:
        o=v&0xFF; o=o-256 if o>127 else o; add(a,a+2+2*o,'Bcc')
    elif v in (0x0012,0x0011,0x00ff): nxt=None
    if nxt is not None: add(a,nxt,'fall')
    a+=sz
rev={}
for s,ts in edges.items():
    for t,k in ts:
        if k!='fall': rev.setdefault(t,[]).append((s,k))

# Detect computed jumps -- writes to PCL (0xFF9). These break static CFG.
pcl=[a for a in range(LO,HI,2) if (w(a)&0xFF)==0xF9 and (w(a)&0xFF00) in (0x6E00,0x2600,0x2400,0x5000)]
ENTRIES=[0x400,0x408,0x418]
BLINK=0x1682; MSSP=0x1A8C
def reach(seeds, block=None):
    seen=set(); stack=list(seeds)
    while stack:
        x=stack.pop()
        if x in seen or x==block: continue
        seen.add(x)
        for t,k in edges.get(x,[]): stack.append(t)
    return seen
res={}
res['pcl_writes']=[hex(a) for a in pcl]
res['blink_incoming']=[[hex(s),k] for s,k in rev.get(BLINK,[])]
res['mssp_incoming']=[[hex(s),k] for s,k in rev.get(MSSP,[])]
for name,seeds in (('reset_only',[0x400]),('all_vectors',ENTRIES)):
    r=reach(seeds)
    rb=reach(seeds,block=MSSP)
    res[name]={'reachable':len(r),
               'blink_reachable':BLINK in r,
               'mssp_reachable':MSSP in r,
               'blink_reachable_without_mssp':BLINK in rb}
# what IS at 0x408/0x418
res['vectors']={hex(v):hex(w(v)) for v in ENTRIES}
print(json.dumps(res,indent=2))
open('cfg_v2_result.json','w').write(json.dumps(res,indent=2))
