;--------------------------------------------------------
; File Created by SDCC : free open source ISO C Compiler
; Version 4.6.0 #16555 (Mac OS X ppc)
;--------------------------------------------------------
	.module eeprom_dump_all
	
	.optsdcc -mmcs51 --model-small
;--------------------------------------------------------
; Public variables in this module
;--------------------------------------------------------
	.globl _main
	.globl _st
	.globl _d52
	.globl _d51
;--------------------------------------------------------
; special function registers
;--------------------------------------------------------
	.area RSEG    (ABS,DATA)
	.org 0x0000
;--------------------------------------------------------
; special function bits
;--------------------------------------------------------
	.area RSEG    (ABS,DATA)
	.org 0x0000
;--------------------------------------------------------
; overlayable register banks
;--------------------------------------------------------
	.area REG_BANK_0	(REL,OVR,DATA)
	.ds 8
;--------------------------------------------------------
; internal ram data
;--------------------------------------------------------
	.area DSEG    (DATA)
_dump_PARM_2:
	.ds 2
;--------------------------------------------------------
; overlayable items in internal ram
;--------------------------------------------------------
	.area	OSEG    (OVR,DATA)
	.area	OSEG    (OVR,DATA)
;--------------------------------------------------------
; Stack segment in internal ram
;--------------------------------------------------------
	.area SSEG
__start__stack:
	.ds	1

;--------------------------------------------------------
; indirectly addressable internal ram data
;--------------------------------------------------------
	.area ISEG    (DATA)
;--------------------------------------------------------
; absolute internal ram data
;--------------------------------------------------------
	.area IABS    (ABS,DATA)
	.area IABS    (ABS,DATA)
;--------------------------------------------------------
; bit data
;--------------------------------------------------------
	.area BSEG    (BIT)
;--------------------------------------------------------
; paged external ram data
;--------------------------------------------------------
	.area PSEG    (PAG,XDATA)
;--------------------------------------------------------
; uninitialized external ram data
;--------------------------------------------------------
	.area XSEG    (XDATA)
_d51	=	0x0400
_d52	=	0x0500
_st	=	0x0600
;--------------------------------------------------------
; absolute external ram data
;--------------------------------------------------------
	.area XABS    (ABS,XDATA)
;--------------------------------------------------------
; initialized external ram data
;--------------------------------------------------------
	.area XISEG   (XDATA)
	.area HOME    (CODE)
	.area GSINIT0 (CODE)
	.area GSINIT1 (CODE)
	.area GSINIT2 (CODE)
	.area GSINIT3 (CODE)
	.area GSINIT4 (CODE)
	.area GSINIT5 (CODE)
	.area GSINIT  (CODE)
	.area GSFINAL (CODE)
	.area CSEG    (CODE)
;--------------------------------------------------------
; interrupt vector
;--------------------------------------------------------
	.area HOME    (CODE)
__interrupt_vect:
	ljmp	__sdcc_gsinit_startup
; restartable atomic support routines
	.ds	5
sdcc_atomic_exchange_rollback_start::
	nop
	nop
sdcc_atomic_exchange_pdata_impl:
	movx	a, @r0
	mov	r3, a
	mov	a, r2
	movx	@r0, a
	sjmp	sdcc_atomic_exchange_exit
	nop
	nop
sdcc_atomic_exchange_xdata_impl:
	movx	a, @dptr
	mov	r3, a
	mov	a, r2
	movx	@dptr, a
	sjmp	sdcc_atomic_exchange_exit
sdcc_atomic_compare_exchange_idata_impl:
	mov	a, @r0
	cjne	a, ar2, .+#5
	mov	a, r3
	mov	@r0, a
	ret
	nop
sdcc_atomic_compare_exchange_pdata_impl:
	movx	a, @r0
	cjne	a, ar2, .+#5
	mov	a, r3
	movx	@r0, a
	ret
	nop
sdcc_atomic_compare_exchange_xdata_impl:
	movx	a, @dptr
	cjne	a, ar2, .+#5
	mov	a, r3
	movx	@dptr, a
	ret
sdcc_atomic_exchange_rollback_end::

sdcc_atomic_exchange_gptr_impl::
	jnb	b.6, sdcc_atomic_exchange_xdata_impl
	mov	r0, dpl
	jb	b.5, sdcc_atomic_exchange_pdata_impl
sdcc_atomic_exchange_idata_impl:
	mov	a, r2
	xch	a, @r0
	mov	dpl, a
	ret
sdcc_atomic_exchange_exit:
	mov	dpl, r3
	ret
sdcc_atomic_compare_exchange_gptr_impl::
	jnb	b.6, sdcc_atomic_compare_exchange_xdata_impl
	mov	r0, dpl
	jb	b.5, sdcc_atomic_compare_exchange_pdata_impl
	sjmp	sdcc_atomic_compare_exchange_idata_impl
;--------------------------------------------------------
; global & static initialisations
;--------------------------------------------------------
	.area HOME    (CODE)
	.area GSINIT  (CODE)
	.area GSFINAL (CODE)
	.area GSINIT  (CODE)
	.globl __sdcc_gsinit_startup
	.globl __sdcc_program_startup
	.globl __start__stack
	.globl __mcs51_genXINIT
	.globl __mcs51_genXRAMCLEAR
	.globl __mcs51_genRAMCLEAR
	.area GSFINAL (CODE)
	ljmp	__sdcc_program_startup
;--------------------------------------------------------
; Home
;--------------------------------------------------------
	.area HOME    (CODE)
	.area HOME    (CODE)
__sdcc_program_startup:
	lcall	_main
__sdcc_program_exit:
	sjmp	.
;	return from main will return to caller
;--------------------------------------------------------
; code
;--------------------------------------------------------
	.area CSEG    (CODE)
;------------------------------------------------------------
;Allocation info for local variables in function 'wd'
;------------------------------------------------------------
;t             Allocated to registers r6 r7 
;s             Allocated to registers r5 
;------------------------------------------------------------
;	eeprom_dump_all.c:49: static unsigned char wd(void)
;	-----------------------------------------
;	 function wd
;	-----------------------------------------
_wd:
	ar7 = 0x07
	ar6 = 0x06
	ar5 = 0x05
	ar4 = 0x04
	ar3 = 0x03
	ar2 = 0x02
	ar1 = 0x01
	ar0 = 0x00
;	eeprom_dump_all.c:53: for (t = 0; t < 30000; t++) {
	mov	r6,#0x00
	mov	r7,#0x00
00104$:
;	eeprom_dump_all.c:54: s = I2CS;
	mov	dptr,#0xe678
	movx	a,@dptr
;	eeprom_dump_all.c:55: if (s & (ST_DONE | ST_BERR))
	mov	r5,a
	anl	a,#0x05
	jz	00105$
;	eeprom_dump_all.c:56: return s;
	mov	dpl, r5
	ret
00105$:
;	eeprom_dump_all.c:53: for (t = 0; t < 30000; t++) {
	inc	r6
	cjne	r6,#0x00,00130$
	inc	r7
00130$:
	clr	c
	mov	a,r6
	subb	a,#0x30
	mov	a,r7
	subb	a,#0x75
	jc	00104$
;	eeprom_dump_all.c:58: return s;
	mov	dpl, r5
;	eeprom_dump_all.c:59: }
	ret
;------------------------------------------------------------
;Allocation info for local variables in function 'stop'
;------------------------------------------------------------
;t             Allocated to registers r6 r7 
;------------------------------------------------------------
;	eeprom_dump_all.c:61: static void stop(void)
;	-----------------------------------------
;	 function stop
;	-----------------------------------------
_stop:
;	eeprom_dump_all.c:64: I2CS = ST_STOP;
	mov	dptr,#0xe678
	mov	a,#0x40
	movx	@dptr,a
;	eeprom_dump_all.c:65: for (t = 0; t < 30000; t++)
	mov	r6,#0x00
	mov	r7,#0x00
00104$:
;	eeprom_dump_all.c:66: if (!(I2CS & ST_STOP))
	mov	dptr,#0xe678
	movx	a,@dptr
	jnb	acc.6,00106$
;	eeprom_dump_all.c:65: for (t = 0; t < 30000; t++)
	inc	r6
	cjne	r6,#0x00,00124$
	inc	r7
00124$:
	clr	c
	mov	a,r6
	subb	a,#0x30
	mov	a,r7
	subb	a,#0x75
	jc	00104$
00106$:
;	eeprom_dump_all.c:68: }
	ret
;------------------------------------------------------------
;Allocation info for local variables in function 'dump'
;------------------------------------------------------------
;out           Allocated with name '_dump_PARM_2'
;addr8         Allocated to registers r7 
;i             Allocated to registers r5 r6 
;s             Allocated to registers r7 
;------------------------------------------------------------
;	eeprom_dump_all.c:71: static unsigned char dump(unsigned char addr8, __xdata unsigned char *out)
;	-----------------------------------------
;	 function dump
;	-----------------------------------------
_dump:
	mov	r7, dpl
;	eeprom_dump_all.c:76: for (i = 0; i < 256; i++)
	mov	r5,#0x00
	mov	r6,#0x00
00116$:
;	eeprom_dump_all.c:77: out[i] = 0xEE;                       /* "never read" sentinel */
	mov	a,r5
	add	a, _dump_PARM_2
	mov	dpl,a
	mov	a,r6
	addc	a, (_dump_PARM_2 + 1)
	mov	dph,a
	mov	a,#0xee
	movx	@dptr,a
;	eeprom_dump_all.c:76: for (i = 0; i < 256; i++)
	inc	r5
	cjne	r5,#0x00,00195$
	inc	r6
00195$:
	mov	a,#0x100 - 0x01
	add	a,r6
	jnc	00116$
;	eeprom_dump_all.c:79: I2CS  = ST_START;
	mov	dptr,#0xe678
	mov	a,#0x80
	movx	@dptr,a
;	eeprom_dump_all.c:80: I2DAT = addr8;                           /* device address, write dir */
	inc	dptr
	mov	a,r7
	movx	@dptr,a
;	eeprom_dump_all.c:81: s = wd();
	push	ar7
	lcall	_wd
	mov	r6, dpl
	pop	ar7
;	eeprom_dump_all.c:82: if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 1; }
	mov	a,r6
	jnb	acc.1,00102$
	mov	a,r6
	jnb	acc.2,00103$
00102$:
	lcall	_stop
	mov	dpl, #0x01
	ret
00103$:
;	eeprom_dump_all.c:84: I2DAT = 0x00;                            /* word address 0 -- pointer only */
	mov	dptr,#0xe679
	clr	a
	movx	@dptr,a
;	eeprom_dump_all.c:85: s = wd();
	push	ar7
	lcall	_wd
	mov	r6, dpl
	pop	ar7
;	eeprom_dump_all.c:86: if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 2; }
	mov	a,r6
	jnb	acc.1,00105$
	mov	a,r6
	jnb	acc.2,00106$
00105$:
	lcall	_stop
	mov	dpl, #0x02
	ret
00106$:
;	eeprom_dump_all.c:88: I2CS  = ST_START;                        /* REPEATED start, no STOP first */
	mov	dptr,#0xe678
	mov	a,#0x80
	movx	@dptr,a
;	eeprom_dump_all.c:89: I2DAT = (unsigned char)(addr8 | 1);      /* device address, read dir */
	orl	ar7,#0x01
	mov	dptr,#0xe679
	mov	a,r7
	movx	@dptr,a
;	eeprom_dump_all.c:90: s = wd();
	lcall	_wd
;	eeprom_dump_all.c:91: if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 3; }
	mov	a,dpl
	mov	r7,a
	jnb	acc.1,00108$
	mov	a,r7
	jnb	acc.2,00109$
00108$:
	lcall	_stop
	mov	dpl, #0x03
	ret
00109$:
;	eeprom_dump_all.c:93: (void)I2DAT;                             /* starts the first byte */
	mov	dptr,#0xe679
	movx	a,@dptr
;	eeprom_dump_all.c:94: for (i = 0; i < 256; i++) {
	mov	r6,#0x00
	mov	r7,#0x00
00118$:
;	eeprom_dump_all.c:95: if (i == 255)
	cjne	r6,#0xff,00112$
	cjne	r7,#0x00,00112$
;	eeprom_dump_all.c:96: I2CS = ST_LASTRD;                /* NACK the final byte */
	mov	dptr,#0xe678
	mov	a,#0x20
	movx	@dptr,a
00112$:
;	eeprom_dump_all.c:97: s = wd();
	push	ar7
	push	ar6
	lcall	_wd
	mov	r5, dpl
	pop	ar6
	pop	ar7
;	eeprom_dump_all.c:98: if (s & ST_BERR) { stop(); return 4; }
	mov	a,r5
	jnb	acc.2,00114$
	lcall	_stop
	mov	dpl, #0x04
	ret
00114$:
;	eeprom_dump_all.c:99: out[i] = I2DAT;
	mov	a,r6
	add	a, _dump_PARM_2
	mov	r4,a
	mov	a,r7
	addc	a, (_dump_PARM_2 + 1)
	mov	r5,a
	mov	dptr,#0xe679
	movx	a,@dptr
	mov	dpl,r4
	mov	dph,r5
	movx	@dptr,a
;	eeprom_dump_all.c:94: for (i = 0; i < 256; i++) {
	inc	r6
	cjne	r6,#0x00,00206$
	inc	r7
00206$:
	mov	a,#0x100 - 0x01
	add	a,r7
	jnc	00118$
;	eeprom_dump_all.c:101: stop();
	lcall	_stop
;	eeprom_dump_all.c:102: return 0;
	mov	dpl, #0x00
;	eeprom_dump_all.c:103: }
	ret
;------------------------------------------------------------
;Allocation info for local variables in function 'main'
;------------------------------------------------------------
;i             Allocated to registers r7 
;------------------------------------------------------------
;	eeprom_dump_all.c:105: void main(void)
;	-----------------------------------------
;	 function main
;	-----------------------------------------
_main:
;	eeprom_dump_all.c:108: for (i = 0; i < 8; i++) st[i] = 0;
	mov	r7,#0x00
00103$:
	mov	dpl,r7
	mov	dph,#(_st >> 8)
	clr	a
	movx	@dptr,a
	inc	r7
	cjne	r7,#0x08,00131$
00131$:
	jc	00103$
;	eeprom_dump_all.c:110: st[0] = dump(0xA2, d51);                 /* 7-bit 0x51 */
	mov	_dump_PARM_2,#_d51
	mov	(_dump_PARM_2 + 1),#(_d51 >> 8)
	mov	dpl, #0xa2
	lcall	_dump
	mov	r7, dpl
	mov	dptr,#_st
	mov	a,r7
	movx	@dptr,a
;	eeprom_dump_all.c:111: st[1] = dump(0xA4, d52);                 /* 7-bit 0x52 */
	mov	_dump_PARM_2,#_d52
	mov	(_dump_PARM_2 + 1),#(_d52 >> 8)
	mov	dpl, #0xa4
	lcall	_dump
	mov	r7, dpl
	mov	dptr,#(_st + 0x0001)
	mov	a,r7
	movx	@dptr,a
;	eeprom_dump_all.c:113: st[2] = 0xC0; st[3] = 0xDE; st[4] = 0xF1; st[5] = 0x35;
	mov	dptr,#(_st + 0x0002)
	mov	a,#0xc0
	movx	@dptr,a
	mov	dptr,#(_st + 0x0003)
	mov	a,#0xde
	movx	@dptr,a
	mov	dptr,#(_st + 0x0004)
	mov	a,#0xf1
	movx	@dptr,a
	mov	dptr,#(_st + 0x0005)
	mov	a,#0x35
	movx	@dptr,a
00106$:
;	eeprom_dump_all.c:116: }
	sjmp	00106$
	.area CSEG    (CODE)
	.area CONST   (CODE)
	.area XINIT   (CODE)
	.area CABS    (ABS,CODE)
