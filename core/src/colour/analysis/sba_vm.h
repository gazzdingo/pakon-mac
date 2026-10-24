#ifndef PAKON_COLOUR_ANALYSIS_SBA_VM_H
#define PAKON_COLOUR_ANALYSIS_SBA_VM_H
#include <stdint.h>
#include "internal.h"

/* PakonIMAu's SBA p-code (lab/reference pakon_sba_pcode.py + pakon_vm.py).
 *   stage 1 = SbaDecodePcode 0x102884b0: a 0x1A8-byte parameter struct (five 22-word tables + scalars);
 *   stage 2 = FUN_102a8f40's section stream, of which pcode-dls_1.7 uses sections 0 (grid dims) and 7 (the 264
 *             expression records), run by the stack VM fcn.102aadf0 (driver fcn.102ac140). */
#define PKC_SBA_STRUCT_SIZE 0x1A8
#define PKC_SBA_VM_STACK 0x190          /* calloc(0x190, 4) @ 0x102ac358 */
#define PKC_SBA_L_VAR 133               /* L = vars[133]: the whole body of tag-1 record 156 (extract index 22) */
#define PKC_SBA_L_EXTRACT 22

typedef struct {
    int32_t tag;                        /* +0x0c of the 16-byte record: 0 = scratch, 1 = extracted */
    int32_t nwords;
    uint16_t *words;
} pkc_sba_rec;

typedef struct {
    int nrec;
    pkc_sba_rec *rec;                   /* indexed by the record's own index (record k stores into var k) */
} pkc_sba_prog;

/* Stage 1 + stage 2 of one pcode file (binary, big-endian words on disk; byte-swapped when word 0 != 0x00FB, as the
 * DLL does). params[] receives the stage-1 struct. Kodak's failure code 0x18A8 / -6 -> PK_E_VENDOR_DATA, as does a
 * missing file (PK_E_IO is reserved for read errors on a file that exists). Stage-2 sections other than 0, 7 and the
 * skip sections 0x10..0x12 are not used by any record table we run and are rejected (PK_E_VENDOR_DATA). */
pk_status pkc_sba_pcode_load(const char *path, uint8_t params[PKC_SBA_STRUCT_SIZE], pkc_sba_prog *prog);
void pkc_sba_prog_free(pkc_sba_prog *prog);

/* Run every record in file order over in[0..nin) (fcn.102ac140) and return L = the 23rd tag-1 record's variable.
 * A vendor error exit of the VM (bad opcode, divide by zero, stack under/overflow, label scan off the record) -> PK_E_ARG
 * (Kodak: the caller returns 0x18a9). An in[] index >= nin is a port guard, not a Kodak error: Kodak hands the VM a count of
 * 0x2d0 (0x1028bfa0) yet the records read up to in[732]. The stack is cleared between records (every shipped record halts
 * balanced; the reference keeps one persistent stack). known (nin bytes, or NULL = all slots known): R18 as taint tracking. A value read from a
 * slot with known[i] == 0 (the port never fills it, Kodak's object holds data there) is tainted; taint follows the stack and the
 * variable file (SEL keeps only the chosen branch's taint). PK_E_UNSUPPORTED if L is tainted or a tainted value decides control
 * flow (opcodes 27-30 count, 54/55 condition, a tainted divide by zero). A plain "any executed read" rule was tried and is wrong: real
 * frames execute reads of slot 643 whose value never reaches L (perturbing it leaves L unchanged on every truth scene). vars_out may be NULL, or receive nrec values. */
pk_status pkc_sba_vm_l(const pkc_sba_prog *prog, const int32_t *in, const uint8_t *known, int nin, int32_t *L, int32_t *vars_out);
#endif
