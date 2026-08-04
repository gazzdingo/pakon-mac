                                      1 ;--------------------------------------------------------
                                      2 ; File Created by SDCC : free open source ISO C Compiler
                                      3 ; Version 4.6.0 #16555 (Mac OS X ppc)
                                      4 ;--------------------------------------------------------
                                      5 	.module mclr_window
                                      6 	
                                      7 	.optsdcc -mmcs51 --model-small
                                      8 ;--------------------------------------------------------
                                      9 ; Public variables in this module
                                     10 ;--------------------------------------------------------
                                     11 	.globl _main
                                     12 	.globl _tick
                                     13 	.globl _nhit
                                     14 	.globl _marker
                                     15 	.globl _hits
                                     16 ;--------------------------------------------------------
                                     17 ; special function registers
                                     18 ;--------------------------------------------------------
                                     19 	.area RSEG    (ABS,DATA)
      000000                         20 	.org 0x0000
                                     21 ;--------------------------------------------------------
                                     22 ; special function bits
                                     23 ;--------------------------------------------------------
                                     24 	.area RSEG    (ABS,DATA)
      000000                         25 	.org 0x0000
                                     26 ;--------------------------------------------------------
                                     27 ; overlayable register banks
                                     28 ;--------------------------------------------------------
                                     29 	.area REG_BANK_0	(REL,OVR,DATA)
      000000                         30 	.ds 8
                                     31 ;--------------------------------------------------------
                                     32 ; internal ram data
                                     33 ;--------------------------------------------------------
                                     34 	.area DSEG    (DATA)
                                     35 ;--------------------------------------------------------
                                     36 ; overlayable items in internal ram
                                     37 ;--------------------------------------------------------
                                     38 	.area	OSEG    (OVR,DATA)
                                     39 ;--------------------------------------------------------
                                     40 ; Stack segment in internal ram
                                     41 ;--------------------------------------------------------
                                     42 	.area SSEG
      000008                         43 __start__stack:
      000008                         44 	.ds	1
                                     45 
                                     46 ;--------------------------------------------------------
                                     47 ; indirectly addressable internal ram data
                                     48 ;--------------------------------------------------------
                                     49 	.area ISEG    (DATA)
                                     50 ;--------------------------------------------------------
                                     51 ; absolute internal ram data
                                     52 ;--------------------------------------------------------
                                     53 	.area IABS    (ABS,DATA)
                                     54 	.area IABS    (ABS,DATA)
                                     55 ;--------------------------------------------------------
                                     56 ; bit data
                                     57 ;--------------------------------------------------------
                                     58 	.area BSEG    (BIT)
                                     59 ;--------------------------------------------------------
                                     60 ; paged external ram data
                                     61 ;--------------------------------------------------------
                                     62 	.area PSEG    (PAG,XDATA)
                                     63 ;--------------------------------------------------------
                                     64 ; uninitialized external ram data
                                     65 ;--------------------------------------------------------
                                     66 	.area XSEG    (XDATA)
                           000400    67 _hits	=	0x0400
                           000480    68 _marker	=	0x0480
                           000500    69 _nhit	=	0x0500
                           000504    70 _tick	=	0x0504
                                     71 ;--------------------------------------------------------
                                     72 ; absolute external ram data
                                     73 ;--------------------------------------------------------
                                     74 	.area XABS    (ABS,XDATA)
                                     75 ;--------------------------------------------------------
                                     76 ; initialized external ram data
                                     77 ;--------------------------------------------------------
                                     78 	.area XISEG   (XDATA)
                                     79 	.area HOME    (CODE)
                                     80 	.area GSINIT0 (CODE)
                                     81 	.area GSINIT1 (CODE)
                                     82 	.area GSINIT2 (CODE)
                                     83 	.area GSINIT3 (CODE)
                                     84 	.area GSINIT4 (CODE)
                                     85 	.area GSINIT5 (CODE)
                                     86 	.area GSINIT  (CODE)
                                     87 	.area GSFINAL (CODE)
                                     88 	.area CSEG    (CODE)
                                     89 ;--------------------------------------------------------
                                     90 ; interrupt vector
                                     91 ;--------------------------------------------------------
                                     92 	.area HOME    (CODE)
      000000                         93 __interrupt_vect:
      000000 02 00 4E         [24]   94 	ljmp	__sdcc_gsinit_startup
                                     95 ; restartable atomic support routines
      000003                         96 	.ds	5
      000008                         97 sdcc_atomic_exchange_rollback_start::
      000008 00               [12]   98 	nop
      000009 00               [12]   99 	nop
      00000A                        100 sdcc_atomic_exchange_pdata_impl:
      00000A E2               [24]  101 	movx	a, @r0
      00000B FB               [12]  102 	mov	r3, a
      00000C EA               [12]  103 	mov	a, r2
      00000D F2               [24]  104 	movx	@r0, a
      00000E 80 2C            [24]  105 	sjmp	sdcc_atomic_exchange_exit
      000010 00               [12]  106 	nop
      000011 00               [12]  107 	nop
      000012                        108 sdcc_atomic_exchange_xdata_impl:
      000012 E0               [24]  109 	movx	a, @dptr
      000013 FB               [12]  110 	mov	r3, a
      000014 EA               [12]  111 	mov	a, r2
      000015 F0               [24]  112 	movx	@dptr, a
      000016 80 24            [24]  113 	sjmp	sdcc_atomic_exchange_exit
      000018                        114 sdcc_atomic_compare_exchange_idata_impl:
      000018 E6               [12]  115 	mov	a, @r0
      000019 B5 02 02         [24]  116 	cjne	a, ar2, .+#5
      00001C EB               [12]  117 	mov	a, r3
      00001D F6               [12]  118 	mov	@r0, a
      00001E 22               [24]  119 	ret
      00001F 00               [12]  120 	nop
      000020                        121 sdcc_atomic_compare_exchange_pdata_impl:
      000020 E2               [24]  122 	movx	a, @r0
      000021 B5 02 02         [24]  123 	cjne	a, ar2, .+#5
      000024 EB               [12]  124 	mov	a, r3
      000025 F2               [24]  125 	movx	@r0, a
      000026 22               [24]  126 	ret
      000027 00               [12]  127 	nop
      000028                        128 sdcc_atomic_compare_exchange_xdata_impl:
      000028 E0               [24]  129 	movx	a, @dptr
      000029 B5 02 02         [24]  130 	cjne	a, ar2, .+#5
      00002C EB               [12]  131 	mov	a, r3
      00002D F0               [24]  132 	movx	@dptr, a
      00002E 22               [24]  133 	ret
      00002F                        134 sdcc_atomic_exchange_rollback_end::
                                    135 
      00002F                        136 sdcc_atomic_exchange_gptr_impl::
      00002F 30 F6 E0         [24]  137 	jnb	b.6, sdcc_atomic_exchange_xdata_impl
      000032 A8 82            [24]  138 	mov	r0, dpl
      000034 20 F5 D3         [24]  139 	jb	b.5, sdcc_atomic_exchange_pdata_impl
      000037                        140 sdcc_atomic_exchange_idata_impl:
      000037 EA               [12]  141 	mov	a, r2
      000038 C6               [12]  142 	xch	a, @r0
      000039 F5 82            [12]  143 	mov	dpl, a
      00003B 22               [24]  144 	ret
      00003C                        145 sdcc_atomic_exchange_exit:
      00003C 8B 82            [24]  146 	mov	dpl, r3
      00003E 22               [24]  147 	ret
      00003F                        148 sdcc_atomic_compare_exchange_gptr_impl::
      00003F 30 F6 E6         [24]  149 	jnb	b.6, sdcc_atomic_compare_exchange_xdata_impl
      000042 A8 82            [24]  150 	mov	r0, dpl
      000044 20 F5 D9         [24]  151 	jb	b.5, sdcc_atomic_compare_exchange_pdata_impl
      000047 80 CF            [24]  152 	sjmp	sdcc_atomic_compare_exchange_idata_impl
                                    153 ;--------------------------------------------------------
                                    154 ; global & static initialisations
                                    155 ;--------------------------------------------------------
                                    156 	.area HOME    (CODE)
                                    157 	.area GSINIT  (CODE)
                                    158 	.area GSFINAL (CODE)
                                    159 	.area GSINIT  (CODE)
                                    160 	.globl __sdcc_gsinit_startup
                                    161 	.globl __sdcc_program_startup
                                    162 	.globl __start__stack
                                    163 	.globl __mcs51_genXINIT
                                    164 	.globl __mcs51_genXRAMCLEAR
                                    165 	.globl __mcs51_genRAMCLEAR
                                    166 	.area GSFINAL (CODE)
      0000A7 02 00 49         [24]  167 	ljmp	__sdcc_program_startup
                                    168 ;--------------------------------------------------------
                                    169 ; Home
                                    170 ;--------------------------------------------------------
                                    171 	.area HOME    (CODE)
                                    172 	.area HOME    (CODE)
      000049                        173 __sdcc_program_startup:
      000049 12 01 E0         [24]  174 	lcall	_main
      00004C                        175 __sdcc_program_exit:
      00004C 80 FE            [24]  176 	sjmp	.
                                    177 ;	return from main will return to caller
                                    178 ;--------------------------------------------------------
                                    179 ; code
                                    180 ;--------------------------------------------------------
                                    181 	.area CSEG    (CODE)
                                    182 ;------------------------------------------------------------
                                    183 ;Allocation info for local variables in function 'wait_done'
                                    184 ;------------------------------------------------------------
                                    185 ;t             Allocated to registers r6 r7 
                                    186 ;s             Allocated to registers r5 
                                    187 ;------------------------------------------------------------
                                    188 ;	mclr_window.c:68: static unsigned char wait_done(void)
                                    189 ;	-----------------------------------------
                                    190 ;	 function wait_done
                                    191 ;	-----------------------------------------
      0000AA                        192 _wait_done:
                           000007   193 	ar7 = 0x07
                           000006   194 	ar6 = 0x06
                           000005   195 	ar5 = 0x05
                           000004   196 	ar4 = 0x04
                           000003   197 	ar3 = 0x03
                           000002   198 	ar2 = 0x02
                           000001   199 	ar1 = 0x01
                           000000   200 	ar0 = 0x00
                                    201 ;	mclr_window.c:72: for (t = 0; t < 4000; t++) {          /* short: we want a TIGHT loop */
      0000AA 7E 00            [12]  202 	mov	r6,#0x00
      0000AC 7F 00            [12]  203 	mov	r7,#0x00
      0000AE                        204 00104$:
                                    205 ;	mclr_window.c:73: s = I2CS;
      0000AE 90 E6 78         [24]  206 	mov	dptr,#0xe678
      0000B1 E0               [24]  207 	movx	a,@dptr
                                    208 ;	mclr_window.c:74: if (s & (ST_DONE | ST_BERR))
      0000B2 FD               [12]  209 	mov	r5,a
      0000B3 54 05            [12]  210 	anl	a,#0x05
      0000B5 60 03            [24]  211 	jz	00105$
                                    212 ;	mclr_window.c:75: return s;
      0000B7 8D 82            [24]  213 	mov	dpl, r5
      0000B9 22               [24]  214 	ret
      0000BA                        215 00105$:
                                    216 ;	mclr_window.c:72: for (t = 0; t < 4000; t++) {          /* short: we want a TIGHT loop */
      0000BA 0E               [12]  217 	inc	r6
      0000BB BE 00 01         [24]  218 	cjne	r6,#0x00,00130$
      0000BE 0F               [12]  219 	inc	r7
      0000BF                        220 00130$:
      0000BF C3               [12]  221 	clr	c
      0000C0 EE               [12]  222 	mov	a,r6
      0000C1 94 A0            [12]  223 	subb	a,#0xa0
      0000C3 EF               [12]  224 	mov	a,r7
      0000C4 94 0F            [12]  225 	subb	a,#0x0f
      0000C6 40 E6            [24]  226 	jc	00104$
                                    227 ;	mclr_window.c:77: return s;
      0000C8 8D 82            [24]  228 	mov	dpl, r5
                                    229 ;	mclr_window.c:78: }
      0000CA 22               [24]  230 	ret
                                    231 ;------------------------------------------------------------
                                    232 ;Allocation info for local variables in function 'probe'
                                    233 ;------------------------------------------------------------
                                    234 ;a             Allocated to registers r7 
                                    235 ;s             Allocated to registers r6 
                                    236 ;t             Allocated to registers r6 r7 
                                    237 ;------------------------------------------------------------
                                    238 ;	mclr_window.c:80: static void probe(unsigned char a)
                                    239 ;	-----------------------------------------
                                    240 ;	 function probe
                                    241 ;	-----------------------------------------
      0000CB                        242 _probe:
      0000CB AF 82            [24]  243 	mov	r7, dpl
                                    244 ;	mclr_window.c:85: I2CS  = ST_START;
      0000CD 90 E6 78         [24]  245 	mov	dptr,#0xe678
      0000D0 74 80            [12]  246 	mov	a,#0x80
      0000D2 F0               [24]  247 	movx	@dptr,a
                                    248 ;	mclr_window.c:86: I2DAT = (unsigned char)((a << 1) | 1);   /* READ address, no data sent */
      0000D3 EF               [12]  249 	mov	a,r7
      0000D4 2F               [12]  250 	add	a,r7
      0000D5 FE               [12]  251 	mov	r6,a
      0000D6 43 06 01         [24]  252 	orl	ar6,#0x01
      0000D9 90 E6 79         [24]  253 	mov	dptr,#0xe679
      0000DC EE               [12]  254 	mov	a,r6
      0000DD F0               [24]  255 	movx	@dptr,a
                                    256 ;	mclr_window.c:87: s = wait_done();
      0000DE C0 07            [24]  257 	push	ar7
      0000E0 12 00 AA         [24]  258 	lcall	_wait_done
      0000E3 AE 82            [24]  259 	mov	r6, dpl
      0000E5 D0 07            [24]  260 	pop	ar7
                                    261 ;	mclr_window.c:89: if ((s & ST_ACK) && !(s & ST_BERR)) {
      0000E7 EE               [12]  262 	mov	a,r6
      0000E8 20 E1 03         [24]  263 	jb	acc.1,00149$
      0000EB 02 01 C0         [24]  264 	ljmp	00104$
      0000EE                        265 00149$:
      0000EE EE               [12]  266 	mov	a,r6
      0000EF 30 E2 03         [24]  267 	jnb	acc.2,00150$
      0000F2 02 01 C0         [24]  268 	ljmp	00104$
      0000F5                        269 00150$:
                                    270 ;	mclr_window.c:90: if (nhit < MAXHIT) {
      0000F5 90 05 00         [24]  271 	mov	dptr,#_nhit
      0000F8 E0               [24]  272 	movx	a,@dptr
      0000F9 FC               [12]  273 	mov	r4,a
      0000FA A3               [24]  274 	inc	dptr
      0000FB E0               [24]  275 	movx	a,@dptr
      0000FC FD               [12]  276 	mov	r5,a
      0000FD C3               [12]  277 	clr	c
      0000FE EC               [12]  278 	mov	a,r4
      0000FF 94 30            [12]  279 	subb	a,#0x30
      000101 ED               [12]  280 	mov	a,r5
      000102 94 00            [12]  281 	subb	a,#0x00
      000104 40 03            [24]  282 	jc	00151$
      000106 02 01 B1         [24]  283 	ljmp	00102$
      000109                        284 00151$:
                                    285 ;	mclr_window.c:91: hits[nhit * 4 + 0] = a;
      000109 90 05 00         [24]  286 	mov	dptr,#_nhit
      00010C E0               [24]  287 	movx	a,@dptr
      00010D FC               [12]  288 	mov	r4,a
      00010E A3               [24]  289 	inc	dptr
      00010F E0               [24]  290 	movx	a,@dptr
      000110 FD               [12]  291 	mov	r5,a
      000111 EC               [12]  292 	mov	a,r4
      000112 2C               [12]  293 	add	a,r4
      000113 FC               [12]  294 	mov	r4,a
      000114 ED               [12]  295 	mov	a,r5
      000115 33               [12]  296 	rlc	a
      000116 FD               [12]  297 	mov	r5,a
      000117 EC               [12]  298 	mov	a,r4
      000118 2C               [12]  299 	add	a,r4
      000119 FC               [12]  300 	mov	r4,a
      00011A ED               [12]  301 	mov	a,r5
      00011B 33               [12]  302 	rlc	a
      00011C FD               [12]  303 	mov	r5,a
      00011D 8C 82            [24]  304 	mov	dpl,r4
      00011F 74 04            [12]  305 	mov	a,#(_hits >> 8)
      000121 2D               [12]  306 	add	a,r5
      000122 F5 83            [12]  307 	mov	dph,a
      000124 EF               [12]  308 	mov	a,r7
      000125 F0               [24]  309 	movx	@dptr,a
                                    310 ;	mclr_window.c:92: hits[nhit * 4 + 1] = s;
      000126 90 05 00         [24]  311 	mov	dptr,#_nhit
      000129 E0               [24]  312 	movx	a,@dptr
      00012A FD               [12]  313 	mov	r5,a
      00012B A3               [24]  314 	inc	dptr
      00012C E0               [24]  315 	movx	a,@dptr
      00012D FF               [12]  316 	mov	r7,a
      00012E ED               [12]  317 	mov	a,r5
      00012F 2D               [12]  318 	add	a,r5
      000130 FD               [12]  319 	mov	r5,a
      000131 EF               [12]  320 	mov	a,r7
      000132 33               [12]  321 	rlc	a
      000133 FF               [12]  322 	mov	r7,a
      000134 ED               [12]  323 	mov	a,r5
      000135 2D               [12]  324 	add	a,r5
      000136 FD               [12]  325 	mov	r5,a
      000137 EF               [12]  326 	mov	a,r7
      000138 33               [12]  327 	rlc	a
      000139 FF               [12]  328 	mov	r7,a
      00013A 0D               [12]  329 	inc	r5
      00013B BD 00 01         [24]  330 	cjne	r5,#0x00,00152$
      00013E 0F               [12]  331 	inc	r7
      00013F                        332 00152$:
      00013F 8D 82            [24]  333 	mov	dpl,r5
      000141 74 04            [12]  334 	mov	a,#(_hits >> 8)
      000143 2F               [12]  335 	add	a,r7
      000144 F5 83            [12]  336 	mov	dph,a
      000146 EE               [12]  337 	mov	a,r6
      000147 F0               [24]  338 	movx	@dptr,a
                                    339 ;	mclr_window.c:93: hits[nhit * 4 + 2] = (unsigned char)((tick >> 8) & 0xFF);
      000148 90 05 00         [24]  340 	mov	dptr,#_nhit
      00014B E0               [24]  341 	movx	a,@dptr
      00014C FE               [12]  342 	mov	r6,a
      00014D A3               [24]  343 	inc	dptr
      00014E E0               [24]  344 	movx	a,@dptr
      00014F FF               [12]  345 	mov	r7,a
      000150 EE               [12]  346 	mov	a,r6
      000151 2E               [12]  347 	add	a,r6
      000152 FE               [12]  348 	mov	r6,a
      000153 EF               [12]  349 	mov	a,r7
      000154 33               [12]  350 	rlc	a
      000155 FF               [12]  351 	mov	r7,a
      000156 EE               [12]  352 	mov	a,r6
      000157 2E               [12]  353 	add	a,r6
      000158 FE               [12]  354 	mov	r6,a
      000159 EF               [12]  355 	mov	a,r7
      00015A 33               [12]  356 	rlc	a
      00015B FF               [12]  357 	mov	r7,a
      00015C 74 02            [12]  358 	mov	a,#0x02
      00015E 2E               [12]  359 	add	a, r6
      00015F FE               [12]  360 	mov	r6,a
      000160 E4               [12]  361 	clr	a
      000161 3F               [12]  362 	addc	a, r7
      000162 24 04            [12]  363 	add	a,#(_hits >> 8)
      000164 FF               [12]  364 	mov	r7,a
      000165 90 05 04         [24]  365 	mov	dptr,#_tick
      000168 E0               [24]  366 	movx	a,@dptr
      000169 A3               [24]  367 	inc	dptr
      00016A E0               [24]  368 	movx	a,@dptr
      00016B FB               [12]  369 	mov	r3,a
      00016C A3               [24]  370 	inc	dptr
      00016D E0               [24]  371 	movx	a,@dptr
      00016E A3               [24]  372 	inc	dptr
      00016F E0               [24]  373 	movx	a,@dptr
      000170 8B 02            [24]  374 	mov	ar2,r3
      000172 8E 82            [24]  375 	mov	dpl,r6
      000174 8F 83            [24]  376 	mov	dph,r7
      000176 EA               [12]  377 	mov	a,r2
      000177 F0               [24]  378 	movx	@dptr,a
                                    379 ;	mclr_window.c:94: hits[nhit * 4 + 3] = (unsigned char)(tick & 0xFF);
      000178 90 05 00         [24]  380 	mov	dptr,#_nhit
      00017B E0               [24]  381 	movx	a,@dptr
      00017C FE               [12]  382 	mov	r6,a
      00017D A3               [24]  383 	inc	dptr
      00017E E0               [24]  384 	movx	a,@dptr
      00017F FF               [12]  385 	mov	r7,a
      000180 EE               [12]  386 	mov	a,r6
      000181 2E               [12]  387 	add	a,r6
      000182 FE               [12]  388 	mov	r6,a
      000183 EF               [12]  389 	mov	a,r7
      000184 33               [12]  390 	rlc	a
      000185 FF               [12]  391 	mov	r7,a
      000186 EE               [12]  392 	mov	a,r6
      000187 2E               [12]  393 	add	a,r6
      000188 FE               [12]  394 	mov	r6,a
      000189 EF               [12]  395 	mov	a,r7
      00018A 33               [12]  396 	rlc	a
      00018B FF               [12]  397 	mov	r7,a
      00018C 74 03            [12]  398 	mov	a,#0x03
      00018E 2E               [12]  399 	add	a, r6
      00018F FE               [12]  400 	mov	r6,a
      000190 E4               [12]  401 	clr	a
      000191 3F               [12]  402 	addc	a, r7
      000192 24 04            [12]  403 	add	a,#(_hits >> 8)
      000194 FF               [12]  404 	mov	r7,a
      000195 90 05 04         [24]  405 	mov	dptr,#_tick
      000198 E0               [24]  406 	movx	a,@dptr
      000199 8E 82            [24]  407 	mov	dpl,r6
      00019B 8F 83            [24]  408 	mov	dph,r7
      00019D F0               [24]  409 	movx	@dptr,a
                                    410 ;	mclr_window.c:95: nhit++;
      00019E 90 05 00         [24]  411 	mov	dptr,#_nhit
      0001A1 E0               [24]  412 	movx	a,@dptr
      0001A2 FE               [12]  413 	mov	r6,a
      0001A3 A3               [24]  414 	inc	dptr
      0001A4 E0               [24]  415 	movx	a,@dptr
      0001A5 FF               [12]  416 	mov	r7,a
      0001A6 90 05 00         [24]  417 	mov	dptr,#_nhit
      0001A9 74 01            [12]  418 	mov	a,#0x01
      0001AB 2E               [12]  419 	add	a, r6
      0001AC F0               [24]  420 	movx	@dptr,a
      0001AD E4               [12]  421 	clr	a
      0001AE 3F               [12]  422 	addc	a, r7
      0001AF A3               [24]  423 	inc	dptr
      0001B0 F0               [24]  424 	movx	@dptr,a
      0001B1                        425 00102$:
                                    426 ;	mclr_window.c:99: I2CS = ST_LASTRD;
      0001B1 90 E6 78         [24]  427 	mov	dptr,#0xe678
      0001B4 74 20            [12]  428 	mov	a,#0x20
      0001B6 F0               [24]  429 	movx	@dptr,a
                                    430 ;	mclr_window.c:100: (void)I2DAT;
      0001B7 A3               [24]  431 	inc	dptr
      0001B8 E0               [24]  432 	movx	a,@dptr
                                    433 ;	mclr_window.c:101: (void)wait_done();
      0001B9 12 00 AA         [24]  434 	lcall	_wait_done
                                    435 ;	mclr_window.c:102: (void)I2DAT;
      0001BC 90 E6 79         [24]  436 	mov	dptr,#0xe679
      0001BF E0               [24]  437 	movx	a,@dptr
      0001C0                        438 00104$:
                                    439 ;	mclr_window.c:105: I2CS = ST_STOP;
      0001C0 90 E6 78         [24]  440 	mov	dptr,#0xe678
      0001C3 74 40            [12]  441 	mov	a,#0x40
      0001C5 F0               [24]  442 	movx	@dptr,a
                                    443 ;	mclr_window.c:106: for (t = 0; t < 4000; t++)
      0001C6 7E 00            [12]  444 	mov	r6,#0x00
      0001C8 7F 00            [12]  445 	mov	r7,#0x00
      0001CA                        446 00109$:
                                    447 ;	mclr_window.c:107: if (!(I2CS & ST_STOP))
      0001CA 90 E6 78         [24]  448 	mov	dptr,#0xe678
      0001CD E0               [24]  449 	movx	a,@dptr
      0001CE 30 E6 0E         [24]  450 	jnb	acc.6,00111$
                                    451 ;	mclr_window.c:106: for (t = 0; t < 4000; t++)
      0001D1 0E               [12]  452 	inc	r6
      0001D2 BE 00 01         [24]  453 	cjne	r6,#0x00,00154$
      0001D5 0F               [12]  454 	inc	r7
      0001D6                        455 00154$:
      0001D6 C3               [12]  456 	clr	c
      0001D7 EE               [12]  457 	mov	a,r6
      0001D8 94 A0            [12]  458 	subb	a,#0xa0
      0001DA EF               [12]  459 	mov	a,r7
      0001DB 94 0F            [12]  460 	subb	a,#0x0f
      0001DD 40 EB            [24]  461 	jc	00109$
      0001DF                        462 00111$:
                                    463 ;	mclr_window.c:109: }
      0001DF 22               [24]  464 	ret
                                    465 ;------------------------------------------------------------
                                    466 ;Allocation info for local variables in function 'main'
                                    467 ;------------------------------------------------------------
                                    468 ;i             Allocated to registers r7 
                                    469 ;------------------------------------------------------------
                                    470 ;	mclr_window.c:111: void main(void)
                                    471 ;	-----------------------------------------
                                    472 ;	 function main
                                    473 ;	-----------------------------------------
      0001E0                        474 _main:
                                    475 ;	mclr_window.c:115: for (i = 0; i < MAXHIT * 4; i++)
      0001E0 7F 00            [12]  476 	mov	r7,#0x00
      0001E2                        477 00103$:
                                    478 ;	mclr_window.c:116: hits[i] = 0;
      0001E2 8F 82            [24]  479 	mov	dpl,r7
      0001E4 75 83 04         [24]  480 	mov	dph,#(_hits >> 8)
      0001E7 E4               [12]  481 	clr	a
      0001E8 F0               [24]  482 	movx	@dptr,a
                                    483 ;	mclr_window.c:115: for (i = 0; i < MAXHIT * 4; i++)
      0001E9 0F               [12]  484 	inc	r7
      0001EA BF C0 00         [24]  485 	cjne	r7,#0xc0,00131$
      0001ED                        486 00131$:
      0001ED 40 F3            [24]  487 	jc	00103$
                                    488 ;	mclr_window.c:117: nhit = 0;
      0001EF 90 05 00         [24]  489 	mov	dptr,#_nhit
      0001F2 E4               [12]  490 	clr	a
      0001F3 F0               [24]  491 	movx	@dptr,a
      0001F4 A3               [24]  492 	inc	dptr
      0001F5 F0               [24]  493 	movx	@dptr,a
                                    494 ;	mclr_window.c:118: tick = 0;
      0001F6 90 05 04         [24]  495 	mov	dptr,#_tick
      0001F9 F0               [24]  496 	movx	@dptr,a
      0001FA A3               [24]  497 	inc	dptr
      0001FB F0               [24]  498 	movx	@dptr,a
      0001FC A3               [24]  499 	inc	dptr
      0001FD F0               [24]  500 	movx	@dptr,a
      0001FE A3               [24]  501 	inc	dptr
      0001FF F0               [24]  502 	movx	@dptr,a
                                    503 ;	mclr_window.c:119: marker[0] = 0xC0; marker[1] = 0xDE;
      000200 90 04 80         [24]  504 	mov	dptr,#_marker
      000203 74 C0            [12]  505 	mov	a,#0xc0
      000205 F0               [24]  506 	movx	@dptr,a
      000206 90 04 81         [24]  507 	mov	dptr,#(_marker + 0x0001)
      000209 74 DE            [12]  508 	mov	a,#0xde
      00020B F0               [24]  509 	movx	@dptr,a
                                    510 ;	mclr_window.c:120: marker[2] = 0xF1; marker[3] = 0x35;
      00020C 90 04 82         [24]  511 	mov	dptr,#(_marker + 0x0002)
      00020F 74 F1            [12]  512 	mov	a,#0xf1
      000211 F0               [24]  513 	movx	@dptr,a
      000212 90 04 83         [24]  514 	mov	dptr,#(_marker + 0x0003)
      000215 74 35            [12]  515 	mov	a,#0x35
      000217 F0               [24]  516 	movx	@dptr,a
      000218                        517 00105$:
                                    518 ;	mclr_window.c:125: probe(0x22);            /* PICM application */
      000218 75 82 22         [24]  519 	mov	dpl, #0x22
      00021B 12 00 CB         [24]  520 	lcall	_probe
                                    521 ;	mclr_window.c:126: probe(0x23);            /* PICM bootloader  */
      00021E 75 82 23         [24]  522 	mov	dpl, #0x23
      000221 12 00 CB         [24]  523 	lcall	_probe
                                    524 ;	mclr_window.c:127: tick++;
      000224 90 05 04         [24]  525 	mov	dptr,#_tick
      000227 E0               [24]  526 	movx	a,@dptr
      000228 FC               [12]  527 	mov	r4,a
      000229 A3               [24]  528 	inc	dptr
      00022A E0               [24]  529 	movx	a,@dptr
      00022B FD               [12]  530 	mov	r5,a
      00022C A3               [24]  531 	inc	dptr
      00022D E0               [24]  532 	movx	a,@dptr
      00022E FE               [12]  533 	mov	r6,a
      00022F A3               [24]  534 	inc	dptr
      000230 E0               [24]  535 	movx	a,@dptr
      000231 FF               [12]  536 	mov	r7,a
      000232 90 05 04         [24]  537 	mov	dptr,#_tick
      000235 74 01            [12]  538 	mov	a,#0x01
      000237 2C               [12]  539 	add	a, r4
      000238 F0               [24]  540 	movx	@dptr,a
      000239 E4               [12]  541 	clr	a
      00023A 3D               [12]  542 	addc	a, r5
      00023B A3               [24]  543 	inc	dptr
      00023C F0               [24]  544 	movx	@dptr,a
      00023D E4               [12]  545 	clr	a
      00023E 3E               [12]  546 	addc	a, r6
      00023F A3               [24]  547 	inc	dptr
      000240 F0               [24]  548 	movx	@dptr,a
      000241 E4               [12]  549 	clr	a
      000242 3F               [12]  550 	addc	a, r7
      000243 A3               [24]  551 	inc	dptr
      000244 F0               [24]  552 	movx	@dptr,a
                                    553 ;	mclr_window.c:129: }
      000245 80 D1            [24]  554 	sjmp	00105$
                                    555 	.area CSEG    (CODE)
                                    556 	.area CONST   (CODE)
                                    557 	.area XINIT   (CODE)
                                    558 	.area CABS    (ABS,CODE)
