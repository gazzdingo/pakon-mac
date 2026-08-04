;--------------------------------------------------------
; File Created by SDCC : free open source ISO C Compiler
; Version 4.6.0 #16555 (Mac OS X ppc)
;--------------------------------------------------------
	.module eeprom_read
	
	.optsdcc -mmcs51 --model-small
;--------------------------------------------------------
; Public variables in this module
;--------------------------------------------------------
	.globl _main
	.globl _marker
	.globl _st
	.globl _buf
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
;--------------------------------------------------------
; overlayable items in internal ram
;--------------------------------------------------------
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
_buf	=	0x0400
_st	=	0x0420
_marker	=	0x0480
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
;Allocation info for local variables in function 'wait_done'
;------------------------------------------------------------
;t             Allocated to registers r6 r7 
;s             Allocated to registers r5 
;------------------------------------------------------------
;	eeprom_read.c:32: static unsigned char wait_done(void)
;	-----------------------------------------
;	 function wait_done
;	-----------------------------------------
_wait_done:
	ar7 = 0x07
	ar6 = 0x06
	ar5 = 0x05
	ar4 = 0x04
	ar3 = 0x03
	ar2 = 0x02
	ar1 = 0x01
	ar0 = 0x00
;	eeprom_read.c:36: for (t = 0; t < 30000; t++) {
	mov	r6,#0x00
	mov	r7,#0x00
00104$:
;	eeprom_read.c:37: s = I2CS;
	mov	dptr,#0xe678
	movx	a,@dptr
;	eeprom_read.c:38: if (s & (ST_DONE | ST_BERR))
	mov	r5,a
	anl	a,#0x05
	jz	00105$
;	eeprom_read.c:39: return s;
	mov	dpl, r5
	ret
00105$:
;	eeprom_read.c:36: for (t = 0; t < 30000; t++) {
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
;	eeprom_read.c:41: return s;
	mov	dpl, r5
;	eeprom_read.c:42: }
	ret
;------------------------------------------------------------
;Allocation info for local variables in function 'main'
;------------------------------------------------------------
;i             Allocated to registers r7 
;s             Allocated to registers r7 
;t             Allocated to registers r6 r7 
;------------------------------------------------------------
;	eeprom_read.c:44: void main(void)
;	-----------------------------------------
;	 function main
;	-----------------------------------------
_main:
;	eeprom_read.c:49: for (i = 0; i < N; i++) buf[i] = 0xEE;
	mov	r7,#0x00
00119$:
	mov	dpl,r7
	mov	dph,#(_buf >> 8)
	mov	a,#0xee
	movx	@dptr,a
	inc	r7
	cjne	r7,#0x10,00220$
00220$:
	jc	00119$
;	eeprom_read.c:50: st[0] = st[1] = st[2] = st[3] = 0;
	mov	dptr,#(_st + 0x0003)
	clr	a
	movx	@dptr,a
	mov	dptr,#(_st + 0x0002)
	movx	@dptr,a
	mov	dptr,#(_st + 0x0001)
	movx	@dptr,a
	mov	dptr,#_st
	movx	@dptr,a
;	eeprom_read.c:51: marker[0] = marker[1] = marker[2] = marker[3] = 0;
	mov	dptr,#(_marker + 0x0003)
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0002)
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0001)
	movx	@dptr,a
	mov	dptr,#_marker
	movx	@dptr,a
;	eeprom_read.c:54: I2CS  = ST_START;
	mov	dptr,#0xe678
	mov	a,#0x80
	movx	@dptr,a
;	eeprom_read.c:55: I2DAT = 0xA2;
	inc	dptr
	mov	a,#0xa2
	movx	@dptr,a
;	eeprom_read.c:56: s = wait_done(); st[0] = s;
	lcall	_wait_done
	mov	r7, dpl
	mov	dptr,#_st
	mov	a,r7
	movx	@dptr,a
;	eeprom_read.c:57: if (!(s & ST_ACK) || (s & ST_BERR)) { marker[0] = 0xE1; goto done; }
	mov	a,r7
	jnb	acc.1,00102$
	mov	a,r7
	jnb	acc.2,00103$
00102$:
	mov	dptr,#_marker
	mov	a,#0xe1
	movx	@dptr,a
	ljmp	00114$
00103$:
;	eeprom_read.c:59: I2DAT = 0x00;                       /* word address 0 -- not data */
	mov	dptr,#0xe679
	clr	a
	movx	@dptr,a
;	eeprom_read.c:60: s = wait_done(); st[1] = s;
	lcall	_wait_done
	mov	r7, dpl
	mov	dptr,#(_st + 0x0001)
	mov	a,r7
	movx	@dptr,a
;	eeprom_read.c:61: if (!(s & ST_ACK) || (s & ST_BERR)) { marker[0] = 0xE2; goto done; }
	mov	a,r7
	jnb	acc.1,00105$
	mov	a,r7
	jnb	acc.2,00106$
00105$:
	mov	dptr,#_marker
	mov	a,#0xe2
	movx	@dptr,a
	sjmp	00114$
00106$:
;	eeprom_read.c:64: I2CS  = ST_START;
	mov	dptr,#0xe678
	mov	a,#0x80
	movx	@dptr,a
;	eeprom_read.c:65: I2DAT = 0xA3;
	inc	dptr
	mov	a,#0xa3
	movx	@dptr,a
;	eeprom_read.c:66: s = wait_done(); st[2] = s;
	lcall	_wait_done
	mov	r7, dpl
	mov	dptr,#(_st + 0x0002)
	mov	a,r7
	movx	@dptr,a
;	eeprom_read.c:67: if (!(s & ST_ACK) || (s & ST_BERR)) { marker[0] = 0xE3; goto done; }
	mov	a,r7
	jnb	acc.1,00108$
	mov	a,r7
	jnb	acc.2,00109$
00108$:
	mov	dptr,#_marker
	mov	a,#0xe3
	movx	@dptr,a
	sjmp	00114$
00109$:
;	eeprom_read.c:69: (void)I2DAT;                        /* starts the first byte */
	mov	dptr,#0xe679
	movx	a,@dptr
;	eeprom_read.c:70: for (i = 0; i < N; i++) {
	mov	r7,#0x00
00121$:
;	eeprom_read.c:71: if (i == N - 1)
	cjne	r7,#0x0f,00112$
;	eeprom_read.c:72: I2CS = ST_LASTRD;
	mov	dptr,#0xe678
	mov	a,#0x20
	movx	@dptr,a
00112$:
;	eeprom_read.c:73: s = wait_done();
	push	ar7
	lcall	_wait_done
	mov	r6, dpl
	pop	ar7
;	eeprom_read.c:74: buf[i] = I2DAT;
	mov	ar4,r7
	mov	r5,#(_buf >> 8)
	mov	dptr,#0xe679
	movx	a,@dptr
	mov	dpl,r4
	mov	dph,r5
	movx	@dptr,a
;	eeprom_read.c:70: for (i = 0; i < N; i++) {
	inc	r7
	cjne	r7,#0x10,00230$
00230$:
	jc	00121$
;	eeprom_read.c:76: st[3] = s;
	mov	dptr,#(_st + 0x0003)
	mov	a,r6
	movx	@dptr,a
;	eeprom_read.c:77: marker[0] = 0xC0; marker[1] = 0xDE;
	mov	dptr,#_marker
	mov	a,#0xc0
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0001)
	mov	a,#0xde
	movx	@dptr,a
;	eeprom_read.c:79: done:
00114$:
;	eeprom_read.c:80: I2CS = ST_STOP;
	mov	dptr,#0xe678
	mov	a,#0x40
	movx	@dptr,a
;	eeprom_read.c:81: for (t = 0; t < 30000; t++)
	mov	r6,#0x00
	mov	r7,#0x00
00123$:
;	eeprom_read.c:82: if (!(I2CS & ST_STOP))
	mov	dptr,#0xe678
	movx	a,@dptr
	jnb	acc.6,00117$
;	eeprom_read.c:81: for (t = 0; t < 30000; t++)
	inc	r6
	cjne	r6,#0x00,00233$
	inc	r7
00233$:
	clr	c
	mov	a,r6
	subb	a,#0x30
	mov	a,r7
	subb	a,#0x75
	jc	00123$
00117$:
;	eeprom_read.c:84: marker[2] = 0xF1; marker[3] = 0x35;
	mov	dptr,#(_marker + 0x0002)
	mov	a,#0xf1
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0003)
	mov	a,#0x35
	movx	@dptr,a
00126$:
;	eeprom_read.c:88: }
	sjmp	00126$
	.area CSEG    (CODE)
	.area CONST   (CODE)
	.area XINIT   (CODE)
	.area CABS    (ABS,CODE)
