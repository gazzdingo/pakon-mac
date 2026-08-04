;--------------------------------------------------------
; File Created by SDCC : free open source ISO C Compiler
; Version 4.6.0 #16555 (Mac OS X ppc)
;--------------------------------------------------------
	.module mclr_window
	
	.optsdcc -mmcs51 --model-small
;--------------------------------------------------------
; Public variables in this module
;--------------------------------------------------------
	.globl _main
	.globl _tick
	.globl _nhit
	.globl _marker
	.globl _hits
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
_hits	=	0x0400
_marker	=	0x0480
_nhit	=	0x0500
_tick	=	0x0504
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
;	mclr_window.c:68: static unsigned char wait_done(void)
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
;	mclr_window.c:72: for (t = 0; t < 4000; t++) {          /* short: we want a TIGHT loop */
	mov	r6,#0x00
	mov	r7,#0x00
00104$:
;	mclr_window.c:73: s = I2CS;
	mov	dptr,#0xe678
	movx	a,@dptr
;	mclr_window.c:74: if (s & (ST_DONE | ST_BERR))
	mov	r5,a
	anl	a,#0x05
	jz	00105$
;	mclr_window.c:75: return s;
	mov	dpl, r5
	ret
00105$:
;	mclr_window.c:72: for (t = 0; t < 4000; t++) {          /* short: we want a TIGHT loop */
	inc	r6
	cjne	r6,#0x00,00130$
	inc	r7
00130$:
	clr	c
	mov	a,r6
	subb	a,#0xa0
	mov	a,r7
	subb	a,#0x0f
	jc	00104$
;	mclr_window.c:77: return s;
	mov	dpl, r5
;	mclr_window.c:78: }
	ret
;------------------------------------------------------------
;Allocation info for local variables in function 'probe'
;------------------------------------------------------------
;a             Allocated to registers r7 
;s             Allocated to registers r6 
;t             Allocated to registers r6 r7 
;------------------------------------------------------------
;	mclr_window.c:80: static void probe(unsigned char a)
;	-----------------------------------------
;	 function probe
;	-----------------------------------------
_probe:
	mov	r7, dpl
;	mclr_window.c:85: I2CS  = ST_START;
	mov	dptr,#0xe678
	mov	a,#0x80
	movx	@dptr,a
;	mclr_window.c:86: I2DAT = (unsigned char)((a << 1) | 1);   /* READ address, no data sent */
	mov	a,r7
	add	a,r7
	mov	r6,a
	orl	ar6,#0x01
	mov	dptr,#0xe679
	mov	a,r6
	movx	@dptr,a
;	mclr_window.c:87: s = wait_done();
	push	ar7
	lcall	_wait_done
	mov	r6, dpl
	pop	ar7
;	mclr_window.c:89: if ((s & ST_ACK) && !(s & ST_BERR)) {
	mov	a,r6
	jb	acc.1,00149$
	ljmp	00104$
00149$:
	mov	a,r6
	jnb	acc.2,00150$
	ljmp	00104$
00150$:
;	mclr_window.c:90: if (nhit < MAXHIT) {
	mov	dptr,#_nhit
	movx	a,@dptr
	mov	r4,a
	inc	dptr
	movx	a,@dptr
	mov	r5,a
	clr	c
	mov	a,r4
	subb	a,#0x30
	mov	a,r5
	subb	a,#0x00
	jc	00151$
	ljmp	00102$
00151$:
;	mclr_window.c:91: hits[nhit * 4 + 0] = a;
	mov	dptr,#_nhit
	movx	a,@dptr
	mov	r4,a
	inc	dptr
	movx	a,@dptr
	mov	r5,a
	mov	a,r4
	add	a,r4
	mov	r4,a
	mov	a,r5
	rlc	a
	mov	r5,a
	mov	a,r4
	add	a,r4
	mov	r4,a
	mov	a,r5
	rlc	a
	mov	r5,a
	mov	dpl,r4
	mov	a,#(_hits >> 8)
	add	a,r5
	mov	dph,a
	mov	a,r7
	movx	@dptr,a
;	mclr_window.c:92: hits[nhit * 4 + 1] = s;
	mov	dptr,#_nhit
	movx	a,@dptr
	mov	r5,a
	inc	dptr
	movx	a,@dptr
	mov	r7,a
	mov	a,r5
	add	a,r5
	mov	r5,a
	mov	a,r7
	rlc	a
	mov	r7,a
	mov	a,r5
	add	a,r5
	mov	r5,a
	mov	a,r7
	rlc	a
	mov	r7,a
	inc	r5
	cjne	r5,#0x00,00152$
	inc	r7
00152$:
	mov	dpl,r5
	mov	a,#(_hits >> 8)
	add	a,r7
	mov	dph,a
	mov	a,r6
	movx	@dptr,a
;	mclr_window.c:93: hits[nhit * 4 + 2] = (unsigned char)((tick >> 8) & 0xFF);
	mov	dptr,#_nhit
	movx	a,@dptr
	mov	r6,a
	inc	dptr
	movx	a,@dptr
	mov	r7,a
	mov	a,r6
	add	a,r6
	mov	r6,a
	mov	a,r7
	rlc	a
	mov	r7,a
	mov	a,r6
	add	a,r6
	mov	r6,a
	mov	a,r7
	rlc	a
	mov	r7,a
	mov	a,#0x02
	add	a, r6
	mov	r6,a
	clr	a
	addc	a, r7
	add	a,#(_hits >> 8)
	mov	r7,a
	mov	dptr,#_tick
	movx	a,@dptr
	inc	dptr
	movx	a,@dptr
	mov	r3,a
	inc	dptr
	movx	a,@dptr
	inc	dptr
	movx	a,@dptr
	mov	ar2,r3
	mov	dpl,r6
	mov	dph,r7
	mov	a,r2
	movx	@dptr,a
;	mclr_window.c:94: hits[nhit * 4 + 3] = (unsigned char)(tick & 0xFF);
	mov	dptr,#_nhit
	movx	a,@dptr
	mov	r6,a
	inc	dptr
	movx	a,@dptr
	mov	r7,a
	mov	a,r6
	add	a,r6
	mov	r6,a
	mov	a,r7
	rlc	a
	mov	r7,a
	mov	a,r6
	add	a,r6
	mov	r6,a
	mov	a,r7
	rlc	a
	mov	r7,a
	mov	a,#0x03
	add	a, r6
	mov	r6,a
	clr	a
	addc	a, r7
	add	a,#(_hits >> 8)
	mov	r7,a
	mov	dptr,#_tick
	movx	a,@dptr
	mov	dpl,r6
	mov	dph,r7
	movx	@dptr,a
;	mclr_window.c:95: nhit++;
	mov	dptr,#_nhit
	movx	a,@dptr
	mov	r6,a
	inc	dptr
	movx	a,@dptr
	mov	r7,a
	mov	dptr,#_nhit
	mov	a,#0x01
	add	a, r6
	movx	@dptr,a
	clr	a
	addc	a, r7
	inc	dptr
	movx	@dptr,a
00102$:
;	mclr_window.c:99: I2CS = ST_LASTRD;
	mov	dptr,#0xe678
	mov	a,#0x20
	movx	@dptr,a
;	mclr_window.c:100: (void)I2DAT;
	inc	dptr
	movx	a,@dptr
;	mclr_window.c:101: (void)wait_done();
	lcall	_wait_done
;	mclr_window.c:102: (void)I2DAT;
	mov	dptr,#0xe679
	movx	a,@dptr
00104$:
;	mclr_window.c:105: I2CS = ST_STOP;
	mov	dptr,#0xe678
	mov	a,#0x40
	movx	@dptr,a
;	mclr_window.c:106: for (t = 0; t < 4000; t++)
	mov	r6,#0x00
	mov	r7,#0x00
00109$:
;	mclr_window.c:107: if (!(I2CS & ST_STOP))
	mov	dptr,#0xe678
	movx	a,@dptr
	jnb	acc.6,00111$
;	mclr_window.c:106: for (t = 0; t < 4000; t++)
	inc	r6
	cjne	r6,#0x00,00154$
	inc	r7
00154$:
	clr	c
	mov	a,r6
	subb	a,#0xa0
	mov	a,r7
	subb	a,#0x0f
	jc	00109$
00111$:
;	mclr_window.c:109: }
	ret
;------------------------------------------------------------
;Allocation info for local variables in function 'main'
;------------------------------------------------------------
;i             Allocated to registers r7 
;------------------------------------------------------------
;	mclr_window.c:111: void main(void)
;	-----------------------------------------
;	 function main
;	-----------------------------------------
_main:
;	mclr_window.c:115: for (i = 0; i < MAXHIT * 4; i++)
	mov	r7,#0x00
00103$:
;	mclr_window.c:116: hits[i] = 0;
	mov	dpl,r7
	mov	dph,#(_hits >> 8)
	clr	a
	movx	@dptr,a
;	mclr_window.c:115: for (i = 0; i < MAXHIT * 4; i++)
	inc	r7
	cjne	r7,#0xc0,00131$
00131$:
	jc	00103$
;	mclr_window.c:117: nhit = 0;
	mov	dptr,#_nhit
	clr	a
	movx	@dptr,a
	inc	dptr
	movx	@dptr,a
;	mclr_window.c:118: tick = 0;
	mov	dptr,#_tick
	movx	@dptr,a
	inc	dptr
	movx	@dptr,a
	inc	dptr
	movx	@dptr,a
	inc	dptr
	movx	@dptr,a
;	mclr_window.c:119: marker[0] = 0xC0; marker[1] = 0xDE;
	mov	dptr,#_marker
	mov	a,#0xc0
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0001)
	mov	a,#0xde
	movx	@dptr,a
;	mclr_window.c:120: marker[2] = 0xF1; marker[3] = 0x35;
	mov	dptr,#(_marker + 0x0002)
	mov	a,#0xf1
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0003)
	mov	a,#0x35
	movx	@dptr,a
00105$:
;	mclr_window.c:125: probe(0x22);            /* PICM application */
	mov	dpl, #0x22
	lcall	_probe
;	mclr_window.c:126: probe(0x23);            /* PICM bootloader  */
	mov	dpl, #0x23
	lcall	_probe
;	mclr_window.c:127: tick++;
	mov	dptr,#_tick
	movx	a,@dptr
	mov	r4,a
	inc	dptr
	movx	a,@dptr
	mov	r5,a
	inc	dptr
	movx	a,@dptr
	mov	r6,a
	inc	dptr
	movx	a,@dptr
	mov	r7,a
	mov	dptr,#_tick
	mov	a,#0x01
	add	a, r4
	movx	@dptr,a
	clr	a
	addc	a, r5
	inc	dptr
	movx	@dptr,a
	clr	a
	addc	a, r6
	inc	dptr
	movx	@dptr,a
	clr	a
	addc	a, r7
	inc	dptr
	movx	@dptr,a
;	mclr_window.c:129: }
	sjmp	00105$
	.area CSEG    (CODE)
	.area CONST   (CODE)
	.area XINIT   (CODE)
	.area CABS    (ABS,CODE)
