                                      1 ;--------------------------------------------------------
                                      2 ; File Created by SDCC : free open source ISO C Compiler
                                      3 ; Version 4.6.0 #16555 (Mac OS X ppc)
                                      4 ;--------------------------------------------------------
                                      5 	.module eeprom_dump_all
                                      6 	
                                      7 	.optsdcc -mmcs51 --model-small
                                      8 ;--------------------------------------------------------
                                      9 ; Public variables in this module
                                     10 ;--------------------------------------------------------
                                     11 	.globl _main
                                     12 	.globl _st
                                     13 	.globl _d52
                                     14 	.globl _d51
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
      000008                         34 _dump_PARM_2:
      000008                         35 	.ds 2
                                     36 ;--------------------------------------------------------
                                     37 ; overlayable items in internal ram
                                     38 ;--------------------------------------------------------
                                     39 	.area	OSEG    (OVR,DATA)
                                     40 	.area	OSEG    (OVR,DATA)
                                     41 ;--------------------------------------------------------
                                     42 ; Stack segment in internal ram
                                     43 ;--------------------------------------------------------
                                     44 	.area SSEG
      00000A                         45 __start__stack:
      00000A                         46 	.ds	1
                                     47 
                                     48 ;--------------------------------------------------------
                                     49 ; indirectly addressable internal ram data
                                     50 ;--------------------------------------------------------
                                     51 	.area ISEG    (DATA)
                                     52 ;--------------------------------------------------------
                                     53 ; absolute internal ram data
                                     54 ;--------------------------------------------------------
                                     55 	.area IABS    (ABS,DATA)
                                     56 	.area IABS    (ABS,DATA)
                                     57 ;--------------------------------------------------------
                                     58 ; bit data
                                     59 ;--------------------------------------------------------
                                     60 	.area BSEG    (BIT)
                                     61 ;--------------------------------------------------------
                                     62 ; paged external ram data
                                     63 ;--------------------------------------------------------
                                     64 	.area PSEG    (PAG,XDATA)
                                     65 ;--------------------------------------------------------
                                     66 ; uninitialized external ram data
                                     67 ;--------------------------------------------------------
                                     68 	.area XSEG    (XDATA)
                           000400    69 _d51	=	0x0400
                           000500    70 _d52	=	0x0500
                           000600    71 _st	=	0x0600
                                     72 ;--------------------------------------------------------
                                     73 ; absolute external ram data
                                     74 ;--------------------------------------------------------
                                     75 	.area XABS    (ABS,XDATA)
                                     76 ;--------------------------------------------------------
                                     77 ; initialized external ram data
                                     78 ;--------------------------------------------------------
                                     79 	.area XISEG   (XDATA)
                                     80 	.area HOME    (CODE)
                                     81 	.area GSINIT0 (CODE)
                                     82 	.area GSINIT1 (CODE)
                                     83 	.area GSINIT2 (CODE)
                                     84 	.area GSINIT3 (CODE)
                                     85 	.area GSINIT4 (CODE)
                                     86 	.area GSINIT5 (CODE)
                                     87 	.area GSINIT  (CODE)
                                     88 	.area GSFINAL (CODE)
                                     89 	.area CSEG    (CODE)
                                     90 ;--------------------------------------------------------
                                     91 ; interrupt vector
                                     92 ;--------------------------------------------------------
                                     93 	.area HOME    (CODE)
      000000                         94 __interrupt_vect:
      000000 02 00 4E         [24]   95 	ljmp	__sdcc_gsinit_startup
                                     96 ; restartable atomic support routines
      000003                         97 	.ds	5
      000008                         98 sdcc_atomic_exchange_rollback_start::
      000008 00               [12]   99 	nop
      000009 00               [12]  100 	nop
      00000A                        101 sdcc_atomic_exchange_pdata_impl:
      00000A E2               [24]  102 	movx	a, @r0
      00000B FB               [12]  103 	mov	r3, a
      00000C EA               [12]  104 	mov	a, r2
      00000D F2               [24]  105 	movx	@r0, a
      00000E 80 2C            [24]  106 	sjmp	sdcc_atomic_exchange_exit
      000010 00               [12]  107 	nop
      000011 00               [12]  108 	nop
      000012                        109 sdcc_atomic_exchange_xdata_impl:
      000012 E0               [24]  110 	movx	a, @dptr
      000013 FB               [12]  111 	mov	r3, a
      000014 EA               [12]  112 	mov	a, r2
      000015 F0               [24]  113 	movx	@dptr, a
      000016 80 24            [24]  114 	sjmp	sdcc_atomic_exchange_exit
      000018                        115 sdcc_atomic_compare_exchange_idata_impl:
      000018 E6               [12]  116 	mov	a, @r0
      000019 B5 02 02         [24]  117 	cjne	a, ar2, .+#5
      00001C EB               [12]  118 	mov	a, r3
      00001D F6               [12]  119 	mov	@r0, a
      00001E 22               [24]  120 	ret
      00001F 00               [12]  121 	nop
      000020                        122 sdcc_atomic_compare_exchange_pdata_impl:
      000020 E2               [24]  123 	movx	a, @r0
      000021 B5 02 02         [24]  124 	cjne	a, ar2, .+#5
      000024 EB               [12]  125 	mov	a, r3
      000025 F2               [24]  126 	movx	@r0, a
      000026 22               [24]  127 	ret
      000027 00               [12]  128 	nop
      000028                        129 sdcc_atomic_compare_exchange_xdata_impl:
      000028 E0               [24]  130 	movx	a, @dptr
      000029 B5 02 02         [24]  131 	cjne	a, ar2, .+#5
      00002C EB               [12]  132 	mov	a, r3
      00002D F0               [24]  133 	movx	@dptr, a
      00002E 22               [24]  134 	ret
      00002F                        135 sdcc_atomic_exchange_rollback_end::
                                    136 
      00002F                        137 sdcc_atomic_exchange_gptr_impl::
      00002F 30 F6 E0         [24]  138 	jnb	b.6, sdcc_atomic_exchange_xdata_impl
      000032 A8 82            [24]  139 	mov	r0, dpl
      000034 20 F5 D3         [24]  140 	jb	b.5, sdcc_atomic_exchange_pdata_impl
      000037                        141 sdcc_atomic_exchange_idata_impl:
      000037 EA               [12]  142 	mov	a, r2
      000038 C6               [12]  143 	xch	a, @r0
      000039 F5 82            [12]  144 	mov	dpl, a
      00003B 22               [24]  145 	ret
      00003C                        146 sdcc_atomic_exchange_exit:
      00003C 8B 82            [24]  147 	mov	dpl, r3
      00003E 22               [24]  148 	ret
      00003F                        149 sdcc_atomic_compare_exchange_gptr_impl::
      00003F 30 F6 E6         [24]  150 	jnb	b.6, sdcc_atomic_compare_exchange_xdata_impl
      000042 A8 82            [24]  151 	mov	r0, dpl
      000044 20 F5 D9         [24]  152 	jb	b.5, sdcc_atomic_compare_exchange_pdata_impl
      000047 80 CF            [24]  153 	sjmp	sdcc_atomic_compare_exchange_idata_impl
                                    154 ;--------------------------------------------------------
                                    155 ; global & static initialisations
                                    156 ;--------------------------------------------------------
                                    157 	.area HOME    (CODE)
                                    158 	.area GSINIT  (CODE)
                                    159 	.area GSFINAL (CODE)
                                    160 	.area GSINIT  (CODE)
                                    161 	.globl __sdcc_gsinit_startup
                                    162 	.globl __sdcc_program_startup
                                    163 	.globl __start__stack
                                    164 	.globl __mcs51_genXINIT
                                    165 	.globl __mcs51_genXRAMCLEAR
                                    166 	.globl __mcs51_genRAMCLEAR
                                    167 	.area GSFINAL (CODE)
      0000A7 02 00 49         [24]  168 	ljmp	__sdcc_program_startup
                                    169 ;--------------------------------------------------------
                                    170 ; Home
                                    171 ;--------------------------------------------------------
                                    172 	.area HOME    (CODE)
                                    173 	.area HOME    (CODE)
      000049                        174 __sdcc_program_startup:
      000049 12 01 B6         [24]  175 	lcall	_main
      00004C                        176 __sdcc_program_exit:
      00004C 80 FE            [24]  177 	sjmp	.
                                    178 ;	return from main will return to caller
                                    179 ;--------------------------------------------------------
                                    180 ; code
                                    181 ;--------------------------------------------------------
                                    182 	.area CSEG    (CODE)
                                    183 ;------------------------------------------------------------
                                    184 ;Allocation info for local variables in function 'wd'
                                    185 ;------------------------------------------------------------
                                    186 ;t             Allocated to registers r6 r7 
                                    187 ;s             Allocated to registers r5 
                                    188 ;------------------------------------------------------------
                                    189 ;	eeprom_dump_all.c:49: static unsigned char wd(void)
                                    190 ;	-----------------------------------------
                                    191 ;	 function wd
                                    192 ;	-----------------------------------------
      0000AA                        193 _wd:
                           000007   194 	ar7 = 0x07
                           000006   195 	ar6 = 0x06
                           000005   196 	ar5 = 0x05
                           000004   197 	ar4 = 0x04
                           000003   198 	ar3 = 0x03
                           000002   199 	ar2 = 0x02
                           000001   200 	ar1 = 0x01
                           000000   201 	ar0 = 0x00
                                    202 ;	eeprom_dump_all.c:53: for (t = 0; t < 30000; t++) {
      0000AA 7E 00            [12]  203 	mov	r6,#0x00
      0000AC 7F 00            [12]  204 	mov	r7,#0x00
      0000AE                        205 00104$:
                                    206 ;	eeprom_dump_all.c:54: s = I2CS;
      0000AE 90 E6 78         [24]  207 	mov	dptr,#0xe678
      0000B1 E0               [24]  208 	movx	a,@dptr
                                    209 ;	eeprom_dump_all.c:55: if (s & (ST_DONE | ST_BERR))
      0000B2 FD               [12]  210 	mov	r5,a
      0000B3 54 05            [12]  211 	anl	a,#0x05
      0000B5 60 03            [24]  212 	jz	00105$
                                    213 ;	eeprom_dump_all.c:56: return s;
      0000B7 8D 82            [24]  214 	mov	dpl, r5
      0000B9 22               [24]  215 	ret
      0000BA                        216 00105$:
                                    217 ;	eeprom_dump_all.c:53: for (t = 0; t < 30000; t++) {
      0000BA 0E               [12]  218 	inc	r6
      0000BB BE 00 01         [24]  219 	cjne	r6,#0x00,00130$
      0000BE 0F               [12]  220 	inc	r7
      0000BF                        221 00130$:
      0000BF C3               [12]  222 	clr	c
      0000C0 EE               [12]  223 	mov	a,r6
      0000C1 94 30            [12]  224 	subb	a,#0x30
      0000C3 EF               [12]  225 	mov	a,r7
      0000C4 94 75            [12]  226 	subb	a,#0x75
      0000C6 40 E6            [24]  227 	jc	00104$
                                    228 ;	eeprom_dump_all.c:58: return s;
      0000C8 8D 82            [24]  229 	mov	dpl, r5
                                    230 ;	eeprom_dump_all.c:59: }
      0000CA 22               [24]  231 	ret
                                    232 ;------------------------------------------------------------
                                    233 ;Allocation info for local variables in function 'stop'
                                    234 ;------------------------------------------------------------
                                    235 ;t             Allocated to registers r6 r7 
                                    236 ;------------------------------------------------------------
                                    237 ;	eeprom_dump_all.c:61: static void stop(void)
                                    238 ;	-----------------------------------------
                                    239 ;	 function stop
                                    240 ;	-----------------------------------------
      0000CB                        241 _stop:
                                    242 ;	eeprom_dump_all.c:64: I2CS = ST_STOP;
      0000CB 90 E6 78         [24]  243 	mov	dptr,#0xe678
      0000CE 74 40            [12]  244 	mov	a,#0x40
      0000D0 F0               [24]  245 	movx	@dptr,a
                                    246 ;	eeprom_dump_all.c:65: for (t = 0; t < 30000; t++)
      0000D1 7E 00            [12]  247 	mov	r6,#0x00
      0000D3 7F 00            [12]  248 	mov	r7,#0x00
      0000D5                        249 00104$:
                                    250 ;	eeprom_dump_all.c:66: if (!(I2CS & ST_STOP))
      0000D5 90 E6 78         [24]  251 	mov	dptr,#0xe678
      0000D8 E0               [24]  252 	movx	a,@dptr
      0000D9 30 E6 0E         [24]  253 	jnb	acc.6,00106$
                                    254 ;	eeprom_dump_all.c:65: for (t = 0; t < 30000; t++)
      0000DC 0E               [12]  255 	inc	r6
      0000DD BE 00 01         [24]  256 	cjne	r6,#0x00,00124$
      0000E0 0F               [12]  257 	inc	r7
      0000E1                        258 00124$:
      0000E1 C3               [12]  259 	clr	c
      0000E2 EE               [12]  260 	mov	a,r6
      0000E3 94 30            [12]  261 	subb	a,#0x30
      0000E5 EF               [12]  262 	mov	a,r7
      0000E6 94 75            [12]  263 	subb	a,#0x75
      0000E8 40 EB            [24]  264 	jc	00104$
      0000EA                        265 00106$:
                                    266 ;	eeprom_dump_all.c:68: }
      0000EA 22               [24]  267 	ret
                                    268 ;------------------------------------------------------------
                                    269 ;Allocation info for local variables in function 'dump'
                                    270 ;------------------------------------------------------------
                                    271 ;out           Allocated with name '_dump_PARM_2'
                                    272 ;addr8         Allocated to registers r7 
                                    273 ;i             Allocated to registers r5 r6 
                                    274 ;s             Allocated to registers r7 
                                    275 ;------------------------------------------------------------
                                    276 ;	eeprom_dump_all.c:71: static unsigned char dump(unsigned char addr8, __xdata unsigned char *out)
                                    277 ;	-----------------------------------------
                                    278 ;	 function dump
                                    279 ;	-----------------------------------------
      0000EB                        280 _dump:
      0000EB AF 82            [24]  281 	mov	r7, dpl
                                    282 ;	eeprom_dump_all.c:76: for (i = 0; i < 256; i++)
      0000ED 7D 00            [12]  283 	mov	r5,#0x00
      0000EF 7E 00            [12]  284 	mov	r6,#0x00
      0000F1                        285 00116$:
                                    286 ;	eeprom_dump_all.c:77: out[i] = 0xEE;                       /* "never read" sentinel */
      0000F1 ED               [12]  287 	mov	a,r5
      0000F2 25 08            [12]  288 	add	a, _dump_PARM_2
      0000F4 F5 82            [12]  289 	mov	dpl,a
      0000F6 EE               [12]  290 	mov	a,r6
      0000F7 35 09            [12]  291 	addc	a, (_dump_PARM_2 + 1)
      0000F9 F5 83            [12]  292 	mov	dph,a
      0000FB 74 EE            [12]  293 	mov	a,#0xee
      0000FD F0               [24]  294 	movx	@dptr,a
                                    295 ;	eeprom_dump_all.c:76: for (i = 0; i < 256; i++)
      0000FE 0D               [12]  296 	inc	r5
      0000FF BD 00 01         [24]  297 	cjne	r5,#0x00,00195$
      000102 0E               [12]  298 	inc	r6
      000103                        299 00195$:
      000103 74 FF            [12]  300 	mov	a,#0x100 - 0x01
      000105 2E               [12]  301 	add	a,r6
      000106 50 E9            [24]  302 	jnc	00116$
                                    303 ;	eeprom_dump_all.c:79: I2CS  = ST_START;
      000108 90 E6 78         [24]  304 	mov	dptr,#0xe678
      00010B 74 80            [12]  305 	mov	a,#0x80
      00010D F0               [24]  306 	movx	@dptr,a
                                    307 ;	eeprom_dump_all.c:80: I2DAT = addr8;                           /* device address, write dir */
      00010E A3               [24]  308 	inc	dptr
      00010F EF               [12]  309 	mov	a,r7
      000110 F0               [24]  310 	movx	@dptr,a
                                    311 ;	eeprom_dump_all.c:81: s = wd();
      000111 C0 07            [24]  312 	push	ar7
      000113 12 00 AA         [24]  313 	lcall	_wd
      000116 AE 82            [24]  314 	mov	r6, dpl
      000118 D0 07            [24]  315 	pop	ar7
                                    316 ;	eeprom_dump_all.c:82: if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 1; }
      00011A EE               [12]  317 	mov	a,r6
      00011B 30 E1 04         [24]  318 	jnb	acc.1,00102$
      00011E EE               [12]  319 	mov	a,r6
      00011F 30 E2 07         [24]  320 	jnb	acc.2,00103$
      000122                        321 00102$:
      000122 12 00 CB         [24]  322 	lcall	_stop
      000125 75 82 01         [24]  323 	mov	dpl, #0x01
      000128 22               [24]  324 	ret
      000129                        325 00103$:
                                    326 ;	eeprom_dump_all.c:84: I2DAT = 0x00;                            /* word address 0 -- pointer only */
      000129 90 E6 79         [24]  327 	mov	dptr,#0xe679
      00012C E4               [12]  328 	clr	a
      00012D F0               [24]  329 	movx	@dptr,a
                                    330 ;	eeprom_dump_all.c:85: s = wd();
      00012E C0 07            [24]  331 	push	ar7
      000130 12 00 AA         [24]  332 	lcall	_wd
      000133 AE 82            [24]  333 	mov	r6, dpl
      000135 D0 07            [24]  334 	pop	ar7
                                    335 ;	eeprom_dump_all.c:86: if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 2; }
      000137 EE               [12]  336 	mov	a,r6
      000138 30 E1 04         [24]  337 	jnb	acc.1,00105$
      00013B EE               [12]  338 	mov	a,r6
      00013C 30 E2 07         [24]  339 	jnb	acc.2,00106$
      00013F                        340 00105$:
      00013F 12 00 CB         [24]  341 	lcall	_stop
      000142 75 82 02         [24]  342 	mov	dpl, #0x02
      000145 22               [24]  343 	ret
      000146                        344 00106$:
                                    345 ;	eeprom_dump_all.c:88: I2CS  = ST_START;                        /* REPEATED start, no STOP first */
      000146 90 E6 78         [24]  346 	mov	dptr,#0xe678
      000149 74 80            [12]  347 	mov	a,#0x80
      00014B F0               [24]  348 	movx	@dptr,a
                                    349 ;	eeprom_dump_all.c:89: I2DAT = (unsigned char)(addr8 | 1);      /* device address, read dir */
      00014C 43 07 01         [24]  350 	orl	ar7,#0x01
      00014F 90 E6 79         [24]  351 	mov	dptr,#0xe679
      000152 EF               [12]  352 	mov	a,r7
      000153 F0               [24]  353 	movx	@dptr,a
                                    354 ;	eeprom_dump_all.c:90: s = wd();
      000154 12 00 AA         [24]  355 	lcall	_wd
                                    356 ;	eeprom_dump_all.c:91: if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 3; }
      000157 E5 82            [12]  357 	mov	a,dpl
      000159 FF               [12]  358 	mov	r7,a
      00015A 30 E1 04         [24]  359 	jnb	acc.1,00108$
      00015D EF               [12]  360 	mov	a,r7
      00015E 30 E2 07         [24]  361 	jnb	acc.2,00109$
      000161                        362 00108$:
      000161 12 00 CB         [24]  363 	lcall	_stop
      000164 75 82 03         [24]  364 	mov	dpl, #0x03
      000167 22               [24]  365 	ret
      000168                        366 00109$:
                                    367 ;	eeprom_dump_all.c:93: (void)I2DAT;                             /* starts the first byte */
      000168 90 E6 79         [24]  368 	mov	dptr,#0xe679
      00016B E0               [24]  369 	movx	a,@dptr
                                    370 ;	eeprom_dump_all.c:94: for (i = 0; i < 256; i++) {
      00016C 7E 00            [12]  371 	mov	r6,#0x00
      00016E 7F 00            [12]  372 	mov	r7,#0x00
      000170                        373 00118$:
                                    374 ;	eeprom_dump_all.c:95: if (i == 255)
      000170 BE FF 09         [24]  375 	cjne	r6,#0xff,00112$
      000173 BF 00 06         [24]  376 	cjne	r7,#0x00,00112$
                                    377 ;	eeprom_dump_all.c:96: I2CS = ST_LASTRD;                /* NACK the final byte */
      000176 90 E6 78         [24]  378 	mov	dptr,#0xe678
      000179 74 20            [12]  379 	mov	a,#0x20
      00017B F0               [24]  380 	movx	@dptr,a
      00017C                        381 00112$:
                                    382 ;	eeprom_dump_all.c:97: s = wd();
      00017C C0 07            [24]  383 	push	ar7
      00017E C0 06            [24]  384 	push	ar6
      000180 12 00 AA         [24]  385 	lcall	_wd
      000183 AD 82            [24]  386 	mov	r5, dpl
      000185 D0 06            [24]  387 	pop	ar6
      000187 D0 07            [24]  388 	pop	ar7
                                    389 ;	eeprom_dump_all.c:98: if (s & ST_BERR) { stop(); return 4; }
      000189 ED               [12]  390 	mov	a,r5
      00018A 30 E2 07         [24]  391 	jnb	acc.2,00114$
      00018D 12 00 CB         [24]  392 	lcall	_stop
      000190 75 82 04         [24]  393 	mov	dpl, #0x04
      000193 22               [24]  394 	ret
      000194                        395 00114$:
                                    396 ;	eeprom_dump_all.c:99: out[i] = I2DAT;
      000194 EE               [12]  397 	mov	a,r6
      000195 25 08            [12]  398 	add	a, _dump_PARM_2
      000197 FC               [12]  399 	mov	r4,a
      000198 EF               [12]  400 	mov	a,r7
      000199 35 09            [12]  401 	addc	a, (_dump_PARM_2 + 1)
      00019B FD               [12]  402 	mov	r5,a
      00019C 90 E6 79         [24]  403 	mov	dptr,#0xe679
      00019F E0               [24]  404 	movx	a,@dptr
      0001A0 8C 82            [24]  405 	mov	dpl,r4
      0001A2 8D 83            [24]  406 	mov	dph,r5
      0001A4 F0               [24]  407 	movx	@dptr,a
                                    408 ;	eeprom_dump_all.c:94: for (i = 0; i < 256; i++) {
      0001A5 0E               [12]  409 	inc	r6
      0001A6 BE 00 01         [24]  410 	cjne	r6,#0x00,00206$
      0001A9 0F               [12]  411 	inc	r7
      0001AA                        412 00206$:
      0001AA 74 FF            [12]  413 	mov	a,#0x100 - 0x01
      0001AC 2F               [12]  414 	add	a,r7
      0001AD 50 C1            [24]  415 	jnc	00118$
                                    416 ;	eeprom_dump_all.c:101: stop();
      0001AF 12 00 CB         [24]  417 	lcall	_stop
                                    418 ;	eeprom_dump_all.c:102: return 0;
      0001B2 75 82 00         [24]  419 	mov	dpl, #0x00
                                    420 ;	eeprom_dump_all.c:103: }
      0001B5 22               [24]  421 	ret
                                    422 ;------------------------------------------------------------
                                    423 ;Allocation info for local variables in function 'main'
                                    424 ;------------------------------------------------------------
                                    425 ;i             Allocated to registers r7 
                                    426 ;------------------------------------------------------------
                                    427 ;	eeprom_dump_all.c:105: void main(void)
                                    428 ;	-----------------------------------------
                                    429 ;	 function main
                                    430 ;	-----------------------------------------
      0001B6                        431 _main:
                                    432 ;	eeprom_dump_all.c:108: for (i = 0; i < 8; i++) st[i] = 0;
      0001B6 7F 00            [12]  433 	mov	r7,#0x00
      0001B8                        434 00103$:
      0001B8 8F 82            [24]  435 	mov	dpl,r7
      0001BA 75 83 06         [24]  436 	mov	dph,#(_st >> 8)
      0001BD E4               [12]  437 	clr	a
      0001BE F0               [24]  438 	movx	@dptr,a
      0001BF 0F               [12]  439 	inc	r7
      0001C0 BF 08 00         [24]  440 	cjne	r7,#0x08,00131$
      0001C3                        441 00131$:
      0001C3 40 F3            [24]  442 	jc	00103$
                                    443 ;	eeprom_dump_all.c:110: st[0] = dump(0xA2, d51);                 /* 7-bit 0x51 */
      0001C5 75 08 00         [24]  444 	mov	_dump_PARM_2,#_d51
      0001C8 75 09 04         [24]  445 	mov	(_dump_PARM_2 + 1),#(_d51 >> 8)
      0001CB 75 82 A2         [24]  446 	mov	dpl, #0xa2
      0001CE 12 00 EB         [24]  447 	lcall	_dump
      0001D1 AF 82            [24]  448 	mov	r7, dpl
      0001D3 90 06 00         [24]  449 	mov	dptr,#_st
      0001D6 EF               [12]  450 	mov	a,r7
      0001D7 F0               [24]  451 	movx	@dptr,a
                                    452 ;	eeprom_dump_all.c:111: st[1] = dump(0xA4, d52);                 /* 7-bit 0x52 */
      0001D8 75 08 00         [24]  453 	mov	_dump_PARM_2,#_d52
      0001DB 75 09 05         [24]  454 	mov	(_dump_PARM_2 + 1),#(_d52 >> 8)
      0001DE 75 82 A4         [24]  455 	mov	dpl, #0xa4
      0001E1 12 00 EB         [24]  456 	lcall	_dump
      0001E4 AF 82            [24]  457 	mov	r7, dpl
      0001E6 90 06 01         [24]  458 	mov	dptr,#(_st + 0x0001)
      0001E9 EF               [12]  459 	mov	a,r7
      0001EA F0               [24]  460 	movx	@dptr,a
                                    461 ;	eeprom_dump_all.c:113: st[2] = 0xC0; st[3] = 0xDE; st[4] = 0xF1; st[5] = 0x35;
      0001EB 90 06 02         [24]  462 	mov	dptr,#(_st + 0x0002)
      0001EE 74 C0            [12]  463 	mov	a,#0xc0
      0001F0 F0               [24]  464 	movx	@dptr,a
      0001F1 90 06 03         [24]  465 	mov	dptr,#(_st + 0x0003)
      0001F4 74 DE            [12]  466 	mov	a,#0xde
      0001F6 F0               [24]  467 	movx	@dptr,a
      0001F7 90 06 04         [24]  468 	mov	dptr,#(_st + 0x0004)
      0001FA 74 F1            [12]  469 	mov	a,#0xf1
      0001FC F0               [24]  470 	movx	@dptr,a
      0001FD 90 06 05         [24]  471 	mov	dptr,#(_st + 0x0005)
      000200 74 35            [12]  472 	mov	a,#0x35
      000202 F0               [24]  473 	movx	@dptr,a
      000203                        474 00106$:
                                    475 ;	eeprom_dump_all.c:116: }
      000203 80 FE            [24]  476 	sjmp	00106$
                                    477 	.area CSEG    (CODE)
                                    478 	.area CONST   (CODE)
                                    479 	.area XINIT   (CODE)
                                    480 	.area CABS    (ABS,CODE)
