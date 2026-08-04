"""Backward trace: does the MSSP-arming path connect to the reset vector?

v2 showed forward reachability from the vectors covers only ~6% of the image,
so forward conclusions are unsafe. Backward tracing from the target is the
sound direction: it does not depend on having every forward edge.
"""
import json
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
rev={}; fwd={}
a=LO
while a<HI:
    v=w(a); sz=2; outs=[]
    if (v&0xFF00)==0xEF00 and (w(a+2)&0xF000)==0xF000:
        outs=[((((w(a+2)&0xFFF)<<8)|(v&0xFF))*2,'GOTO')]; sz=4
    elif (v&0xFE00)==0xEC00 and (w(a+2)&0xF000)==0xF000:
        outs=[((((w(a+2)&0xFFF)<<8)|(v&0xFF))*2,'CALL'),(a+4,'fall')]; sz=4
    elif (v&0xF800)==0xD000:
        o=v&0x7FF; o=o-2048 if o>1023 else o; outs=[(a+2+2*o,'BRA')]
    elif (v&0xF800)==0xD800:
        o=v&0x7FF; o=o-2048 if o>1023 else o; outs=[(a+2+2*o,'RCALL'),(a+2,'fall')]
    elif (v&0xF800)==0xE000:
        o=v&0xFF; o=o-256 if o>127 else o; outs=[(a+2+2*o,'Bcc'),(a+2,'fall')]
    elif v in (0x0012,0x0011,0x00ff): outs=[]
    else: outs=[(a+2,'fall')]
    fwd[a]=outs
    for t,k in outs: rev.setdefault(t,[]).append((a,k))
    a+=sz

def backchain(target, maxdepth=40):
    """Walk backwards to the reset vector, recording one representative path."""
    seen={target:None}; frontier=[target]; depth=0
    while frontier and depth<maxdepth:
        nf=[]
        for x in frontier:
            for s,k in rev.get(x,[]):
                if s not in seen:
                    seen[s]=(x,k); nf.append(s)
        frontier=nf; depth+=1
        if 0x400 in seen: break
    return seen

MSSP=0x1A8C; RESET=0x400
seen=backchain(MSSP)
res={'mssp_incoming':[[hex(s),k] for s,k in rev.get(MSSP,[])],
     'reset_reaches_mssp': RESET in seen,
     'backward_nodes': len(seen)}
if RESET in seen:
    path=[]; x=RESET
    while x is not None and x!=MSSP:
        nxt=seen[x]
        if nxt is None: break
        path.append((hex(x),nxt[1])); x=nxt[0]
    path.append((hex(MSSP),'TARGET'))
    res['path_reset_to_mssp']=path
# who reaches 0x2c6a
res['2c6a_incoming']=[[hex(s),k] for s,k in rev.get(0x2c6a,[])]
res['2c62_incoming']=[[hex(s),k] for s,k in rev.get(0x2c62,[])]
print(json.dumps(res,indent=2))
open('cfg_v3_result.json','w').write(json.dumps(res,indent=2))
