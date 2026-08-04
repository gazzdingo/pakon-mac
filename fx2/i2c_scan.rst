                                      1 ;--------------------------------------------------------
                                      2 ; File Created by SDCC : free open source ISO C Compiler
                                      3 ; Version 4.6.0 #16555 (Mac OS X ppc)
                                      4 ;--------------------------------------------------------
                                      5 	.module i2c_scan
                                      6 	
                                      7 	.optsdcc -mmcs51 --model-small
                                      8 ;--------------------------------------------------------
                                      9 ; Public variables in this module
                                     10 ;--------------------------------------------------------
                                     11 	.globl _main
                                     12 	.globl _marker
                                     13 	.globl _results
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
                                     33 ;--------------------------------------------------------
                                     34 ; overlayable items in internal ram
                                     35 ;--------------------------------------------------------
                                     36 	.area	OSEG    (OVR,DATA)
                                     37 ;--------------------------------------------------------
                                     38 ; Stack segment in internal ram
                                     39 ;--------------------------------------------------------
                                     40 	.area SSEG
      000008                         41 __start__stack:
      000008                         42 	.ds	1
                                     43 
                                     44 ;--------------------------------------------------------
                                     45 ; indirectly addressable internal ram data
                                     46 ;--------------------------------------------------------
                                     47 	.area ISEG    (DATA)
                                     48 ;--------------------------------------------------------
                                     49 ; absolute internal ram data
                                     50 ;--------------------------------------------------------
                                     51 	.area IABS    (ABS,DATA)
                                     52 	.area IABS    (ABS,DATA)
                                     53 ;--------------------------------------------------------
                                     54 ; bit data
                                     55 ;--------------------------------------------------------
                                     56 	.area BSEG    (BIT)
                                     57 ;--------------------------------------------------------
                                     58 ; paged external ram data
                                     59 ;--------------------------------------------------------
                                     60 	.area PSEG    (PAG,XDATA)
                                     61 ;--------------------------------------------------------
                                     62 ; uninitialized external ram data
                                     63 ;--------------------------------------------------------
                                     64 	.area XSEG    (XDATA)
                           000400    65 _results	=	0x0400
                           000480    66 _marker	=	0x0480
                                     67 ;--------------------------------------------------------
                                     68 ; absolute external ram data
                                     69 ;--------------------------------------------------------
                                     70 	.area XABS    (ABS,XDATA)
                                     71 ;--------------------------------------------------------
                                     72 ; initialized external ram data
                                     73 ;--------------------------------------------------------
                                     74 	.area XISEG   (XDATA)
                                     75 	.area HOME    (CODE)
                                     76 	.area GSINIT0 (CODE)
                                     77 	.area GSINIT1 (CODE)
                                     78 	.area GSINIT2 (CODE)
                                     79 	.area GSINIT3 (CODE)
                                     80 	.area GSINIT4 (CODE)
                                     81 	.area GSINIT5 (CODE)
                                     82 	.area GSINIT  (CODE)
                                     83 	.area GSFINAL (CODE)
                                     84 	.area CSEG    (CODE)
                                     85 ;--------------------------------------------------------
                                     86 ; interrupt vector
                                     87 ;--------------------------------------------------------
                                     88 	.area HOME    (CODE)
      000000                         89 __interrupt_vect:
      000000 02 00 4E         [24]   90 	ljmp	__sdcc_gsinit_startup
                                     91 ; restartable atomic support routines
      000003                         92 	.ds	5
      000008                         93 sdcc_atomic_exchange_rollback_start::
      000008 00               [12]   94 	nop
      000009 00               [12]   95 	nop
      00000A                         96 sdcc_atomic_exchange_pdata_impl:
      00000A E2               [24]   97 	movx	a, @r0
      00000B FB               [12]   98 	mov	r3, a
      00000C EA               [12]   99 	mov	a, r2
      00000D F2               [24]  100 	movx	@r0, a
      00000E 80 2C            [24]  101 	sjmp	sdcc_atomic_exchange_exit
      000010 00               [12]  102 	nop
      000011 00               [12]  103 	nop
      000012                        104 sdcc_atomic_exchange_xdata_impl:
      000012 E0               [24]  105 	movx	a, @dptr
      000013 FB               [12]  106 	mov	r3, a
      000014 EA               [12]  107 	mov	a, r2
      000015 F0               [24]  108 	movx	@dptr, a
      000016 80 24            [24]  109 	sjmp	sdcc_atomic_exchange_exit
      000018                        110 sdcc_atomic_compare_exchange_idata_impl:
      000018 E6               [12]  111 	mov	a, @r0
      000019 B5 02 02         [24]  112 	cjne	a, ar2, .+#5
      00001C EB               [12]  113 	mov	a, r3
      00001D F6               [12]  114 	mov	@r0, a
      00001E 22               [24]  115 	ret
      00001F 00               [12]  116 	nop
      000020                        117 sdcc_atomic_compare_exchange_pdata_impl:
      000020 E2               [24]  118 	movx	a, @r0
      000021 B5 02 02         [24]  119 	cjne	a, ar2, .+#5
      000024 EB               [12]  120 	mov	a, r3
      000025 F2               [24]  121 	movx	@r0, a
      000026 22               [24]  122 	ret
      000027 00               [12]  123 	nop
      000028                        124 sdcc_atomic_compare_exchange_xdata_impl:
      000028 E0               [24]  125 	movx	a, @dptr
      000029 B5 02 02         [24]  126 	cjne	a, ar2, .+#5
      00002C EB               [12]  127 	mov	a, r3
      00002D F0               [24]  128 	movx	@dptr, a
      00002E 22               [24]  129 	ret
      00002F                        130 sdcc_atomic_exchange_rollback_end::
                                    131 
      00002F                        132 sdcc_atomic_exchange_gptr_impl::
      00002F 30 F6 E0         [24]  133 	jnb	b.6, sdcc_atomic_exchange_xdata_impl
      000032 A8 82            [24]  134 	mov	r0, dpl
      000034 20 F5 D3         [24]  135 	jb	b.5, sdcc_atomic_exchange_pdata_impl
      000037                        136 sdcc_atomic_exchange_idata_impl:
      000037 EA               [12]  137 	mov	a, r2
      000038 C6               [12]  138 	xch	a, @r0
      000039 F5 82            [12]  139 	mov	dpl, a
      00003B 22               [24]  140 	ret
      00003C                        141 sdcc_atomic_exchange_exit:
      00003C 8B 82            [24]  142 	mov	dpl, r3
      00003E 22               [24]  143 	ret
      00003F                        144 sdcc_atomic_compare_exchange_gptr_impl::
      00003F 30 F6 E6         [24]  145 	jnb	b.6, sdcc_atomic_compare_exchange_xdata_impl
      000042 A8 82            [24]  146 	mov	r0, dpl
      000044 20 F5 D9         [24]  147 	jb	b.5, sdcc_atomic_compare_exchange_pdata_impl
      000047 80 CF            [24]  148 	sjmp	sdcc_atomic_compare_exchange_idata_impl
                                    149 ;--------------------------------------------------------
                                    150 ; global & static initialisations
                                    151 ;--------------------------------------------------------
                                    152 	.area HOME    (CODE)
                                    153 	.area GSINIT  (CODE)
                                    154 	.area GSFINAL (CODE)
                                    155 	.area GSINIT  (CODE)
                                    156 	.globl __sdcc_gsinit_startup
                                    157 	.globl __sdcc_program_startup
                                    158 	.globl __start__stack
                                    159 	.globl __mcs51_genXINIT
                                    160 	.globl __mcs51_genXRAMCLEAR
                                    161 	.globl __mcs51_genRAMCLEAR
                                    162 	.area GSFINAL (CODE)
      0000A7 02 00 49         [24]  163 	ljmp	__sdcc_program_startup
                                    164 ;--------------------------------------------------------
                                    165 ; Home
                                    166 ;--------------------------------------------------------
                                    167 	.area HOME    (CODE)
                                    168 	.area HOME    (CODE)
      000049                        169 __sdcc_program_startup:
      000049 12 01 2D         [24]  170 	lcall	_main
      00004C                        171 __sdcc_program_exit:
      00004C 80 FE            [24]  172 	sjmp	.
                                    173 ;	return from main will return to caller
                                    174 ;--------------------------------------------------------
                                    175 ; code
                                    176 ;--------------------------------------------------------
                                    177 	.area CSEG    (CODE)
                                    178 ;------------------------------------------------------------
                                    179 ;Allocation info for local variables in function 'probe'
                                    180 ;------------------------------------------------------------
                                    181 ;a             Allocated to registers r7 
                                    182 ;t             Allocated to registers r5 r6 
                                    183 ;st            Allocated to registers r4 
                                    184 ;------------------------------------------------------------
                                    185 ;	i2c_scan.c:42: static void probe(unsigned char a)
                                    186 ;	-----------------------------------------
                                    187 ;	 function probe
                                    188 ;	-----------------------------------------
      0000AA                        189 _probe:
                           000007   190 	ar7 = 0x07
                           000006   191 	ar6 = 0x06
                           000005   192 	ar5 = 0x05
                           000004   193 	ar4 = 0x04
                           000003   194 	ar3 = 0x03
                           000002   195 	ar2 = 0x02
                           000001   196 	ar1 = 0x01
                           000000   197 	ar0 = 0x00
      0000AA AF 82            [24]  198 	mov	r7, dpl
                                    199 ;	i2c_scan.c:50: I2CS  = ST_START;
      0000AC 90 E6 78         [24]  200 	mov	dptr,#0xe678
      0000AF 74 80            [12]  201 	mov	a,#0x80
      0000B1 F0               [24]  202 	movx	@dptr,a
                                    203 ;	i2c_scan.c:51: I2DAT = (unsigned char)((a << 1) | 1);   /* READ address, no data sent */
      0000B2 EF               [12]  204 	mov	a,r7
      0000B3 2F               [12]  205 	add	a,r7
      0000B4 FE               [12]  206 	mov	r6,a
      0000B5 43 06 01         [24]  207 	orl	ar6,#0x01
      0000B8 90 E6 79         [24]  208 	mov	dptr,#0xe679
      0000BB EE               [12]  209 	mov	a,r6
      0000BC F0               [24]  210 	movx	@dptr,a
                                    211 ;	i2c_scan.c:53: for (t = 0; t < 30000; t++) {
      0000BD 7D 00            [12]  212 	mov	r5,#0x00
      0000BF 7E 00            [12]  213 	mov	r6,#0x00
      0000C1                        214 00113$:
                                    215 ;	i2c_scan.c:54: st = I2CS;
      0000C1 90 E6 78         [24]  216 	mov	dptr,#0xe678
      0000C4 E0               [24]  217 	movx	a,@dptr
                                    218 ;	i2c_scan.c:55: if (st & (ST_DONE | ST_BERR))
      0000C5 FC               [12]  219 	mov	r4,a
      0000C6 54 05            [12]  220 	anl	a,#0x05
      0000C8 70 0E            [24]  221 	jnz	00103$
                                    222 ;	i2c_scan.c:53: for (t = 0; t < 30000; t++) {
      0000CA 0D               [12]  223 	inc	r5
      0000CB BD 00 01         [24]  224 	cjne	r5,#0x00,00182$
      0000CE 0E               [12]  225 	inc	r6
      0000CF                        226 00182$:
      0000CF C3               [12]  227 	clr	c
      0000D0 ED               [12]  228 	mov	a,r5
      0000D1 94 30            [12]  229 	subb	a,#0x30
      0000D3 EE               [12]  230 	mov	a,r6
      0000D4 94 75            [12]  231 	subb	a,#0x75
      0000D6 40 E9            [24]  232 	jc	00113$
      0000D8                        233 00103$:
                                    234 ;	i2c_scan.c:58: results[a] = st;                          /* captured before recovery */
      0000D8 8F 82            [24]  235 	mov	dpl,r7
      0000DA 75 83 04         [24]  236 	mov	dph,#(_results >> 8)
      0000DD EC               [12]  237 	mov	a,r4
      0000DE F0               [24]  238 	movx	@dptr,a
                                    239 ;	i2c_scan.c:64: if ((st & ST_ACK) && !(st & ST_BERR)) {
      0000DF EC               [12]  240 	mov	a,r4
      0000E0 30 E1 2A         [24]  241 	jnb	acc.1,00108$
      0000E3 EC               [12]  242 	mov	a,r4
      0000E4 20 E2 26         [24]  243 	jb	acc.2,00108$
                                    244 ;	i2c_scan.c:65: I2CS = ST_LASTRD;
      0000E7 90 E6 78         [24]  245 	mov	dptr,#0xe678
      0000EA 74 20            [12]  246 	mov	a,#0x20
      0000EC F0               [24]  247 	movx	@dptr,a
                                    248 ;	i2c_scan.c:66: (void)I2DAT;                          /* dummy read starts the byte */
      0000ED A3               [24]  249 	inc	dptr
      0000EE E0               [24]  250 	movx	a,@dptr
                                    251 ;	i2c_scan.c:67: for (t = 0; t < 30000; t++)
      0000EF 7E 00            [12]  252 	mov	r6,#0x00
      0000F1 7F 00            [12]  253 	mov	r7,#0x00
      0000F3                        254 00115$:
                                    255 ;	i2c_scan.c:68: if (I2CS & (ST_DONE | ST_BERR))
      0000F3 90 E6 78         [24]  256 	mov	dptr,#0xe678
      0000F6 E0               [24]  257 	movx	a,@dptr
      0000F7 54 05            [12]  258 	anl	a,#0x05
      0000F9 70 0E            [24]  259 	jnz	00106$
                                    260 ;	i2c_scan.c:67: for (t = 0; t < 30000; t++)
      0000FB 0E               [12]  261 	inc	r6
      0000FC BE 00 01         [24]  262 	cjne	r6,#0x00,00188$
      0000FF 0F               [12]  263 	inc	r7
      000100                        264 00188$:
      000100 C3               [12]  265 	clr	c
      000101 EE               [12]  266 	mov	a,r6
      000102 94 30            [12]  267 	subb	a,#0x30
      000104 EF               [12]  268 	mov	a,r7
      000105 94 75            [12]  269 	subb	a,#0x75
      000107 40 EA            [24]  270 	jc	00115$
      000109                        271 00106$:
                                    272 ;	i2c_scan.c:70: (void)I2DAT;                          /* collect it, freeing the bus */
      000109 90 E6 79         [24]  273 	mov	dptr,#0xe679
      00010C E0               [24]  274 	movx	a,@dptr
      00010D                        275 00108$:
                                    276 ;	i2c_scan.c:73: I2CS = ST_STOP;
      00010D 90 E6 78         [24]  277 	mov	dptr,#0xe678
      000110 74 40            [12]  278 	mov	a,#0x40
      000112 F0               [24]  279 	movx	@dptr,a
                                    280 ;	i2c_scan.c:74: for (t = 0; t < 30000; t++)
      000113 7E 00            [12]  281 	mov	r6,#0x00
      000115 7F 00            [12]  282 	mov	r7,#0x00
      000117                        283 00117$:
                                    284 ;	i2c_scan.c:75: if (!(I2CS & ST_STOP))
      000117 90 E6 78         [24]  285 	mov	dptr,#0xe678
      00011A E0               [24]  286 	movx	a,@dptr
      00011B 30 E6 0E         [24]  287 	jnb	acc.6,00119$
                                    288 ;	i2c_scan.c:74: for (t = 0; t < 30000; t++)
      00011E 0E               [12]  289 	inc	r6
      00011F BE 00 01         [24]  290 	cjne	r6,#0x00,00191$
      000122 0F               [12]  291 	inc	r7
      000123                        292 00191$:
      000123 C3               [12]  293 	clr	c
      000124 EE               [12]  294 	mov	a,r6
      000125 94 30            [12]  295 	subb	a,#0x30
      000127 EF               [12]  296 	mov	a,r7
      000128 94 75            [12]  297 	subb	a,#0x75
      00012A 40 EB            [24]  298 	jc	00117$
      00012C                        299 00119$:
                                    300 ;	i2c_scan.c:77: }
      00012C 22               [24]  301 	ret
                                    302 ;------------------------------------------------------------
                                    303 ;Allocation info for local variables in function 'main'
                                    304 ;------------------------------------------------------------
                                    305 ;a             Allocated to registers r7 
                                    306 ;------------------------------------------------------------
                                    307 ;	i2c_scan.c:79: void main(void)
                                    308 ;	-----------------------------------------
                                    309 ;	 function main
                                    310 ;	-----------------------------------------
      00012D                        311 _main:
                                    312 ;	i2c_scan.c:83: marker[0] = 0; marker[1] = 0; marker[2] = 0; marker[3] = 0;
      00012D 90 04 80         [24]  313 	mov	dptr,#_marker
      000130 E4               [12]  314 	clr	a
      000131 F0               [24]  315 	movx	@dptr,a
      000132 90 04 81         [24]  316 	mov	dptr,#(_marker + 0x0001)
      000135 F0               [24]  317 	movx	@dptr,a
      000136 90 04 82         [24]  318 	mov	dptr,#(_marker + 0x0002)
      000139 F0               [24]  319 	movx	@dptr,a
      00013A 90 04 83         [24]  320 	mov	dptr,#(_marker + 0x0003)
      00013D F0               [24]  321 	movx	@dptr,a
                                    322 ;	i2c_scan.c:84: for (a = 0; a < 128; a++)
      00013E FF               [12]  323 	mov	r7,a
      00013F                        324 00104$:
                                    325 ;	i2c_scan.c:85: results[a] = 0xEE;                /* "never ran" sentinel */
      00013F 8F 82            [24]  326 	mov	dpl,r7
      000141 75 83 04         [24]  327 	mov	dph,#(_results >> 8)
      000144 74 EE            [12]  328 	mov	a,#0xee
      000146 F0               [24]  329 	movx	@dptr,a
                                    330 ;	i2c_scan.c:84: for (a = 0; a < 128; a++)
      000147 0F               [12]  331 	inc	r7
      000148 BF 80 00         [24]  332 	cjne	r7,#0x80,00149$
      00014B                        333 00149$:
      00014B 40 F2            [24]  334 	jc	00104$
                                    335 ;	i2c_scan.c:87: for (a = 0; a < 128; a++)
      00014D 7F 00            [12]  336 	mov	r7,#0x00
      00014F                        337 00106$:
                                    338 ;	i2c_scan.c:88: probe(a);
      00014F 8F 82            [24]  339 	mov	dpl, r7
      000151 C0 07            [24]  340 	push	ar7
      000153 12 00 AA         [24]  341 	lcall	_probe
      000156 D0 07            [24]  342 	pop	ar7
                                    343 ;	i2c_scan.c:87: for (a = 0; a < 128; a++)
      000158 0F               [12]  344 	inc	r7
      000159 BF 80 00         [24]  345 	cjne	r7,#0x80,00151$
      00015C                        346 00151$:
      00015C 40 F1            [24]  347 	jc	00106$
                                    348 ;	i2c_scan.c:90: marker[0] = 0xC0; marker[1] = 0xDE;   /* scan complete */
      00015E 90 04 80         [24]  349 	mov	dptr,#_marker
      000161 74 C0            [12]  350 	mov	a,#0xc0
      000163 F0               [24]  351 	movx	@dptr,a
      000164 90 04 81         [24]  352 	mov	dptr,#(_marker + 0x0001)
      000167 74 DE            [12]  353 	mov	a,#0xde
      000169 F0               [24]  354 	movx	@dptr,a
                                    355 ;	i2c_scan.c:91: marker[2] = 0xF1; marker[3] = 0x35;
      00016A 90 04 82         [24]  356 	mov	dptr,#(_marker + 0x0002)
      00016D 74 F1            [12]  357 	mov	a,#0xf1
      00016F F0               [24]  358 	movx	@dptr,a
      000170 90 04 83         [24]  359 	mov	dptr,#(_marker + 0x0003)
      000173 74 35            [12]  360 	mov	a,#0x35
      000175 F0               [24]  361 	movx	@dptr,a
      000176                        362 00109$:
                                    363 ;	i2c_scan.c:95: }
      000176 80 FE            [24]  364 	sjmp	00109$
                                    365 	.area CSEG    (CODE)
                                    366 	.area CONST   (CODE)
                                    367 	.area XINIT   (CODE)
                                    368 	.area CABS    (ABS,CODE)
