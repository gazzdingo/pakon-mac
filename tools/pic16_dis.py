#!/usr/bin/env python3
"""Flow-following disassembler for PIC16 midrange (14-bit) firmware images.

Written for the Pakon F-135 DX board image `dx0211.HEX` (PIC16F877); see
docs/57-dx-firmware.md.

Why this exists: gpdasm (gputils) decodes CALL/GOTO using only the 11 address
bits in the opcode and ignores PCLATH<4:3>, so on any paged image most branch
targets it prints are wrong.  This tool does a worklist traversal from the
reset and interrupt vectors, propagating PCLATH<4:3> and the RP1:RP0 bank bits
along every control-flow edge, and resolves each target properly.  It also
names SFRs per the resolved bank, which gpdasm cannot do either.

Usage:
    python3 tools/pic16_dis.py <image.hex> [-o out.lst]

It reports how many words were reached and whether any address was reached
under conflicting PCLATH values (which would make its targets untrustworthy).
"""
import sys
import argparse
from collections import defaultdict, deque

def load_ihex(path):
    mem, ext = {}, 0
    for line in open(path, 'r', errors='replace'):
        line = line.strip()
        if not line.startswith(':'): continue
        b = bytes.fromhex(line[1:]); n, addr, typ = b[0], (b[1]<<8)|b[2], b[3]
        data = b[4:4+n]
        if typ == 0:
            for i, v in enumerate(data): mem[ext+addr+i] = v
        elif typ == 4: ext = ((data[0]<<8)|data[1]) << 16
        elif typ == 1: break
    return mem

ap = argparse.ArgumentParser()
ap.add_argument('image', help='Intel HEX image')
ap.add_argument('-o', '--out', default=None, help='output listing path')
args = ap.parse_args()

mem = load_ihex(args.image)
words = {}
for ba in sorted(mem):
    if ba % 2 == 0 and (ba+1) in mem: words[ba//2] = mem[ba] | (mem[ba+1]<<8)
CODE = {a: w for a, w in words.items() if a < 0x2000}

# state per address: set of (pclath4_3, bank)
state = defaultdict(set)
wl = deque()
def push(a, pl, bk):
    if a not in CODE: return
    if (pl, bk) in state[a]: return
    state[a].add((pl, bk)); wl.append((a, pl, bk))

push(0x0000, 0, 0)
push(0x0004, 0, 0)   # ISR entry

calls = defaultdict(set)   # target -> callers
gotos = defaultdict(set)
targets = {}               # addr -> resolved target

while wl:
    a, pl, bk = wl.popleft()
    w = CODE[a]
    op11 = w & 0x7ff
    f = w & 0x7f
    nxt_pl, nxt_bk = pl, bk
    # PCLATH / STATUS updates
    if (w >> 10) == 0x4:      # bcf f,b
        b = (w >> 7) & 7
        if f == 0x0a and b in (3, 4): nxt_pl = pl & ~(1 << b)
        if f == 0x03 and b == 5: nxt_bk = bk & ~1
        if f == 0x03 and b == 6: nxt_bk = bk & ~2
    elif (w >> 10) == 0x5:    # bsf f,b
        b = (w >> 7) & 7
        if f == 0x0a and b in (3, 4): nxt_pl = pl | (1 << b)
        if f == 0x03 and b == 5: nxt_bk = bk | 1
        if f == 0x03 and b == 6: nxt_bk = bk | 2
    elif (w & 0x3f80) == 0x0080 and f == 0x0a:   # movwf PCLATH
        prev = CODE.get(a-1, 0)
        if (prev >> 9) == 0x18: nxt_pl = (prev & 0xff) & 0x18
        else: nxt_pl = pl
    elif (w & 0x3f80) == 0x0180 and f == 0x0a:   # clrf PCLATH
        nxt_pl = 0
    elif (w & 0x3f80) == 0x0180 and f == 0x03:   # clrf STATUS
        nxt_bk = 0

    if (w >> 11) == 0x4:      # CALL
        t = op11 | (pl << 8); targets[a] = t
        calls[t].add(a)
        push(t, pl, bk)
        push(a+1, pl, bk)     # PCLATH/bank after return: unknown, assume caller restores
        continue
    if (w >> 11) == 0x5:      # GOTO
        t = op11 | (pl << 8); targets[a] = t
        gotos[t].add(a)
        push(t, pl, bk)
        continue
    if w in (0x0008, 0x0009) or (w >> 8) == 0x34:   # return/retfie/retlw
        continue
    if (w & 0x3f80) == 0x0080 and f == 0x02:        # movwf PCL - computed goto
        continue
    # skip-next instructions
    if (w >> 10) in (0x6, 0x7) or (w & 0x3f00) in (0x0b00, 0x0f00):
        push(a+2, nxt_pl, nxt_bk)
    push(a+1, nxt_pl, nxt_bk)

amb = [a for a in state if len({s[0] for s in state[a]}) > 1]
print("reachable words: %d / %d ; ambiguous-PCLATH addrs: %d" % (len(state), len(CODE), len(amb)))

xref = defaultdict(set)
for a, t in targets.items(): xref[t].add(a)

SFR = {0x00:'INDF',0x01:'TMR0',0x02:'PCL',0x03:'STATUS',0x04:'FSR',0x05:'PORTA',0x06:'PORTB',
0x07:'PORTC',0x08:'PORTD',0x09:'PORTE',0x0a:'PCLATH',0x0b:'INTCON',0x0c:'PIR1',0x0d:'PIR2',
0x0e:'TMR1L',0x0f:'TMR1H',0x10:'T1CON',0x11:'TMR2',0x12:'T2CON',0x13:'SSPBUF',0x14:'SSPCON',
0x15:'CCPR1L',0x16:'CCPR1H',0x17:'CCP1CON',0x18:'RCSTA',0x19:'TXREG',0x1a:'RCREG',0x1b:'CCPR2L',
0x1c:'CCPR2H',0x1d:'CCP2CON',0x1e:'ADRESH',0x1f:'ADCON0',0x81:'OPTION_REG',0x85:'TRISA',
0x86:'TRISB',0x87:'TRISC',0x88:'TRISD',0x89:'TRISE',0x8c:'PIE1',0x8d:'PIE2',0x8e:'PCON',
0x91:'SSPCON2',0x92:'PR2',0x93:'SSPADD',0x94:'SSPSTAT',0x98:'TXSTA',0x99:'SPBRG',0x9e:'ADRESL',
0x9f:'ADCON1',0x10c:'EEDATA',0x10d:'EEADR',0x18c:'EECON1',0x18d:'EECON2'}
MIRROR={0x00:'INDF',0x02:'PCL',0x03:'STATUS',0x04:'FSR',0x0a:'PCLATH',0x0b:'INTCON'}
SB={0:'C',1:'DC',2:'Z',3:'PD',4:'TO',5:'RP0',6:'RP1',7:'IRP'}
IB={0:'RBIF',1:'INTF',2:'T0IF',3:'RBIE',4:'INTE',5:'T0IE',6:'PEIE',7:'GIE'}
P1={0:'TMR1IF',1:'TMR2IF',2:'CCP1IF',3:'SSPIF',4:'TXIF',5:'RCIF',6:'ADIF',7:'PSPIF'}
A0={0:'ADON',2:'GO',3:'CHS0',4:'CHS1',5:'CHS2',6:'ADCS0',7:'ADCS1'}
SC={4:'CKP',5:'SSPEN',6:'SSPOV',7:'WCOL'}
SS={0:'BF',1:'UA',2:'R_W',3:'S',4:'P',5:'D_A',6:'CKE',7:'SMP'}

def rname(f, bk):
    if f in MIRROR: return MIRROR[f]
    if 0x70 <= f < 0x80: return "cm_%02x" % f
    a = f | (bk << 7)
    return SFR.get(a, "0x%03x" % a)
def bname(f, b, bk):
    if f == 0x03: return SB.get(b, str(b))
    if f == 0x0b: return IB.get(b, str(b))
    a = f | (bk << 7)
    if a == 0x0c: return P1.get(b, str(b))
    if a == 0x1f: return A0.get(b, str(b))
    if a == 0x14: return SC.get(b, str(b))
    if a == 0x94: return SS.get(b, str(b))
    return str(b)

TBL={0x07:'addwf',0x05:'andwf',0x09:'comf',0x03:'decf',0x0b:'decfsz',0x0a:'incf',
     0x0f:'incfsz',0x04:'iorwf',0x08:'movf',0x0d:'rlf',0x0c:'rrf',0x02:'subwf',
     0x0e:'swapf',0x06:'xorwf'}

def txt(a, w, bk):
    f = w & 0x7f; d = 'F' if (w >> 7) & 1 else 'W'
    if w == 0x0064: return "clrwdt"
    if w == 0x0009: return "retfie"
    if w == 0x0008: return "return"
    if w == 0x0063: return "sleep"
    if (w & 0x3f9f) == 0x0000: return "nop"
    if (w >> 12) == 0 and ((w & 0x3f00) >> 8) in TBL:
        return "%-6s %s, %s" % (TBL[(w & 0x3f00) >> 8], rname(f, bk), d)
    if (w & 0x3f80) == 0x0180: return "clrf   %s" % rname(f, bk)
    if (w & 0x3f80) == 0x0100: return "clrw"
    if (w & 0x3f80) == 0x0080: return "movwf  %s" % rname(f, bk)
    b = (w >> 7) & 7
    if (w >> 10) == 0x4: return "bcf    %s, %s" % (rname(f, bk), bname(f, b, bk))
    if (w >> 10) == 0x5: return "bsf    %s, %s" % (rname(f, bk), bname(f, b, bk))
    if (w >> 10) == 0x6: return "btfsc  %s, %s" % (rname(f, bk), bname(f, b, bk))
    if (w >> 10) == 0x7: return "btfss  %s, %s" % (rname(f, bk), bname(f, b, bk))
    k = w & 0xff
    if (w >> 11) == 0x4: return "call   0x%04x" % targets.get(a, w & 0x7ff)
    if (w >> 11) == 0x5: return "goto   0x%04x" % targets.get(a, w & 0x7ff)
    if (w >> 8) == 0x3e: return "addlw  0x%02x" % k
    if (w >> 8) == 0x39: return "andlw  0x%02x" % k
    if (w >> 8) == 0x38: return "iorlw  0x%02x" % k
    if (w >> 8) == 0x3a: return "xorlw  0x%02x" % k
    if (w >> 8) == 0x3c: return "sublw  0x%02x" % k
    if (w >> 9) == 0x18: return "movlw  0x%02x" % k
    if (w >> 9) == 0x1a: return "retlw  0x%02x" % k
    return ".word  0x%04x" % w

outpath = args.out or (args.image.rsplit('.', 1)[0] + '.flow')
with open(outpath, 'w') as fh:
    for a in sorted(CODE):
        w = CODE[a]
        sts = sorted(state.get(a, []))
        bk = sts[0][1] if sts else 0
        bkset = sorted({s[1] for s in sts})
        if a in xref:
            kind = 'FUNC' if a in calls else 'loc'
            refs = ' '.join("%04x" % r for r in sorted(xref[a])[:10])
            fh.write("\n%s_%04x:   ; <- %s\n" % (kind, a, refs))
        mark = '' if sts else '  ; UNREACHED'
        bktag = "b%s" % (''.join(str(x) for x in bkset) if bkset else '?')
        fh.write("%04x  %04x  %-4s  %s%s\n" % (a, w, bktag, txt(a, w, bk), mark))
print("wrote %s" % outpath)
print("functions (call targets): %d" % len(calls))
