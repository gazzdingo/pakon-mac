                                      1 ;--------------------------------------------------------
                                      2 ; File Created by SDCC : free open source ISO C Compiler
                                      3 ; Version 4.6.0 #16555 (Mac OS X ppc)
                                      4 ;--------------------------------------------------------
                                      5 	.module eeprom_dump_bus
                                      6 	
                                      7 	.optsdcc -mmcs51 --model-small
                                      8 ;--------------------------------------------------------
                                      9 ; Public variables in this module
                                     10 ;--------------------------------------------------------
                                     11 	.globl _main
                                     12 	.globl _st
                                     13 	.globl _buf
                                     14 ;--------------------------------------------------------
                                     15 ; special function registers
                                     16 ;--------------------------------------------------------
                                     17 	.area RSEG    (ABS,DATA)
      000000                         18 	.org 0x0000
                                     19 ;--------------------------------------------------------
                                     20 ; special function bits
                                     21 ;--------------------------------------------------------
                                     22 	.area RSEG    (ABS,DATA)
      000000                         23 	.org 0x0000
                                     24 ;--------------------------------------------------------
                                     25 ; overlayable register banks
                                     26 ;--------------------------------------------------------
                                     27 	.area REG_BANK_0	(REL,OVR,DATA)
      000000                         28 	.ds 8
                                     29 ;--------------------------------------------------------
                                     30 ; internal ram data
                                     31 ;--------------------------------------------------------
                                     32 	.area DSEG    (DATA)
      000008                         33 _dump_PARM_2:
      000008                         34 	.ds 2
                                     35 ;--------------------------------------------------------
                                     36 ; overlayable items in internal ram
                                     37 ;--------------------------------------------------------
                                     38 	.area	OSEG    (OVR,DATA)
                                     39 	.area	OSEG    (OVR,DATA)
                                     40 ;--------------------------------------------------------
                                     41 ; Stack segment in internal ram
                                     42 ;--------------------------------------------------------
                                     43 	.area SSEG
      00000A                         44 __start__stack:
      00000A                         45 	.ds	1
                                     46 
                                     47 ;--------------------------------------------------------
                                     48 ; indirectly addressable internal ram data
                                     49 ;--------------------------------------------------------
                                     50 	.area ISEG    (DATA)
                                     51 ;--------------------------------------------------------
                                     52 ; absolute internal ram data
                                     53 ;--------------------------------------------------------
                                     54 	.area IABS    (ABS,DATA)
                                     55 	.area IABS    (ABS,DATA)
                                     56 ;--------------------------------------------------------
                                     57 ; bit data
                                     58 ;--------------------------------------------------------
                                     59 	.area BSEG    (BIT)
                                     60 ;--------------------------------------------------------
                                     61 ; paged external ram data
                                     62 ;--------------------------------------------------------
                                     63 	.area PSEG    (PAG,XDATA)
                                     64 ;--------------------------------------------------------
                                     65 ; uninitialized external ram data
                                     66 ;--------------------------------------------------------
                                     67 	.area XSEG    (XDATA)
                           000400    68 _buf	=	0x0400
                           000C00    69 _st	=	0x0c00
                                     70 ;--------------------------------------------------------
                                     71 ; absolute external ram data
                                     72 ;--------------------------------------------------------
                                     73 	.area XABS    (ABS,XDATA)
                                     74 ;--------------------------------------------------------
                                     75 ; initialized external ram data
                                     76 ;--------------------------------------------------------
                                     77 	.area XISEG   (XDATA)
                                     78 	.area HOME    (CODE)
                                     79 	.area GSINIT0 (CODE)
                                     80 	.area GSINIT1 (CODE)
                                     81 	.area GSINIT2 (CODE)
                                     82 	.area GSINIT3 (CODE)
                                     83 	.area GSINIT4 (CODE)
                                     84 	.area GSINIT5 (CODE)
                                     85 	.area GSINIT  (CODE)
                                     86 	.area GSFINAL (CODE)
                                     87 	.area CSEG    (CODE)
                                     88 ;--------------------------------------------------------
                                     89 ; interrupt vector
                                     90 ;--------------------------------------------------------
                                     91 	.area HOME    (CODE)
      000000                         92 __interrupt_vect:
      000000 02 00 4E         [24]   93 	ljmp	__sdcc_gsinit_startup
                                     94 ; restartable atomic support routines
      000003                         95 	.ds	5
      000008                         96 sdcc_atomic_exchange_rollback_start::
      000008 00               [12]   97 	nop
      000009 00               [12]   98 	nop
      00000A                         99 sdcc_atomic_exchange_pdata_impl:
      00000A E2               [24]  100 	movx	a, @r0
      00000B FB               [12]  101 	mov	r3, a
      00000C EA               [12]  102 	mov	a, r2
      00000D F2               [24]  103 	movx	@r0, a
      00000E 80 2C            [24]  104 	sjmp	sdcc_atomic_exchange_exit
      000010 00               [12]  105 	nop
      000011 00               [12]  106 	nop
      000012                        107 sdcc_atomic_exchange_xdata_impl:
      000012 E0               [24]  108 	movx	a, @dptr
      000013 FB               [12]  109 	mov	r3, a
      000014 EA               [12]  110 	mov	a, r2
      000015 F0               [24]  111 	movx	@dptr, a
      000016 80 24            [24]  112 	sjmp	sdcc_atomic_exchange_exit
      000018                        113 sdcc_atomic_compare_exchange_idata_impl:
      000018 E6               [12]  114 	mov	a, @r0
      000019 B5 02 02         [24]  115 	cjne	a, ar2, .+#5
      00001C EB               [12]  116 	mov	a, r3
      00001D F6               [12]  117 	mov	@r0, a
      00001E 22               [24]  118 	ret
      00001F 00               [12]  119 	nop
      000020                        120 sdcc_atomic_compare_exchange_pdata_impl:
      000020 E2               [24]  121 	movx	a, @r0
      000021 B5 02 02         [24]  122 	cjne	a, ar2, .+#5
      000024 EB               [12]  123 	mov	a, r3
      000025 F2               [24]  124 	movx	@r0, a
      000026 22               [24]  125 	ret
      000027 00               [12]  126 	nop
      000028                        127 sdcc_atomic_compare_exchange_xdata_impl:
      000028 E0               [24]  128 	movx	a, @dptr
      000029 B5 02 02         [24]  129 	cjne	a, ar2, .+#5
      00002C EB               [12]  130 	mov	a, r3
      00002D F0               [24]  131 	movx	@dptr, a
      00002E 22               [24]  132 	ret
      00002F                        133 sdcc_atomic_exchange_rollback_end::
                                    134 
      00002F                        135 sdcc_atomic_exchange_gptr_impl::
      00002F 30 F6 E0         [24]  136 	jnb	b.6, sdcc_atomic_exchange_xdata_impl
      000032 A8 82            [24]  137 	mov	r0, dpl
      000034 20 F5 D3         [24]  138 	jb	b.5, sdcc_atomic_exchange_pdata_impl
      000037                        139 sdcc_atomic_exchange_idata_impl:
      000037 EA               [12]  140 	mov	a, r2
      000038 C6               [12]  141 	xch	a, @r0
      000039 F5 82            [12]  142 	mov	dpl, a
      00003B 22               [24]  143 	ret
      00003C                        144 sdcc_atomic_exchange_exit:
      00003C 8B 82            [24]  145 	mov	dpl, r3
      00003E 22               [24]  146 	ret
      00003F                        147 sdcc_atomic_compare_exchange_gptr_impl::
      00003F 30 F6 E6         [24]  148 	jnb	b.6, sdcc_atomic_compare_exchange_xdata_impl
      000042 A8 82            [24]  149 	mov	r0, dpl
      000044 20 F5 D9         [24]  150 	jb	b.5, sdcc_atomic_compare_exchange_pdata_impl
      000047 80 CF            [24]  151 	sjmp	sdcc_atomic_compare_exchange_idata_impl
                                    152 ;--------------------------------------------------------
                                    153 ; global & static initialisations
                                    154 ;--------------------------------------------------------
                                    155 	.area HOME    (CODE)
                                    156 	.area GSINIT  (CODE)
                                    157 	.area GSFINAL (CODE)
                                    158 	.area GSINIT  (CODE)
                                    159 	.globl __sdcc_gsinit_startup
                                    160 	.globl __sdcc_program_startup
                                    161 	.globl __start__stack
                                    162 	.globl __mcs51_genXINIT
                                    163 	.globl __mcs51_genXRAMCLEAR
                                    164 	.globl __mcs51_genRAMCLEAR
                                    165 	.area GSFINAL (CODE)
      0000A7 02 00 49         [24]  166 	ljmp	__sdcc_program_startup
                                    167 ;--------------------------------------------------------
                                    168 ; Home
                                    169 ;--------------------------------------------------------
                                    170 	.area HOME    (CODE)
                                    171 	.area HOME    (CODE)
      000049                        172 __sdcc_program_startup:
      000049 12 01 B6         [24]  173 	lcall	_main
      00004C                        174 __sdcc_program_exit:
      00004C 80 FE            [24]  175 	sjmp	.
                                    176 ;	return from main will return to caller
                                    177 ;--------------------------------------------------------
                                    178 ; code
                                    179 ;--------------------------------------------------------
                                    180 	.area CSEG    (CODE)
                                    181 ;------------------------------------------------------------
                                    182 ;Allocation info for local variables in function 'wd'
                                    183 ;------------------------------------------------------------
                                    184 ;t             Allocated to registers r6 r7 
                                    185 ;s             Allocated to registers r5 
                                    186 ;------------------------------------------------------------
                                    187 ;	eeprom_dump_bus.c:101: static unsigned char wd(void)
                                    188 ;	-----------------------------------------
                                    189 ;	 function wd
                                    190 ;	-----------------------------------------
      0000AA                        191 _wd:
                           000007   192 	ar7 = 0x07
                           000006   193 	ar6 = 0x06
                           000005   194 	ar5 = 0x05
                           000004   195 	ar4 = 0x04
                           000003   196 	ar3 = 0x03
                           000002   197 	ar2 = 0x02
                           000001   198 	ar1 = 0x01
                           000000   199 	ar0 = 0x00
                                    200 ;	eeprom_dump_bus.c:105: for (t = 0; t < 30000; t++) {
      0000AA 7E 00            [12]  201 	mov	r6,#0x00
      0000AC 7F 00            [12]  202 	mov	r7,#0x00
      0000AE                        203 00104$:
                                    204 ;	eeprom_dump_bus.c:106: s = I2CS;
      0000AE 90 E6 78         [24]  205 	mov	dptr,#0xe678
      0000B1 E0               [24]  206 	movx	a,@dptr
                                    207 ;	eeprom_dump_bus.c:107: if (s & (ST_DONE | ST_BERR))
      0000B2 FD               [12]  208 	mov	r5,a
      0000B3 54 05            [12]  209 	anl	a,#0x05
      0000B5 60 03            [24]  210 	jz	00105$
                                    211 ;	eeprom_dump_bus.c:108: return s;
      0000B7 8D 82            [24]  212 	mov	dpl, r5
      0000B9 22               [24]  213 	ret
      0000BA                        214 00105$:
                                    215 ;	eeprom_dump_bus.c:105: for (t = 0; t < 30000; t++) {
      0000BA 0E               [12]  216 	inc	r6
      0000BB BE 00 01         [24]  217 	cjne	r6,#0x00,00130$
      0000BE 0F               [12]  218 	inc	r7
      0000BF                        219 00130$:
      0000BF C3               [12]  220 	clr	c
      0000C0 EE               [12]  221 	mov	a,r6
      0000C1 94 30            [12]  222 	subb	a,#0x30
      0000C3 EF               [12]  223 	mov	a,r7
      0000C4 94 75            [12]  224 	subb	a,#0x75
      0000C6 40 E6            [24]  225 	jc	00104$
                                    226 ;	eeprom_dump_bus.c:110: return s;
      0000C8 8D 82            [24]  227 	mov	dpl, r5
                                    228 ;	eeprom_dump_bus.c:111: }
      0000CA 22               [24]  229 	ret
                                    230 ;------------------------------------------------------------
                                    231 ;Allocation info for local variables in function 'stop'
                                    232 ;------------------------------------------------------------
                                    233 ;t             Allocated to registers r6 r7 
                                    234 ;------------------------------------------------------------
                                    235 ;	eeprom_dump_bus.c:113: static void stop(void)
                                    236 ;	-----------------------------------------
                                    237 ;	 function stop
                                    238 ;	-----------------------------------------
      0000CB                        239 _stop:
                                    240 ;	eeprom_dump_bus.c:116: I2CS = ST_STOP;
      0000CB 90 E6 78         [24]  241 	mov	dptr,#0xe678
      0000CE 74 40            [12]  242 	mov	a,#0x40
      0000D0 F0               [24]  243 	movx	@dptr,a
                                    244 ;	eeprom_dump_bus.c:117: for (t = 0; t < 30000; t++)
      0000D1 7E 00            [12]  245 	mov	r6,#0x00
      0000D3 7F 00            [12]  246 	mov	r7,#0x00
      0000D5                        247 00104$:
                                    248 ;	eeprom_dump_bus.c:118: if (!(I2CS & ST_STOP))
      0000D5 90 E6 78         [24]  249 	mov	dptr,#0xe678
      0000D8 E0               [24]  250 	movx	a,@dptr
      0000D9 30 E6 0E         [24]  251 	jnb	acc.6,00106$
                                    252 ;	eeprom_dump_bus.c:117: for (t = 0; t < 30000; t++)
      0000DC 0E               [12]  253 	inc	r6
      0000DD BE 00 01         [24]  254 	cjne	r6,#0x00,00124$
      0000E0 0F               [12]  255 	inc	r7
      0000E1                        256 00124$:
      0000E1 C3               [12]  257 	clr	c
      0000E2 EE               [12]  258 	mov	a,r6
      0000E3 94 30            [12]  259 	subb	a,#0x30
      0000E5 EF               [12]  260 	mov	a,r7
      0000E6 94 75            [12]  261 	subb	a,#0x75
      0000E8 40 EB            [24]  262 	jc	00104$
      0000EA                        263 00106$:
                                    264 ;	eeprom_dump_bus.c:120: }
      0000EA 22               [24]  265 	ret
                                    266 ;------------------------------------------------------------
                                    267 ;Allocation info for local variables in function 'dump'
                                    268 ;------------------------------------------------------------
                                    269 ;out           Allocated with name '_dump_PARM_2'
                                    270 ;addr8         Allocated to registers r7 
                                    271 ;i             Allocated to registers r5 r6 
                                    272 ;s             Allocated to registers r7 
                                    273 ;------------------------------------------------------------
                                    274 ;	eeprom_dump_bus.c:125: static unsigned char dump(unsigned char addr8, __xdata unsigned char *out)
                                    275 ;	-----------------------------------------
                                    276 ;	 function dump
                                    277 ;	-----------------------------------------
      0000EB                        278 _dump:
      0000EB AF 82            [24]  279 	mov	r7, dpl
                                    280 ;	eeprom_dump_bus.c:130: for (i = 0; i < 256; i++)
      0000ED 7D 00            [12]  281 	mov	r5,#0x00
      0000EF 7E 00            [12]  282 	mov	r6,#0x00
      0000F1                        283 00116$:
                                    284 ;	eeprom_dump_bus.c:131: out[i] = 0xEE;                       /* "never read" sentinel */
      0000F1 ED               [12]  285 	mov	a,r5
      0000F2 25 08            [12]  286 	add	a, _dump_PARM_2
      0000F4 F5 82            [12]  287 	mov	dpl,a
      0000F6 EE               [12]  288 	mov	a,r6
      0000F7 35 09            [12]  289 	addc	a, (_dump_PARM_2 + 1)
      0000F9 F5 83            [12]  290 	mov	dph,a
      0000FB 74 EE            [12]  291 	mov	a,#0xee
      0000FD F0               [24]  292 	movx	@dptr,a
                                    293 ;	eeprom_dump_bus.c:130: for (i = 0; i < 256; i++)
      0000FE 0D               [12]  294 	inc	r5
      0000FF BD 00 01         [24]  295 	cjne	r5,#0x00,00195$
      000102 0E               [12]  296 	inc	r6
      000103                        297 00195$:
      000103 74 FF            [12]  298 	mov	a,#0x100 - 0x01
      000105 2E               [12]  299 	add	a,r6
      000106 50 E9            [24]  300 	jnc	00116$
                                    301 ;	eeprom_dump_bus.c:133: I2CS  = ST_START;
      000108 90 E6 78         [24]  302 	mov	dptr,#0xe678
      00010B 74 80            [12]  303 	mov	a,#0x80
      00010D F0               [24]  304 	movx	@dptr,a
                                    305 ;	eeprom_dump_bus.c:134: I2DAT = addr8;                           /* device address, write dir */
      00010E A3               [24]  306 	inc	dptr
      00010F EF               [12]  307 	mov	a,r7
      000110 F0               [24]  308 	movx	@dptr,a
                                    309 ;	eeprom_dump_bus.c:135: s = wd();
      000111 C0 07            [24]  310 	push	ar7
      000113 12 00 AA         [24]  311 	lcall	_wd
      000116 AE 82            [24]  312 	mov	r6, dpl
      000118 D0 07            [24]  313 	pop	ar7
                                    314 ;	eeprom_dump_bus.c:136: if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 1; }
      00011A EE               [12]  315 	mov	a,r6
      00011B 30 E1 04         [24]  316 	jnb	acc.1,00102$
      00011E EE               [12]  317 	mov	a,r6
      00011F 30 E2 07         [24]  318 	jnb	acc.2,00103$
      000122                        319 00102$:
      000122 12 00 CB         [24]  320 	lcall	_stop
      000125 75 82 01         [24]  321 	mov	dpl, #0x01
      000128 22               [24]  322 	ret
      000129                        323 00103$:
                                    324 ;	eeprom_dump_bus.c:138: I2DAT = 0x00;                            /* word address 0 -- pointer only */
      000129 90 E6 79         [24]  325 	mov	dptr,#0xe679
      00012C E4               [12]  326 	clr	a
      00012D F0               [24]  327 	movx	@dptr,a
                                    328 ;	eeprom_dump_bus.c:139: s = wd();
      00012E C0 07            [24]  329 	push	ar7
      000130 12 00 AA         [24]  330 	lcall	_wd
      000133 AE 82            [24]  331 	mov	r6, dpl
      000135 D0 07            [24]  332 	pop	ar7
                                    333 ;	eeprom_dump_bus.c:140: if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 2; }
      000137 EE               [12]  334 	mov	a,r6
      000138 30 E1 04         [24]  335 	jnb	acc.1,00105$
      00013B EE               [12]  336 	mov	a,r6
      00013C 30 E2 07         [24]  337 	jnb	acc.2,00106$
      00013F                        338 00105$:
      00013F 12 00 CB         [24]  339 	lcall	_stop
      000142 75 82 02         [24]  340 	mov	dpl, #0x02
      000145 22               [24]  341 	ret
      000146                        342 00106$:
                                    343 ;	eeprom_dump_bus.c:142: I2CS  = ST_START;                        /* REPEATED start, no STOP first */
      000146 90 E6 78         [24]  344 	mov	dptr,#0xe678
      000149 74 80            [12]  345 	mov	a,#0x80
      00014B F0               [24]  346 	movx	@dptr,a
                                    347 ;	eeprom_dump_bus.c:143: I2DAT = (unsigned char)(addr8 | 1);      /* device address, read dir */
      00014C 43 07 01         [24]  348 	orl	ar7,#0x01
      00014F 90 E6 79         [24]  349 	mov	dptr,#0xe679
      000152 EF               [12]  350 	mov	a,r7
      000153 F0               [24]  351 	movx	@dptr,a
                                    352 ;	eeprom_dump_bus.c:144: s = wd();
      000154 12 00 AA         [24]  353 	lcall	_wd
                                    354 ;	eeprom_dump_bus.c:145: if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 3; }
      000157 E5 82            [12]  355 	mov	a,dpl
      000159 FF               [12]  356 	mov	r7,a
      00015A 30 E1 04         [24]  357 	jnb	acc.1,00108$
      00015D EF               [12]  358 	mov	a,r7
      00015E 30 E2 07         [24]  359 	jnb	acc.2,00109$
      000161                        360 00108$:
      000161 12 00 CB         [24]  361 	lcall	_stop
      000164 75 82 03         [24]  362 	mov	dpl, #0x03
      000167 22               [24]  363 	ret
      000168                        364 00109$:
                                    365 ;	eeprom_dump_bus.c:147: (void)I2DAT;                             /* starts the first byte */
      000168 90 E6 79         [24]  366 	mov	dptr,#0xe679
      00016B E0               [24]  367 	movx	a,@dptr
                                    368 ;	eeprom_dump_bus.c:148: for (i = 0; i < 256; i++) {
      00016C 7E 00            [12]  369 	mov	r6,#0x00
      00016E 7F 00            [12]  370 	mov	r7,#0x00
      000170                        371 00118$:
                                    372 ;	eeprom_dump_bus.c:149: if (i == 255)
      000170 BE FF 09         [24]  373 	cjne	r6,#0xff,00112$
      000173 BF 00 06         [24]  374 	cjne	r7,#0x00,00112$
                                    375 ;	eeprom_dump_bus.c:150: I2CS = ST_LASTRD;                /* NACK the final byte */
      000176 90 E6 78         [24]  376 	mov	dptr,#0xe678
      000179 74 20            [12]  377 	mov	a,#0x20
      00017B F0               [24]  378 	movx	@dptr,a
      00017C                        379 00112$:
                                    380 ;	eeprom_dump_bus.c:151: s = wd();
      00017C C0 07            [24]  381 	push	ar7
      00017E C0 06            [24]  382 	push	ar6
      000180 12 00 AA         [24]  383 	lcall	_wd
      000183 AD 82            [24]  384 	mov	r5, dpl
      000185 D0 06            [24]  385 	pop	ar6
      000187 D0 07            [24]  386 	pop	ar7
                                    387 ;	eeprom_dump_bus.c:152: if (s & ST_BERR) { stop(); return 4; }
      000189 ED               [12]  388 	mov	a,r5
      00018A 30 E2 07         [24]  389 	jnb	acc.2,00114$
      00018D 12 00 CB         [24]  390 	lcall	_stop
      000190 75 82 04         [24]  391 	mov	dpl, #0x04
      000193 22               [24]  392 	ret
      000194                        393 00114$:
                                    394 ;	eeprom_dump_bus.c:153: out[i] = I2DAT;
      000194 EE               [12]  395 	mov	a,r6
      000195 25 08            [12]  396 	add	a, _dump_PARM_2
      000197 FC               [12]  397 	mov	r4,a
      000198 EF               [12]  398 	mov	a,r7
      000199 35 09            [12]  399 	addc	a, (_dump_PARM_2 + 1)
      00019B FD               [12]  400 	mov	r5,a
      00019C 90 E6 79         [24]  401 	mov	dptr,#0xe679
      00019F E0               [24]  402 	movx	a,@dptr
      0001A0 8C 82            [24]  403 	mov	dpl,r4
      0001A2 8D 83            [24]  404 	mov	dph,r5
      0001A4 F0               [24]  405 	movx	@dptr,a
                                    406 ;	eeprom_dump_bus.c:148: for (i = 0; i < 256; i++) {
      0001A5 0E               [12]  407 	inc	r6
      0001A6 BE 00 01         [24]  408 	cjne	r6,#0x00,00206$
      0001A9 0F               [12]  409 	inc	r7
      0001AA                        410 00206$:
      0001AA 74 FF            [12]  411 	mov	a,#0x100 - 0x01
      0001AC 2F               [12]  412 	add	a,r7
      0001AD 50 C1            [24]  413 	jnc	00118$
                                    414 ;	eeprom_dump_bus.c:155: stop();
      0001AF 12 00 CB         [24]  415 	lcall	_stop
                                    416 ;	eeprom_dump_bus.c:156: return 0;
      0001B2 75 82 00         [24]  417 	mov	dpl, #0x00
                                    418 ;	eeprom_dump_bus.c:157: }
      0001B5 22               [24]  419 	ret
                                    420 ;------------------------------------------------------------
                                    421 ;Allocation info for local variables in function 'main'
                                    422 ;------------------------------------------------------------
                                    423 ;n             Allocated to registers r7 
                                    424 ;------------------------------------------------------------
                                    425 ;	eeprom_dump_bus.c:159: void main(void)
                                    426 ;	-----------------------------------------
                                    427 ;	 function main
                                    428 ;	-----------------------------------------
      0001B6                        429 _main:
                                    430 ;	eeprom_dump_bus.c:163: for (n = 0; n < 16; n++)
      0001B6 7F 00            [12]  431 	mov	r7,#0x00
      0001B8                        432 00104$:
                                    433 ;	eeprom_dump_bus.c:164: st[n] = 0;
      0001B8 8F 82            [24]  434 	mov	dpl,r7
      0001BA 75 83 0C         [24]  435 	mov	dph,#(_st >> 8)
      0001BD E4               [12]  436 	clr	a
      0001BE F0               [24]  437 	movx	@dptr,a
                                    438 ;	eeprom_dump_bus.c:163: for (n = 0; n < 16; n++)
      0001BF 0F               [12]  439 	inc	r7
      0001C0 BF 10 00         [24]  440 	cjne	r7,#0x10,00149$
      0001C3                        441 00149$:
      0001C3 40 F3            [24]  442 	jc	00104$
                                    443 ;	eeprom_dump_bus.c:168: for (n = 0; n < NDEV; n++)
      0001C5 7F 00            [12]  444 	mov	r7,#0x00
      0001C7                        445 00106$:
                                    446 ;	eeprom_dump_bus.c:169: st[n] = dump((unsigned char)(0xA0 + (n << 1)), buf[n]);
      0001C7 8F 05            [24]  447 	mov	ar5,r7
      0001C9 7E 0C            [12]  448 	mov	r6,#(_st >> 8)
      0001CB EF               [12]  449 	mov	a,r7
      0001CC 2F               [12]  450 	add	a,r7
      0001CD 24 A0            [12]  451 	add	a,#0xa0
      0001CF F5 82            [12]  452 	mov	dpl,a
      0001D1 8F 03            [24]  453 	mov	ar3,r7
      0001D3 8B 04            [24]  454 	mov	ar4,r3
      0001D5 7B 00            [12]  455 	mov	r3,#0x00
      0001D7 8B 08            [24]  456 	mov	_dump_PARM_2,r3
      0001D9 74 04            [12]  457 	mov	a,#(_buf >> 8)
      0001DB 2C               [12]  458 	add	a,r4
      0001DC F5 09            [12]  459 	mov	(_dump_PARM_2 + 1),a
      0001DE C0 07            [24]  460 	push	ar7
      0001E0 C0 06            [24]  461 	push	ar6
      0001E2 C0 05            [24]  462 	push	ar5
      0001E4 12 00 EB         [24]  463 	lcall	_dump
      0001E7 AC 82            [24]  464 	mov	r4, dpl
      0001E9 D0 05            [24]  465 	pop	ar5
      0001EB D0 06            [24]  466 	pop	ar6
      0001ED D0 07            [24]  467 	pop	ar7
      0001EF 8D 82            [24]  468 	mov	dpl,r5
      0001F1 8E 83            [24]  469 	mov	dph,r6
      0001F3 EC               [12]  470 	mov	a,r4
      0001F4 F0               [24]  471 	movx	@dptr,a
                                    472 ;	eeprom_dump_bus.c:168: for (n = 0; n < NDEV; n++)
      0001F5 0F               [12]  473 	inc	r7
      0001F6 BF 08 00         [24]  474 	cjne	r7,#0x08,00151$
      0001F9                        475 00151$:
      0001F9 40 CC            [24]  476 	jc	00106$
                                    477 ;	eeprom_dump_bus.c:171: st[8] = 0xC0; st[9] = 0xDE; st[10] = 0xF1; st[11] = 0x35;
      0001FB 90 0C 08         [24]  478 	mov	dptr,#(_st + 0x0008)
      0001FE 74 C0            [12]  479 	mov	a,#0xc0
      000200 F0               [24]  480 	movx	@dptr,a
      000201 90 0C 09         [24]  481 	mov	dptr,#(_st + 0x0009)
      000204 74 DE            [12]  482 	mov	a,#0xde
      000206 F0               [24]  483 	movx	@dptr,a
      000207 90 0C 0A         [24]  484 	mov	dptr,#(_st + 0x000a)
      00020A 74 F1            [12]  485 	mov	a,#0xf1
      00020C F0               [24]  486 	movx	@dptr,a
      00020D 90 0C 0B         [24]  487 	mov	dptr,#(_st + 0x000b)
      000210 74 35            [12]  488 	mov	a,#0x35
      000212 F0               [24]  489 	movx	@dptr,a
                                    490 ;	eeprom_dump_bus.c:172: st[12] = 2;                              /* firmware format version */
      000213 90 0C 0C         [24]  491 	mov	dptr,#(_st + 0x000c)
      000216 74 02            [12]  492 	mov	a,#0x02
      000218 F0               [24]  493 	movx	@dptr,a
                                    494 ;	eeprom_dump_bus.c:173: st[13] = NDEV;
      000219 90 0C 0D         [24]  495 	mov	dptr,#(_st + 0x000d)
      00021C 74 08            [12]  496 	mov	a,#0x08
      00021E F0               [24]  497 	movx	@dptr,a
      00021F                        498 00109$:
                                    499 ;	eeprom_dump_bus.c:177: }
      00021F 80 FE            [24]  500 	sjmp	00109$
                                    501 	.area CSEG    (CODE)
                                    502 	.area CONST   (CODE)
                                    503 	.area XINIT   (CODE)
                                    504 	.area CABS    (ABS,CODE)
