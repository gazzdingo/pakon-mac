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

# Build edge list: addr -> list of (target, kind)
edges={}
def add(a,t,k):
    edges.setdefault(a,[]).append((t,k))

a=LO
while a<HI:
    v=w(a); nxt=a+2; sz=2
    if (v&0xFF00)==0xEF00 and (w(a+2)&0xF000)==0xF000:      # GOTO
        k=((w(a+2)&0xFFF)<<8)|(v&0xFF); add(a,k*2,'GOTO'); sz=4; nxt=None
    elif (v&0xFE00)==0xEC00 and (w(a+2)&0xF000)==0xF000:    # CALL
        k=((w(a+2)&0xFFF)<<8)|(v&0xFF); add(a,k*2,'CALL'); sz=4
    elif (v&0xF800)==0xD000:                                # BRA
        o=v&0x7FF; o=o-2048 if o>1023 else o; add(a,a+2+2*o,'BRA'); nxt=None
    elif (v&0xF800)==0xD800:                                # RCALL
        o=v&0x7FF; o=o-2048 if o>1023 else o; add(a,a+2+2*o,'RCALL')
    elif (v&0xF800)==0xE000 and (v&0xFF00)!=0xEF00:         # conditional
        o=v&0xFF; o=o-256 if o>127 else o; add(a,a+2+2*o,'Bcc')
    elif v in (0x0012,0x0011,0x00ff):                       # RETURN/RETFIE/RESET
        nxt=None
    if nxt is not None and sz==4: nxt=a+4
    if nxt is not None: add(a,nxt,'fall')
    a+=sz

# reverse map: who targets X
rev={}
for s,ts in edges.items():
    for t,k in ts:
        if k!='fall': rev.setdefault(t,[]).append((s,k))

BLINK=0x1682; MSSP=0x1A8C
def callers(t,depth=0,seen=None,path=None):
    print(f"{'  '*depth}<- {t:#08x}", end="")
    srcs=rev.get(t,[])
    if not srcs: print("   [NO INCOMING EDGE - entry point or table-driven]"); return
    print()
    for s,k in srcs[:6]:
        print(f"{'  '*(depth+1)}{k} from {s:#08x}")

print("=== who reaches the BLINK routine at 0x1682?")
callers(BLINK)
print("\n=== who reaches MSSP init at 0x1A8C?")
callers(MSSP)

# forward reachability from MSSP init, following non-call edges
def reach(start,limit=6000):
    seen=set(); stack=[start]
    while stack and len(seen)<limit:
        x=stack.pop()
        if x in seen: continue
        seen.add(x)
        for t,k in edges.get(x,[]):
            if t not in seen: stack.append(t)
    return seen

r_from_mssp = reach(MSSP)
print(f"\n=== forward reachability from MSSP init 0x1A8C: {len(r_from_mssp)} addrs")
print(f"    blink routine 0x1682 reachable from MSSP init? "
      f"{'YES' if BLINK in r_from_mssp else 'NO'}")

# Can blink be reached from the RESET vector without passing through MSSP init?
r_no_mssp=set(); stack=[0x400]
while stack:
    x=stack.pop()
    if x in r_no_mssp or x==MSSP: continue   # BLOCK the MSSP node
    r_no_mssp.add(x)
    for t,k in edges.get(x,[]):
        stack.append(t)
print(f"\n=== reachability from reset 0x400 WITH 0x1A8C BLOCKED: {len(r_no_mssp)} addrs")
print(f"    blink 0x1682 still reachable WITHOUT arming MSSP? "
      f"{'*** YES - MSSP init is NOT mandatory ***' if BLINK in r_no_mssp else 'NO - MSSP init is on every path'}")
