"""Minimal PIC16 (14-bit) disassembler, to read Kodak's own bootloader.

The mc*/dx*/lp*/cd* firmware images DO include their 0x0000-0x03FF bootloader
region -- unlike every PIC18 motor image, which start at 0x400. Those PIC16
bootloaders implement the SAME wire protocol as the PIC18 one we lost:
same command set (1 read / 2 write 16 / 4 erase row / 8 finalise), same
board+2 addressing, same app-valid gate. Different core, same design.

So they are a behavioural specification for the bootloader we need to rebuild.
"""
import sys
def load(p):
    m={};ext=0
    for l in open(p,errors='ignore'):
        l=l.strip()
        if not l.startswith(':'):continue
        b=bytes.fromhex(l[1:])
        if len(b)<5:continue
        n,a,t=b[0],(b[1]<<8)|b[2],b[3]
        if t==0:
            for i,v in enumerate(b[4:4+n]):m[ext+a+i]=v
        elif t==4:ext=((b[4]<<8)|b[5])<<16
        elif t==1:break
    return m
SFR={0x00:"INDF",0x01:"TMR0",0x02:"PCL",0x03:"STATUS",0x04:"FSR",0x05:"PORTA",
     0x06:"PORTB",0x07:"PORTC",0x08:"PORTD",0x09:"PORTE",0x0A:"PCLATH",
     0x0B:"INTCON",0x0C:"PIR1",0x0D:"PIR2",0x13:"SSPBUF",0x14:"SSPCON",
     0x81:"OPTION",0x85:"TRISA",0x86:"TRISB",0x87:"TRISC",0x8C:"PIE1",
     0x91:"SSPCON2",0x92:"PR2",0x93:"SSPADD",0x94:"SSPSTAT",
     0x9A:"EEDATA",0x9B:"EEADR",0x9C:"EECON1",0x9D:"EECON2"}
def f(x): return SFR.get(x,f"0x{x:02x}")
def dis(v,a):
    if v&0x3800==0x2800: return f"GOTO  {v&0x7FF:#05x}"
    if v&0x3800==0x2000: return f"CALL  {v&0x7FF:#05x}"
    if v&0x3F00==0x3000: return f"MOVLW {v&0xFF:#04x}"
    if v&0x3F00==0x3900: return f"ANDLW {v&0xFF:#04x}"
    if v&0x3F00==0x3800: return f"IORLW {v&0xFF:#04x}"
    if v&0x3F00==0x3A00: return f"XORLW {v&0xFF:#04x}"
    if v&0x3F00==0x3E00: return f"ADDLW {v&0xFF:#04x}"
    if v&0x3F00==0x3C00: return f"SUBLW {v&0xFF:#04x}"
    if v&0x3F80==0x0080: return f"MOVWF {f(v&0x7F)}"
    if v==0x0008: return "RETURN"
    if v==0x0009: return "RETFIE"
    if v==0x0064: return "CLRWDT"
    if v==0x0063: return "SLEEP"
    if v&0x3F80==0x0180: return f"CLRF  {f(v&0x7F)}"
    if v&0x3F00==0x0800: return f"MOVF  {f(v&0x7F)},{'F' if v&0x80 else 'W'}"
    if v&0x3C00==0x1000: return f"BCF   {f(v&0x7F)},{(v>>7)&7}"
    if v&0x3C00==0x1400: return f"BSF   {f(v&0x7F)},{(v>>7)&7}"
    if v&0x3C00==0x1800: return f"BTFSC {f(v&0x7F)},{(v>>7)&7}"
    if v&0x3C00==0x1C00: return f"BTFSS {f(v&0x7F)},{(v>>7)&7}"
    if v&0x3F00==0x0A00: return f"INCF  {f(v&0x7F)}"
    if v&0x3F00==0x0300: return f"DECF  {f(v&0x7F)}"
    if v&0x3F00==0x0B00: return f"DECFSZ {f(v&0x7F)}"
    if v&0x3F00==0x0F00: return f"INCFSZ {f(v&0x7F)}"
    if v&0x3F00==0x0700: return f"ADDWF {f(v&0x7F)}"
    if v&0x3F00==0x0200: return f"SUBWF {f(v&0x7F)}"
    if v&0x3F00==0x0500: return f"ANDWF {f(v&0x7F)}"
    if v&0x3F00==0x0400: return f"IORWF {f(v&0x7F)}"
    if v&0x3F00==0x0600: return f"XORWF {f(v&0x7F)}"
    if v&0x3400==0x3400: return f"RETLW {v&0xFF:#04x}"
    return f".word {v:#06x}"
m=load(sys.argv[1])
def w(a): return m.get(a,0xff)|(m.get(a+1,0xff)<<8)
lo,hi=0,0x400
print(f"=== {sys.argv[1]} bootloader region {lo:#x}-{hi:#x}")
for a in range(lo,hi,2):
    v=w(a)
    if v==0x3FFF: continue
    print(f"  {a//2:#06x}  {v:04x}  {dis(v,a)}")
