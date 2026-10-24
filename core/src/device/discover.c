/* Device discovery: lists and classifies; opens nothing (pk_usb_list reads cached descriptors only). */
#include "pakon/device.h"

pk_status pk_device_discover(pk_dev_entry *out, size_t cap, size_t *n) {
    if (n) *n = 0;
    if (!n || (cap && !out)) return PK_E_ARG;
    pk_usb_info info[64];
    size_t got = 0;
    pk_status s = pk_usb_list(info, cap < 64 ? cap : 64, &got);
    if (s != PK_OK) return s;
    for (size_t i = 0; i < got; i++) {
        out[i].info = info[i];
        out[i].cls = pk_device_classify(info[i].vid, info[i].pid, info[i].rev);
    }
    *n = got;
    return PK_OK;
}
