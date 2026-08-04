;--------------------------------------------------------
; File Created by SDCC : free open source ISO C Compiler
; Version 4.6.0 #16555 (Mac OS X ppc)
;--------------------------------------------------------
	.module i2c_scan
	
	.optsdcc -mmcs51 --model-small
;--------------------------------------------------------
; Public variables in this module
;--------------------------------------------------------
	.globl _main
	.globl _marker
	.globl _results
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
_results	=	0x0400
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
;Allocation info for local variables in function 'probe'
;------------------------------------------------------------
;a             Allocated to registers r7 
;t             Allocated to registers r5 r6 
;st            Allocated to registers r4 
;------------------------------------------------------------
;	i2c_scan.c:42: static void probe(unsigned char a)
;	-----------------------------------------
;	 function probe
;	-----------------------------------------
_probe:
	ar7 = 0x07
	ar6 = 0x06
	ar5 = 0x05
	ar4 = 0x04
	ar3 = 0x03
	ar2 = 0x02
	ar1 = 0x01
	ar0 = 0x00
	mov	r7, dpl
;	i2c_scan.c:50: I2CS  = ST_START;
	mov	dptr,#0xe678
	mov	a,#0x80
	movx	@dptr,a
;	i2c_scan.c:51: I2DAT = (unsigned char)((a << 1) | 1);   /* READ address, no data sent */
	mov	a,r7
	add	a,r7
	mov	r6,a
	orl	ar6,#0x01
	mov	dptr,#0xe679
	mov	a,r6
	movx	@dptr,a
;	i2c_scan.c:53: for (t = 0; t < 30000; t++) {
	mov	r5,#0x00
	mov	r6,#0x00
00113$:
;	i2c_scan.c:54: st = I2CS;
	mov	dptr,#0xe678
	movx	a,@dptr
;	i2c_scan.c:55: if (st & (ST_DONE | ST_BERR))
	mov	r4,a
	anl	a,#0x05
	jnz	00103$
;	i2c_scan.c:53: for (t = 0; t < 30000; t++) {
	inc	r5
	cjne	r5,#0x00,00182$
	inc	r6
00182$:
	clr	c
	mov	a,r5
	subb	a,#0x30
	mov	a,r6
	subb	a,#0x75
	jc	00113$
00103$:
;	i2c_scan.c:58: results[a] = st;                          /* captured before recovery */
	mov	dpl,r7
	mov	dph,#(_results >> 8)
	mov	a,r4
	movx	@dptr,a
;	i2c_scan.c:64: if ((st & ST_ACK) && !(st & ST_BERR)) {
	mov	a,r4
	jnb	acc.1,00108$
	mov	a,r4
	jb	acc.2,00108$
;	i2c_scan.c:65: I2CS = ST_LASTRD;
	mov	dptr,#0xe678
	mov	a,#0x20
	movx	@dptr,a
;	i2c_scan.c:66: (void)I2DAT;                          /* dummy read starts the byte */
	inc	dptr
	movx	a,@dptr
;	i2c_scan.c:67: for (t = 0; t < 30000; t++)
	mov	r6,#0x00
	mov	r7,#0x00
00115$:
;	i2c_scan.c:68: if (I2CS & (ST_DONE | ST_BERR))
	mov	dptr,#0xe678
	movx	a,@dptr
	anl	a,#0x05
	jnz	00106$
;	i2c_scan.c:67: for (t = 0; t < 30000; t++)
	inc	r6
	cjne	r6,#0x00,00188$
	inc	r7
00188$:
	clr	c
	mov	a,r6
	subb	a,#0x30
	mov	a,r7
	subb	a,#0x75
	jc	00115$
00106$:
;	i2c_scan.c:70: (void)I2DAT;                          /* collect it, freeing the bus */
	mov	dptr,#0xe679
	movx	a,@dptr
00108$:
;	i2c_scan.c:73: I2CS = ST_STOP;
	mov	dptr,#0xe678
	mov	a,#0x40
	movx	@dptr,a
;	i2c_scan.c:74: for (t = 0; t < 30000; t++)
	mov	r6,#0x00
	mov	r7,#0x00
00117$:
;	i2c_scan.c:75: if (!(I2CS & ST_STOP))
	mov	dptr,#0xe678
	movx	a,@dptr
	jnb	acc.6,00119$
;	i2c_scan.c:74: for (t = 0; t < 30000; t++)
	inc	r6
	cjne	r6,#0x00,00191$
	inc	r7
00191$:
	clr	c
	mov	a,r6
	subb	a,#0x30
	mov	a,r7
	subb	a,#0x75
	jc	00117$
00119$:
;	i2c_scan.c:77: }
	ret
;------------------------------------------------------------
;Allocation info for local variables in function 'main'
;------------------------------------------------------------
;a             Allocated to registers r7 
;------------------------------------------------------------
;	i2c_scan.c:79: void main(void)
;	-----------------------------------------
;	 function main
;	-----------------------------------------
_main:
;	i2c_scan.c:83: marker[0] = 0; marker[1] = 0; marker[2] = 0; marker[3] = 0;
	mov	dptr,#_marker
	clr	a
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0001)
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0002)
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0003)
	movx	@dptr,a
;	i2c_scan.c:84: for (a = 0; a < 128; a++)
	mov	r7,a
00104$:
;	i2c_scan.c:85: results[a] = 0xEE;                /* "never ran" sentinel */
	mov	dpl,r7
	mov	dph,#(_results >> 8)
	mov	a,#0xee
	movx	@dptr,a
;	i2c_scan.c:84: for (a = 0; a < 128; a++)
	inc	r7
	cjne	r7,#0x80,00149$
00149$:
	jc	00104$
;	i2c_scan.c:87: for (a = 0; a < 128; a++)
	mov	r7,#0x00
00106$:
;	i2c_scan.c:88: probe(a);
	mov	dpl, r7
	push	ar7
	lcall	_probe
	pop	ar7
;	i2c_scan.c:87: for (a = 0; a < 128; a++)
	inc	r7
	cjne	r7,#0x80,00151$
00151$:
	jc	00106$
;	i2c_scan.c:90: marker[0] = 0xC0; marker[1] = 0xDE;   /* scan complete */
	mov	dptr,#_marker
	mov	a,#0xc0
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0001)
	mov	a,#0xde
	movx	@dptr,a
;	i2c_scan.c:91: marker[2] = 0xF1; marker[3] = 0x35;
	mov	dptr,#(_marker + 0x0002)
	mov	a,#0xf1
	movx	@dptr,a
	mov	dptr,#(_marker + 0x0003)
	mov	a,#0x35
	movx	@dptr,a
00109$:
;	i2c_scan.c:95: }
	sjmp	00109$
	.area CSEG    (CODE)
	.area CONST   (CODE)
	.area XINIT   (CODE)
	.area CABS    (ABS,CODE)
