#ifndef PAKON_DEVICE_MODELS_H
#define PAKON_DEVICE_MODELS_H
/* Internal model-table helpers (pkm_ prefix). */
#include "pakon/device.h"

/* The REV the model's unloaded device reports (0xAA07 / 0xAA05 / 0xAA08); 0 if unknown. */
uint16_t pkm_boot_rev(const pk_model *);
/* VID/PID the device enumerates with once the model's firmware runs. PK_E_ARG for a NULL model. */
pk_status pkm_loaded_identity(const pk_model *usb_model, uint16_t *vid, uint16_t *pid);

#endif
