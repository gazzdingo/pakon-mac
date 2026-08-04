                                      1 ;--------------------------------------------------------
                                      2 ; File Created by SDCC : free open source ISO C Compiler
                                      3 ; Version 4.6.0 #16555 (Mac OS X ppc)
                                      4 ;--------------------------------------------------------
                                      5 	.module eeprom_read
                                      6 	
                                      7 	.optsdcc -mmcs51 --model-small
                                      8 ;--------------------------------------------------------
                                      9 ; Public variables in this module
                                     10 ;--------------------------------------------------------
                                     11 	.globl _main
                                     12 	.globl _marker
                                     13 	.globl _st
                                     14 	.globl _buf
                                     15 ;--------------------------------------------------------
                                     16 ; special function registers
                                     17 ;--------------------------------------------------------
                                     18 	.area RSEG    (ABS,DATA)
      000000                         19 	.org 0x0000
                                     20 ;--------------------------------------------------------
                                     21 ; special function bits
                                     22 ;--------------------------------------------------------
                                     23 	.area RSEG    (ABS,DATA)
      000000                         24 	.org 0x0000
                                     25 ;--------------------------------------------------------
                                     26 ; overlayable register banks
                                     27 ;--------------------------------------------------------
                                     28 	.area REG_BANK_0	(REL,OVR,DATA)
      000000                         29 	.ds 8
                                     30 ;--------------------------------------------------------
                                     31 ; internal ram data
                                     32 ;--------------------------------------------------------
                                     33 	.area DSEG    (DATA)
                                     34 ;--------------------------------------------------------
                                     35 ; overlayable items in internal ram
                                     36 ;--------------------------------------------------------
                                     37 	.area	OSEG    (OVR,DATA)
                                     38 ;--------------------------------------------------------
                                     39 ; Stack segment in internal ram
                                     40 ;--------------------------------------------------------
                                     41 	.area SSEG
      000008                         42 __start__stack:
      000008                         43 	.ds	1
                                     44 
                                     45 ;--------------------------------------------------------
                                     46 ; indirectly addressable internal ram data
                                     47 ;--------------------------------------------------------
                                     48 	.area ISEG    (DATA)
                                     49 ;--------------------------------------------------------
                                     50 ; absolute internal ram data
                                     51 ;--------------------------------------------------------
                                     52 	.area IABS    (ABS,DATA)
                                     53 	.area IABS    (ABS,DATA)
                                     54 ;--------------------------------------------------------
                                     55 ; bit data
                                     56 ;--------------------------------------------------------
                                     57 	.area BSEG    (BIT)
                                     58 ;--------------------------------------------------------
                                     59 ; paged external ram data
                                     60 ;--------------------------------------------------------
                                     61 	.area PSEG    (PAG,XDATA)
                                     62 ;--------------------------------------------------------
                                     63 ; uninitialized external ram data
                                     64 ;--------------------------------------------------------
                                     65 	.area XSEG    (XDATA)
                           000400    66 _buf	=	0x0400
                           000420    67 _st	=	0x0420
                           000480    68 _marker	=	0x0480
                                     69 ;--------------------------------------------------------
                                     70 ; absolute external ram data
                                     71 ;--------------------------------------------------------
                                     72 	.area XABS    (ABS,XDATA)
                                     73 ;--------------------------------------------------------
                                     74 ; initialized external ram data
                                     75 ;--------------------------------------------------------
                                     76 	.area XISEG   (XDATA)
                                     77 	.area HOME    (CODE)
                                     78 	.area GSINIT0 (CODE)
                                     79 	.area GSINIT1 (CODE)
                                     80 	.area GSINIT2 (CODE)
                                     81 	.area GSINIT3 (CODE)
                                     82 	.area GSINIT4 (CODE)
                                     83 	.area GSINIT5 (CODE)
                                     84 	.area GSINIT  (CODE)
                                     85 	.area GSFINAL (CODE)
                                     86 	.area CSEG    (CODE)
                                     87 ;--------------------------------------------------------
                                     88 ; interrupt vector
                                     89 ;--------------------------------------------------------
                                     90 	.area HOME    (CODE)
      000000                         91 __interrupt_vect:
      000000 02 00 4E         [24]   92 	ljmp	__sdcc_gsinit_startup
                                     93 ; restartable atomic support routines
      000003                         94 	.ds	5
      000008                         95 sdcc_atomic_exchange_rollback_start::
      000008 00               [12]   96 	nop
      000009 00               [12]   97 	nop
      00000A                         98 sdcc_atomic_exchange_pdata_impl:
      00000A E2               [24]   99 	movx	a, @r0
      00000B FB               [12]  100 	mov	r3, a
      00000C EA               [12]  101 	mov	a, r2
      00000D F2               [24]  102 	movx	@r0, a
      00000E 80 2C            [24]  103 	sjmp	sdcc_atomic_exchange_exit
      000010 00               [12]  104 	nop
      000011 00               [12]  105 	nop
      000012                        106 sdcc_atomic_exchange_xdata_impl:
      000012 E0               [24]  107 	movx	a, @dptr
      000013 FB               [12]  108 	mov	r3, a
      000014 EA               [12]  109 	mov	a, r2
      000015 F0               [24]  110 	movx	@dptr, a
      000016 80 24            [24]  111 	sjmp	sdcc_atomic_exchange_exit
      000018                        112 sdcc_atomic_compare_exchange_idata_impl:
      000018 E6               [12]  113 	mov	a, @r0
      000019 B5 02 02         [24]  114 	cjne	a, ar2, .+#5
      00001C EB               [12]  115 	mov	a, r3
      00001D F6               [12]  116 	mov	@r0, a
      00001E 22               [24]  117 	ret
      00001F 00               [12]  118 	nop
      000020                        119 sdcc_atomic_compare_exchange_pdata_impl:
      000020 E2               [24]  120 	movx	a, @r0
      000021 B5 02 02         [24]  121 	cjne	a, ar2, .+#5
      000024 EB               [12]  122 	mov	a, r3
      000025 F2               [24]  123 	movx	@r0, a
      000026 22               [24]  124 	ret
      000027 00               [12]  125 	nop
      000028                        126 sdcc_atomic_compare_exchange_xdata_impl:
      000028 E0               [24]  127 	movx	a, @dptr
      000029 B5 02 02         [24]  128 	cjne	a, ar2, .+#5
      00002C EB               [12]  129 	mov	a, r3
      00002D F0               [24]  130 	movx	@dptr, a
      00002E 22               [24]  131 	ret
      00002F                        132 sdcc_atomic_exchange_rollback_end::
                                    133 
      00002F                        134 sdcc_atomic_exchange_gptr_impl::
      00002F 30 F6 E0         [24]  135 	jnb	b.6, sdcc_atomic_exchange_xdata_impl
      000032 A8 82            [24]  136 	mov	r0, dpl
      000034 20 F5 D3         [24]  137 	jb	b.5, sdcc_atomic_exchange_pdata_impl
      000037                        138 sdcc_atomic_exchange_idata_impl:
      000037 EA               [12]  139 	mov	a, r2
      000038 C6               [12]  140 	xch	a, @r0
      000039 F5 82            [12]  141 	mov	dpl, a
      00003B 22               [24]  142 	ret
      00003C                        143 sdcc_atomic_exchange_exit:
      00003C 8B 82            [24]  144 	mov	dpl, r3
      00003E 22               [24]  145 	ret
      00003F                        146 sdcc_atomic_compare_exchange_gptr_impl::
      00003F 30 F6 E6         [24]  147 	jnb	b.6, sdcc_atomic_compare_exchange_xdata_impl
      000042 A8 82            [24]  148 	mov	r0, dpl
      000044 20 F5 D9         [24]  149 	jb	b.5, sdcc_atomic_compare_exchange_pdata_impl
      000047 80 CF            [24]  150 	sjmp	sdcc_atomic_compare_exchange_idata_impl
                                    151 ;--------------------------------------------------------
                                    152 ; global & static initialisations
                                    153 ;--------------------------------------------------------
                                    154 	.area HOME    (CODE)
                                    155 	.area GSINIT  (CODE)
                                    156 	.area GSFINAL (CODE)
                                    157 	.area GSINIT  (CODE)
                                    158 	.globl __sdcc_gsinit_startup
                                    159 	.globl __sdcc_program_startup
                                    160 	.globl __start__stack
                                    161 	.globl __mcs51_genXINIT
                                    162 	.globl __mcs51_genXRAMCLEAR
                                    163 	.globl __mcs51_genRAMCLEAR
                                    164 	.area GSFINAL (CODE)
      0000A7 02 00 49         [24]  165 	ljmp	__sdcc_program_startup
                                    166 ;--------------------------------------------------------
                                    167 ; Home
                                    168 ;--------------------------------------------------------
                                    169 	.area HOME    (CODE)
                                    170 	.area HOME    (CODE)
      000049                        171 __sdcc_program_startup:
      000049 12 00 CB         [24]  172 	lcall	_main
      00004C                        173 __sdcc_program_exit:
      00004C 80 FE            [24]  174 	sjmp	.
                                    175 ;	return from main will return to caller
                                    176 ;--------------------------------------------------------
                                    177 ; code
                                    178 ;--------------------------------------------------------
                                    179 	.area CSEG    (CODE)
                                    180 ;------------------------------------------------------------
                                    181 ;Allocation info for local variables in function 'wait_done'
                                    182 ;------------------------------------------------------------
                                    183 ;t             Allocated to registers r6 r7 
                                    184 ;s             Allocated to registers r5 
                                    185 ;------------------------------------------------------------
                                    186 ;	eeprom_read.c:32: static unsigned char wait_done(void)
                                    187 ;	-----------------------------------------
                                    188 ;	 function wait_done
                                    189 ;	-----------------------------------------
      0000AA                        190 _wait_done:
                           000007   191 	ar7 = 0x07
                           000006   192 	ar6 = 0x06
                           000005   193 	ar5 = 0x05
                           000004   194 	ar4 = 0x04
                           000003   195 	ar3 = 0x03
                           000002   196 	ar2 = 0x02
                           000001   197 	ar1 = 0x01
                           000000   198 	ar0 = 0x00
                                    199 ;	eeprom_read.c:36: for (t = 0; t < 30000; t++) {
      0000AA 7E 00            [12]  200 	mov	r6,#0x00
      0000AC 7F 00            [12]  201 	mov	r7,#0x00
      0000AE                        202 00104$:
                                    203 ;	eeprom_read.c:37: s = I2CS;
      0000AE 90 E6 78         [24]  204 	mov	dptr,#0xe678
      0000B1 E0               [24]  205 	movx	a,@dptr
                                    206 ;	eeprom_read.c:38: if (s & (ST_DONE | ST_BERR))
      0000B2 FD               [12]  207 	mov	r5,a
      0000B3 54 05            [12]  208 	anl	a,#0x05
      0000B5 60 03            [24]  209 	jz	00105$
                                    210 ;	eeprom_read.c:39: return s;
      0000B7 8D 82            [24]  211 	mov	dpl, r5
      0000B9 22               [24]  212 	ret
      0000BA                        213 00105$:
                                    214 ;	eeprom_read.c:36: for (t = 0; t < 30000; t++) {
      0000BA 0E               [12]  215 	inc	r6
      0000BB BE 00 01         [24]  216 	cjne	r6,#0x00,00130$
      0000BE 0F               [12]  217 	inc	r7
      0000BF                        218 00130$:
      0000BF C3               [12]  219 	clr	c
      0000C0 EE               [12]  220 	mov	a,r6
      0000C1 94 30            [12]  221 	subb	a,#0x30
      0000C3 EF               [12]  222 	mov	a,r7
      0000C4 94 75            [12]  223 	subb	a,#0x75
      0000C6 40 E6            [24]  224 	jc	00104$
                                    225 ;	eeprom_read.c:41: return s;
      0000C8 8D 82            [24]  226 	mov	dpl, r5
                                    227 ;	eeprom_read.c:42: }
      0000CA 22               [24]  228 	ret
                                    229 ;------------------------------------------------------------
                                    230 ;Allocation info for local variables in function 'main'
                                    231 ;------------------------------------------------------------
                                    232 ;i             Allocated to registers r7 
                                    233 ;s             Allocated to registers r7 
                                    234 ;t             Allocated to registers r6 r7 
                                    235 ;------------------------------------------------------------
                                    236 ;	eeprom_read.c:44: void main(void)
                                    237 ;	-----------------------------------------
                                    238 ;	 function main
                                    239 ;	-----------------------------------------
      0000CB                        240 _main:
                                    241 ;	eeprom_read.c:49: for (i = 0; i < N; i++) buf[i] = 0xEE;
      0000CB 7F 00            [12]  242 	mov	r7,#0x00
      0000CD                        243 00119$:
      0000CD 8F 82            [24]  244 	mov	dpl,r7
      0000CF 75 83 04         [24]  245 	mov	dph,#(_buf >> 8)
      0000D2 74 EE            [12]  246 	mov	a,#0xee
      0000D4 F0               [24]  247 	movx	@dptr,a
      0000D5 0F               [12]  248 	inc	r7
      0000D6 BF 10 00         [24]  249 	cjne	r7,#0x10,00220$
      0000D9                        250 00220$:
      0000D9 40 F2            [24]  251 	jc	00119$
                                    252 ;	eeprom_read.c:50: st[0] = st[1] = st[2] = st[3] = 0;
      0000DB 90 04 23         [24]  253 	mov	dptr,#(_st + 0x0003)
      0000DE E4               [12]  254 	clr	a
      0000DF F0               [24]  255 	movx	@dptr,a
      0000E0 90 04 22         [24]  256 	mov	dptr,#(_st + 0x0002)
      0000E3 F0               [24]  257 	movx	@dptr,a
      0000E4 90 04 21         [24]  258 	mov	dptr,#(_st + 0x0001)
      0000E7 F0               [24]  259 	movx	@dptr,a
      0000E8 90 04 20         [24]  260 	mov	dptr,#_st
      0000EB F0               [24]  261 	movx	@dptr,a
                                    262 ;	eeprom_read.c:51: marker[0] = marker[1] = marker[2] = marker[3] = 0;
      0000EC 90 04 83         [24]  263 	mov	dptr,#(_marker + 0x0003)
      0000EF F0               [24]  264 	movx	@dptr,a
      0000F0 90 04 82         [24]  265 	mov	dptr,#(_marker + 0x0002)
      0000F3 F0               [24]  266 	movx	@dptr,a
      0000F4 90 04 81         [24]  267 	mov	dptr,#(_marker + 0x0001)
      0000F7 F0               [24]  268 	movx	@dptr,a
      0000F8 90 04 80         [24]  269 	mov	dptr,#_marker
      0000FB F0               [24]  270 	movx	@dptr,a
                                    271 ;	eeprom_read.c:54: I2CS  = ST_START;
      0000FC 90 E6 78         [24]  272 	mov	dptr,#0xe678
      0000FF 74 80            [12]  273 	mov	a,#0x80
      000101 F0               [24]  274 	movx	@dptr,a
                                    275 ;	eeprom_read.c:55: I2DAT = 0xA2;
      000102 A3               [24]  276 	inc	dptr
      000103 74 A2            [12]  277 	mov	a,#0xa2
      000105 F0               [24]  278 	movx	@dptr,a
                                    279 ;	eeprom_read.c:56: s = wait_done(); st[0] = s;
      000106 12 00 AA         [24]  280 	lcall	_wait_done
      000109 AF 82            [24]  281 	mov	r7, dpl
      00010B 90 04 20         [24]  282 	mov	dptr,#_st
      00010E EF               [12]  283 	mov	a,r7
      00010F F0               [24]  284 	movx	@dptr,a
                                    285 ;	eeprom_read.c:57: if (!(s & ST_ACK) || (s & ST_BERR)) { marker[0] = 0xE1; goto done; }
      000110 EF               [12]  286 	mov	a,r7
      000111 30 E1 04         [24]  287 	jnb	acc.1,00102$
      000114 EF               [12]  288 	mov	a,r7
      000115 30 E2 09         [24]  289 	jnb	acc.2,00103$
      000118                        290 00102$:
      000118 90 04 80         [24]  291 	mov	dptr,#_marker
      00011B 74 E1            [12]  292 	mov	a,#0xe1
      00011D F0               [24]  293 	movx	@dptr,a
      00011E 02 01 A0         [24]  294 	ljmp	00114$
      000121                        295 00103$:
                                    296 ;	eeprom_read.c:59: I2DAT = 0x00;                       /* word address 0 -- not data */
      000121 90 E6 79         [24]  297 	mov	dptr,#0xe679
      000124 E4               [12]  298 	clr	a
      000125 F0               [24]  299 	movx	@dptr,a
                                    300 ;	eeprom_read.c:60: s = wait_done(); st[1] = s;
      000126 12 00 AA         [24]  301 	lcall	_wait_done
      000129 AF 82            [24]  302 	mov	r7, dpl
      00012B 90 04 21         [24]  303 	mov	dptr,#(_st + 0x0001)
      00012E EF               [12]  304 	mov	a,r7
      00012F F0               [24]  305 	movx	@dptr,a
                                    306 ;	eeprom_read.c:61: if (!(s & ST_ACK) || (s & ST_BERR)) { marker[0] = 0xE2; goto done; }
      000130 EF               [12]  307 	mov	a,r7
      000131 30 E1 04         [24]  308 	jnb	acc.1,00105$
      000134 EF               [12]  309 	mov	a,r7
      000135 30 E2 08         [24]  310 	jnb	acc.2,00106$
      000138                        311 00105$:
      000138 90 04 80         [24]  312 	mov	dptr,#_marker
      00013B 74 E2            [12]  313 	mov	a,#0xe2
      00013D F0               [24]  314 	movx	@dptr,a
      00013E 80 60            [24]  315 	sjmp	00114$
      000140                        316 00106$:
                                    317 ;	eeprom_read.c:64: I2CS  = ST_START;
      000140 90 E6 78         [24]  318 	mov	dptr,#0xe678
      000143 74 80            [12]  319 	mov	a,#0x80
      000145 F0               [24]  320 	movx	@dptr,a
                                    321 ;	eeprom_read.c:65: I2DAT = 0xA3;
      000146 A3               [24]  322 	inc	dptr
      000147 74 A3            [12]  323 	mov	a,#0xa3
      000149 F0               [24]  324 	movx	@dptr,a
                                    325 ;	eeprom_read.c:66: s = wait_done(); st[2] = s;
      00014A 12 00 AA         [24]  326 	lcall	_wait_done
      00014D AF 82            [24]  327 	mov	r7, dpl
      00014F 90 04 22         [24]  328 	mov	dptr,#(_st + 0x0002)
      000152 EF               [12]  329 	mov	a,r7
      000153 F0               [24]  330 	movx	@dptr,a
                                    331 ;	eeprom_read.c:67: if (!(s & ST_ACK) || (s & ST_BERR)) { marker[0] = 0xE3; goto done; }
      000154 EF               [12]  332 	mov	a,r7
      000155 30 E1 04         [24]  333 	jnb	acc.1,00108$
      000158 EF               [12]  334 	mov	a,r7
      000159 30 E2 08         [24]  335 	jnb	acc.2,00109$
      00015C                        336 00108$:
      00015C 90 04 80         [24]  337 	mov	dptr,#_marker
      00015F 74 E3            [12]  338 	mov	a,#0xe3
      000161 F0               [24]  339 	movx	@dptr,a
      000162 80 3C            [24]  340 	sjmp	00114$
      000164                        341 00109$:
                                    342 ;	eeprom_read.c:69: (void)I2DAT;                        /* starts the first byte */
      000164 90 E6 79         [24]  343 	mov	dptr,#0xe679
      000167 E0               [24]  344 	movx	a,@dptr
                                    345 ;	eeprom_read.c:70: for (i = 0; i < N; i++) {
      000168 7F 00            [12]  346 	mov	r7,#0x00
      00016A                        347 00121$:
                                    348 ;	eeprom_read.c:71: if (i == N - 1)
      00016A BF 0F 06         [24]  349 	cjne	r7,#0x0f,00112$
                                    350 ;	eeprom_read.c:72: I2CS = ST_LASTRD;
      00016D 90 E6 78         [24]  351 	mov	dptr,#0xe678
      000170 74 20            [12]  352 	mov	a,#0x20
      000172 F0               [24]  353 	movx	@dptr,a
      000173                        354 00112$:
                                    355 ;	eeprom_read.c:73: s = wait_done();
      000173 C0 07            [24]  356 	push	ar7
      000175 12 00 AA         [24]  357 	lcall	_wait_done
      000178 AE 82            [24]  358 	mov	r6, dpl
      00017A D0 07            [24]  359 	pop	ar7
                                    360 ;	eeprom_read.c:74: buf[i] = I2DAT;
      00017C 8F 04            [24]  361 	mov	ar4,r7
      00017E 7D 04            [12]  362 	mov	r5,#(_buf >> 8)
      000180 90 E6 79         [24]  363 	mov	dptr,#0xe679
      000183 E0               [24]  364 	movx	a,@dptr
      000184 8C 82            [24]  365 	mov	dpl,r4
      000186 8D 83            [24]  366 	mov	dph,r5
      000188 F0               [24]  367 	movx	@dptr,a
                                    368 ;	eeprom_read.c:70: for (i = 0; i < N; i++) {
      000189 0F               [12]  369 	inc	r7
      00018A BF 10 00         [24]  370 	cjne	r7,#0x10,00230$
      00018D                        371 00230$:
      00018D 40 DB            [24]  372 	jc	00121$
                                    373 ;	eeprom_read.c:76: st[3] = s;
      00018F 90 04 23         [24]  374 	mov	dptr,#(_st + 0x0003)
      000192 EE               [12]  375 	mov	a,r6
      000193 F0               [24]  376 	movx	@dptr,a
                                    377 ;	eeprom_read.c:77: marker[0] = 0xC0; marker[1] = 0xDE;
      000194 90 04 80         [24]  378 	mov	dptr,#_marker
      000197 74 C0            [12]  379 	mov	a,#0xc0
      000199 F0               [24]  380 	movx	@dptr,a
      00019A 90 04 81         [24]  381 	mov	dptr,#(_marker + 0x0001)
      00019D 74 DE            [12]  382 	mov	a,#0xde
      00019F F0               [24]  383 	movx	@dptr,a
                                    384 ;	eeprom_read.c:79: done:
      0001A0                        385 00114$:
                                    386 ;	eeprom_read.c:80: I2CS = ST_STOP;
      0001A0 90 E6 78         [24]  387 	mov	dptr,#0xe678
      0001A3 74 40            [12]  388 	mov	a,#0x40
      0001A5 F0               [24]  389 	movx	@dptr,a
                                    390 ;	eeprom_read.c:81: for (t = 0; t < 30000; t++)
      0001A6 7E 00            [12]  391 	mov	r6,#0x00
      0001A8 7F 00            [12]  392 	mov	r7,#0x00
      0001AA                        393 00123$:
                                    394 ;	eeprom_read.c:82: if (!(I2CS & ST_STOP))
      0001AA 90 E6 78         [24]  395 	mov	dptr,#0xe678
      0001AD E0               [24]  396 	movx	a,@dptr
      0001AE 30 E6 0E         [24]  397 	jnb	acc.6,00117$
                                    398 ;	eeprom_read.c:81: for (t = 0; t < 30000; t++)
      0001B1 0E               [12]  399 	inc	r6
      0001B2 BE 00 01         [24]  400 	cjne	r6,#0x00,00233$
      0001B5 0F               [12]  401 	inc	r7
      0001B6                        402 00233$:
      0001B6 C3               [12]  403 	clr	c
      0001B7 EE               [12]  404 	mov	a,r6
      0001B8 94 30            [12]  405 	subb	a,#0x30
      0001BA EF               [12]  406 	mov	a,r7
      0001BB 94 75            [12]  407 	subb	a,#0x75
      0001BD 40 EB            [24]  408 	jc	00123$
      0001BF                        409 00117$:
                                    410 ;	eeprom_read.c:84: marker[2] = 0xF1; marker[3] = 0x35;
      0001BF 90 04 82         [24]  411 	mov	dptr,#(_marker + 0x0002)
      0001C2 74 F1            [12]  412 	mov	a,#0xf1
      0001C4 F0               [24]  413 	movx	@dptr,a
      0001C5 90 04 83         [24]  414 	mov	dptr,#(_marker + 0x0003)
      0001C8 74 35            [12]  415 	mov	a,#0x35
      0001CA F0               [24]  416 	movx	@dptr,a
      0001CB                        417 00126$:
                                    418 ;	eeprom_read.c:88: }
      0001CB 80 FE            [24]  419 	sjmp	00126$
                                    420 	.area CSEG    (CODE)
                                    421 	.area CONST   (CODE)
                                    422 	.area XINIT   (CODE)
                                    423 	.area CABS    (ABS,CODE)
