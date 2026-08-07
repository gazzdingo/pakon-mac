# 42 — CCD A/D gains and offsets: the wire encoding

Written against the acquisition blocker: *"the sensor clocks but doesn't
integrate… gain/offset almost certainly need programming first."* This is where
they go and how they are encoded. `[VERIFIED-FROM-BINARY]`,
`research/native/TLB.text.asm`.

The values themselves are already recovered — `docs/37`, from the VM registry.
Both halves are now in hand.

## The two functions

`research/native/TLB.fn.txt` names them: **`FN_bDrvPutCcdAtoDGains`** and
**`FN_bDrvPutCcdAtoDOffsets`**. Both write **CCD register `0x84`** (the second
entry in `PutRegisterCcd`'s whitelist, alongside `0x82` — `docs/16`), each as
three consecutive indices.

| function | body | reg | indices | shadows |
|---|---|---|---|---|
| `FN_bDrvPutCcdAtoDGains` | `0x100298b0` | `0x84` | **2, 3, 4** | `[esi+0x340/0x344/0x348]` |
| `FN_bDrvPutCcdAtoDOffsets` | `0x100299c0` | `0x84` | **5, 6, 7** | `[esi+0x34c/0x350/0x354]` |

Both keep host-side shadows and **early-out when the value is unchanged** — the
same write-only-with-shadow pattern as `0x82` (`docs/16`). A host port must
track them, and must not assume a write happened.

## Gains — indices 2/3/4, unsigned, clamp 63

```
if (v >= 0x3f) v = 0x3f          ; 0x100298cc
PutRegisterCcd(0x84, idx, v)
```

Plain unsigned, saturating at **63**. Our recovered values are
`Gain_R = Gain_G = Gain_B = 13` — comfortably in range, no encoding needed.

## Offsets — indices 5/6/7, SIGN-MAGNITUDE, sign in bit 8

This is the one to get right. `0x100299dc`–`0x100299fc`:

```
if (v <= -255) -> error path, no write        ; 0x100299dc  jle
if (v >=  255) v = 255                        ; 0x100299e4
mag = abs(v)                                  ; cdq / xor / sub
if (v < 0) mag |= 0x100                       ; 0x100299fc  or eax, 0x100
PutRegisterCcd(0x84, idx, mag)
```

**Not two's complement.** Magnitude in bits 0–7, sign flag in **bit 8**. Range
±255. A port that writes a two's-complement `int16` will program a large
positive offset instead of a small negative one — which is exactly the kind of
fault that yields a sensor that clocks but reads flat.

Our recovered offsets encode as:

| channel | registry value | wire value |
|---|---|---|
| `Offset_R` | −18 | `18 \| 0x100` = **`0x112`** |
| `Offset_G` | −26 | `26 \| 0x100` = **`0x11A`** |
| `Offset_B` | −20 | `20 \| 0x100` = **`0x114`** |

## The full `0x84` index map seen in bring-up

| idx | written by | value |
|---|---|---|
| 0 | `0x1002d777` | `0x78` |
| 1 | `0x1002d7af` | `0x80` |
| 2,3,4 | `FN_bDrvPutCcdAtoDGains` | R, G, B gain |
| 5,6,7 | `FN_bDrvPutCcdAtoDOffsets` | R, G, B offset |

Indices 0 and 1 are written with fixed constants during bring-up and are not yet
identified. `[UNKNOWN]`

## Suggested ordering

Combining `docs/16` §"CCD init constraints" with the above. The A/D front end is
configured **before** the master acquire enable, which matches the symptom —
enabling acquisition on an unprogrammed A/D gives clocking without useful
integration.

```
1. geometry validation        uiCcdPixelHeight % 4 == 0, height/offset limits
2. 0x84 idx 0,1               0x78, 0x80
3. 0x84 idx 2,3,4             gains   13, 13, 13
4. 0x84 idx 5,6,7             offsets 0x112, 0x11A, 0x114
5. 0x82 mask 0x100            fcn.10029860
6. 0x82 idx 6                 integration time (bounded by 0xFFD)
7. 0x82 masks 0x002, 0x060    fcn.1002c340
8. 0x82 idx 0, bit 0          master acquire enable   <- the untried write
```

Steps 2–4 are the ones never sent. Step 8 is the one `docs/16` identifies as the
master enable.

## Caveat

The ordering above is assembled from separate call sites, not observed as one
trace. Steps 2–7 are individually `[VERIFIED-FROM-BINARY]`; their **sequence**
is `[INFERRED]`. If bring-up still fails with gains and offsets programmed, the
next thing to establish is the true order by tracing `fcn.1002c340`'s caller
rather than assuming this one.
