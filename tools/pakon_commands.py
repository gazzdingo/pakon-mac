"""Pakon F-135 Plus command-packet constants and builders.

PURE DATA MODULE. No USB, no I/O, no side effects. Every function returns
``bytes`` ready to be written to EP 0x01 OUT.

Everything here was derived statically from TLB.dll; see
``docs/12-command-protocol.md`` for the evidence behind each constant and for
confidence tags. Constants whose *meaning* is inferred rather than proven are
marked with an ``# INFERRED`` comment.

Wire format
-----------
::

    [0] Type   [1] PktLen   [2] Address   [3] Count   [4] Reg/Cmd   [5..] payload

    wire size = PktLen + 2

    Type 1  READ     01 03 AA NN RR                 -> 01 (NN+2) AA SS <NN bytes>
    Type 2  WRITE    02 (NN+3) AA NN RR <NN bytes>  -> 07 02 AA SS
    Type 3  POLL     03 01 AA                       -> 03 04 AA SS <2 bytes>
    Type 4  COMMAND  04 03 AA 00 CC                 -> 07 02 AA SS

The host computes no checksum.

SAFETY: only Types 1, 2, 3 and 4 are valid. Sending any other Type wedges the
scanner firmware until a physical power cycle. ``_check_type`` enforces this.
"""

from __future__ import annotations

import math

__all__ = [
    # packet types
    "TYPE_READ", "TYPE_WRITE", "TYPE_POLL", "TYPE_COMMAND", "TYPE_RESPONSE_ACK",
    "VALID_TYPES",
    # addresses
    "AD_HOST", "AD_PICL", "AD_PICM", "AD_PICF", "AD_LIGHT", "AD_MOTOR",
    # status
    "STATUS_ERROR_MASK", "STATUS_BUSY", "STATUS_READY",
    "ack_status_name", "is_error_status", "parse_response",
    # generic builders
    "read_register", "write_register", "poll_status", "command",
    "write_register_u8", "write_register_u16", "write_register_u24",
    "write_ccd_register",
    # light board
    "REG_LIGHT_LAMP_ENABLE", "REG_LIGHT_LED_LEVELS", "REG_LIGHT_LED_DUTY",
    "REG_LIGHT_STATUS", "REG_LIGHT_TEMPERATURE", "REG_LIGHT_DX_START",
    "LAMP_OFF", "LAMP_VISIBLE", "LAMP_IR", "LAMP_VISIBLE_AND_IR",
    "lamp_on", "lamp_off", "lamp_set_mask",
    "read_lamp_status", "read_lamp_temperature",
    "read_led_levels", "read_led_duty_cycles",
    # lamp drive (docs/15-calibration-read.md)
    "LED_SLOT_ORDER", "LED_LEVEL_MAX", "EXPOSURE_MAX", "LAMP_PWM_CLOCK_HZ",
    "BASE_EXPOSURE", "LAMP_DENSITY_EXPONENTS",
    "led_level_max", "led_levels", "lamp_pwm_period", "lamp_on_count",
    "led_pwm", "lamp_duty_from_current", "lamp_duty_bases",
    "lamp_bring_up_sequence",
    # lamp temperature (NOT on the lamp-on path -- see docs 15 section 7.0)
    "LAMP_TEMP_UNITS_PER_C", "LAMP_TEMP_WORKING_MIN", "LAMP_TEMP_WORKING_MAX",
    "LAMP_TEMP_BAND_MIN", "LAMP_TEMP_BAND_MAX",
    "lamp_temp_c", "lamp_temp_warning_band", "lamp_temp_fault_band",
    "mainboard_temp_warning_band", "mainboard_temp_fault_band",
    "lamp_temp_working", "lamp_temp_latch",
    "CMD_LIGHT_FIFO_RESET", "CMD_LIGHT_DX_STOP",
    "dx_stop",
    # DX board (docs/53-edge-data.md)
    "REG_LIGHT_INTERRUPT_STATUS", "REG_LIGHT_DX_CODE", "DX_RESPONSE_LEN",
    "DX_GATE_DX", "DX_GATE_LAMP", "DX_FORMAT_DEFAULT",
    "read_interrupt_status", "read_dx_code", "dx_start",
    # motor board
    "REG_MOTOR_SPEED", "CMD_MOTOR_FORWARD", "CMD_MOTOR_REVERSE", "CMD_MOTOR_STOP",
    "MOTOR_SPEED_MIN_PLUS", "MOTOR_SPEED_MAX_PLUS",
    "MOTOR_SPEED_MIN_LEGACY", "MOTOR_SPEED_MAX_LEGACY",
    "set_motor_speed", "motor_forward", "motor_reverse", "motor_stop",
    "advance_film",
    # CCD / FPGA
    "REG_CCD_FPGA", "REG_CCD_ADC",
    "FPGA_IDX_CONTROL", "FPGA_IDX_PIXEL_OFFSET", "FPGA_IDX_PIXEL_END",
    "FPGA_IDX_INTEGRATION_TIME", "FPGA_IDX_STATUS_LEDS", "FPGA_IDX_0A",
    "FPGA_CTRL_ACQUIRE", "FPGA_CTRL_BIT1", "FPGA_CTRL_MASK_60",
    "FPGA_CTRL_IR_MODE", "FPGA_CTRL_WIDTH_MASK",
    "ADC_IDX_GAIN_R", "ADC_IDX_GAIN_G", "ADC_IDX_GAIN_B",
    "ADC_IDX_EXPOSURE_R", "ADC_IDX_EXPOSURE_G", "ADC_IDX_EXPOSURE_B",
    "ADC_GAIN_MAX",
    "fpga_write", "adc_write", "fpga_set_control", "ccd_acquire_start",
    "set_status_leds",
    # host
    "REG_HOST_STATUS", "REG_HOST_FIFO_RESET", "REG_HOST_8F",
    "CMD_HOST_CLEAR", "HOST_FIFO_RESET_VALUE",
    "reset_fifos", "read_host_status", "host_clear", "poll_host",
    # identity
    "REG_DEVINFO_SELECT", "REG_DEVINFO_DATA", "REG_INFO_STRING",
    "DEVINFO_LENGTH", "DEVINFO_VERSION_MAJOR_INDEX", "DEVINFO_VERSION_MINOR_INDEX",
    "devinfo_select", "devinfo_read", "devinfo_sequence", "read_info_string",
    # curated list
    "SAFE_FIRST_PACKETS",
]

# --------------------------------------------------------------------------
# Packet types
# --------------------------------------------------------------------------

TYPE_READ = 0x01        # read N bytes of a register
TYPE_WRITE = 0x02       # write N bytes to a register
TYPE_POLL = 0x03        # poll device-ready / status
TYPE_COMMAND = 0x04     # execute a command, no payload

TYPE_RESPONSE_ACK = 0x07  # response type for TYPE_WRITE and TYPE_COMMAND

#: The only packet types the firmware accepts. Anything else permanently wedges
#: the scanner until a physical power cycle.
VALID_TYPES = frozenset((TYPE_READ, TYPE_WRITE, TYPE_POLL, TYPE_COMMAND))

# --------------------------------------------------------------------------
# Board addresses
# --------------------------------------------------------------------------

AD_HOST = 0x10     # FX2 itself; handled locally, never relayed
AD_PICL = 0x20     # legacy light board (no-acks on a Plus unit)
AD_PICM = 0x24     # legacy motor board (no-acks on a Plus unit)
AD_PICF = 0x28     # focus / lens steppers
AD_LIGHT = 0x40    # PICL_PLUS: lamps, LEDs, DX
AD_MOTOR = 0x44    # PICM_PLUS: film drive *and* CCD/FPGA registers

# --------------------------------------------------------------------------
# Response status decoding
# --------------------------------------------------------------------------

#: Bits the driver treats as errors on TYPE_READ / TYPE_POLL responses.
#: A status of 0x88 or 0x08 is clean because ``status & STATUS_ERROR_MASK == 0``.
STATUS_ERROR_MASK = 0x36
STATUS_BUSY = 0x01     # caller should retry
STATUS_READY = 0x08    # ready / OK

_ACK_STATUS_NAMES = {
    0: "success",
    1: "no-ack (board absent)",
    2: "invalid packet",
    3: "bad checksum",
    4: "error 4",
    6: "bus error 6",
    8: "success",
    9: "bus error 9",
}


def ack_status_name(status: int) -> str:
    """Human name for the status byte of a TYPE_RESPONSE_ACK (Type 7) reply."""
    return _ACK_STATUS_NAMES.get(status, f"unknown status 0x{status:02X}")


def is_error_status(status: int, response_type: int) -> bool:
    """True if ``status`` indicates an error, given the response's type byte."""
    if response_type == TYPE_RESPONSE_ACK:
        return status not in (0, 8)
    return bool(status & STATUS_ERROR_MASK)


def parse_response(data: bytes) -> dict:
    """Split a raw 64-byte EP 0x81 read into its fields.

    Returns a dict with ``type``, ``pktlen``, ``address``, ``status``,
    ``payload`` and ``error``. Pure function; does no I/O.
    """
    if len(data) < 4:
        raise ValueError(f"response too short: {len(data)} bytes")
    rtype, pktlen, address, status = data[0], data[1], data[2], data[3]
    wire = pktlen + 2
    payload = bytes(data[4:wire]) if wire > 4 else b""
    return {
        "type": rtype,
        "pktlen": pktlen,
        "address": address,
        "status": status,
        "payload": payload,
        "error": is_error_status(status, rtype),
    }


# --------------------------------------------------------------------------
# Generic builders
# --------------------------------------------------------------------------


def _check_type(packet_type: int) -> None:
    if packet_type not in VALID_TYPES:
        raise ValueError(
            f"packet type 0x{packet_type:02X} is not one of "
            f"{sorted(VALID_TYPES)}; sending it would wedge the firmware "
            "until a physical power cycle"
        )


def _check_u8(name: str, value: int) -> int:
    if not 0 <= value <= 0xFF:
        raise ValueError(f"{name} must fit in a byte, got {value}")
    return value


def read_register(address: int, register: int, count: int) -> bytes:
    """Type 1: read ``count`` bytes of ``register`` from ``address``.

    ``01 03 AA NN RR``. Reply is ``01 (NN+2) AA SS <NN bytes>``.
    Reads never change device state.
    """
    _check_u8("address", address)
    _check_u8("register", register)
    _check_u8("count", count)
    return bytes((TYPE_READ, 3, address, count, register))


def write_register(address: int, register: int, payload: bytes) -> bytes:
    """Type 2: write ``payload`` to ``register`` on ``address``.

    ``02 (N+3) AA N RR <payload>``. Reply is ``07 02 AA SS``.
    """
    _check_u8("address", address)
    _check_u8("register", register)
    payload = bytes(payload)
    n = len(payload)
    if n > 0xFF:
        raise ValueError(f"payload too long: {n} bytes")
    return bytes((TYPE_WRITE, n + 3, address, n, register)) + payload


def poll_status(address: int = AD_HOST) -> bytes:
    """Type 3: poll device-ready / status.

    ``03 01 AA``. Reply is ``03 04 AA SS <2 bytes>``.
    The Windows driver retries up to 44 times while ``status & 0x01``.
    """
    _check_u8("address", address)
    return bytes((TYPE_POLL, 1, address))


def command(address: int, cmd: int) -> bytes:
    """Type 4: execute ``cmd`` on ``address`` with no payload.

    ``04 03 AA 00 CC``. Reply is ``07 02 AA SS``.
    """
    _check_u8("address", address)
    _check_u8("command", cmd)
    return bytes((TYPE_COMMAND, 3, address, 0, cmd))


def ping(address: int) -> bytes:
    """Command 0x00 -- the board-presence probe used by FindPicController."""
    return command(address, 0x00)


def write_register_u8(address: int, register: int, value: int) -> bytes:
    """Type 2 with a single byte of payload."""
    return write_register(address, register, bytes((_check_u8("value", value),)))


def write_register_u16(address: int, register: int, value: int) -> bytes:
    """Type 2 with a 16-bit little-endian payload."""
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"value must fit in 16 bits, got {value}")
    return write_register(address, register, value.to_bytes(2, "little"))


def write_register_u24(address: int, register: int, value: int) -> bytes:
    """Type 2 with a 24-bit little-endian payload (the block-read pointer form)."""
    if not 0 <= value <= 0xFFFFFF:
        raise ValueError(f"value must fit in 24 bits, got {value}")
    return write_register(address, register, value.to_bytes(3, "little"))


def write_ccd_register(register: int, index: int, value: int,
                       address: int = AD_MOTOR) -> bytes:
    """The 3-byte indexed form used for the CCD register files.

    ``02 06 AA 03 RR II <lo> <hi>``. ``register`` must be
    :data:`REG_CCD_FPGA` or :data:`REG_CCD_ADC` -- the Windows driver
    validates exactly those two.
    """
    if register not in (REG_CCD_FPGA, REG_CCD_ADC):
        raise ValueError(
            f"CCD register must be 0x{REG_CCD_FPGA:02X} or 0x{REG_CCD_ADC:02X}, "
            f"got 0x{register:02X}"
        )
    _check_u8("index", index)
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"value must fit in 16 bits, got {value}")
    return write_register(
        address, register, bytes((index,)) + value.to_bytes(2, "little")
    )


# ==========================================================================
# Light board (0x40)
# ==========================================================================

REG_LIGHT_ADDRESS_PTR = 0x01    # 3 B, 24-bit block-read pointer
REG_LIGHT_INTERRUPT_STATUS = 0x02  # 1 B, read-only "what needs servicing" byte
REG_LIGHT_LAMP_ENABLE = 0x80    # 1 B, lamp on/off bitmask   <-- THE LAMP
REG_LIGHT_LED_LEVELS = 0x81     # 5 B, LED level / current array
REG_LIGHT_LED_DUTY = 0x82       # 12 B, LED duty cycles
REG_LIGHT_STATUS = 0x83         # 1 B, read-only hardware status
REG_LIGHT_TEMPERATURE = 0x84    # 2 B, read-only lamp temperature
REG_LIGHT_TEMP_SET_8B = 0x8B    # 4 B  temperature setpoints
REG_LIGHT_TEMP_SET_8C = 0x8C    # 4 B
REG_LIGHT_TEMP_SET_8D = 0x8D    # 4 B
REG_LIGHT_TEMP_SET_8F = 0x8F    # 4 B
REG_LIGHT_DX_CODE = 0x90        # 30 B, read-only DX event stream
REG_LIGHT_DX_START = 0x91       # 3 B, DX start
REG_LIGHT_FW_GATE = 0x97        # 1 B, firmware-update gate -- do not poke
REG_LIGHT_TEMP_D0 = 0xD0        # 1 B, := 0 at temperature init
REG_LIGHT_TEMP_D1 = 0xD1        # 1 B, := 1 at temperature init

CMD_LIGHT_PING = 0x00
CMD_LIGHT_FIFO_RESET = 0x8A     # second half of bDrvResetFifos
CMD_LIGHT_DX_STOP = 0x92        # bDrvDxStop

#: Values for :data:`REG_LIGHT_LAMP_ENABLE`. Bit 0 drives the visible lamps,
#: bit 1 the IR lamp (bDrvLampOn builds the mask from two boolean arguments).
LAMP_OFF = 0x00
LAMP_VISIBLE = 0x01
LAMP_IR = 0x02
LAMP_VISIBLE_AND_IR = 0x03


def lamp_set_mask(mask: int, address: int = AD_LIGHT) -> bytes:
    """Write the lamp enable bitmask. ``02 04 40 01 80 <mask>``."""
    if not 0 <= mask <= 0xFF:
        raise ValueError(f"lamp mask must fit in a byte, got {mask}")
    return write_register_u8(address, REG_LIGHT_LAMP_ENABLE, mask)


def lamp_on(visible: bool = True, ir: bool = False,
            address: int = AD_LIGHT) -> bytes:
    """LAMP ON. Default (visible only) is ``02 04 40 01 80 01``.

    This is an *enable*, not a brightness. The LED levels
    (:data:`REG_LIGHT_LED_LEVELS`) and duty cycles
    (:data:`REG_LIGHT_LED_DUTY`) are separate registers -- read them back
    before assuming the lamp will actually emit light.
    """
    mask = (LAMP_VISIBLE if visible else 0) | (LAMP_IR if ir else 0)
    return lamp_set_mask(mask, address)


def lamp_off(address: int = AD_LIGHT) -> bytes:
    """LAMP OFF. ``02 04 40 01 80 00``."""
    return lamp_set_mask(LAMP_OFF, address)


def read_lamp_status(address: int = AD_LIGHT) -> bytes:
    """Read the 1-byte lamp hardware status. ``01 03 40 01 83``. Safe."""
    return read_register(address, REG_LIGHT_STATUS, 1)


def read_lamp_temperature(address: int = AD_LIGHT) -> bytes:
    """Read the 16-bit lamp temperature. ``01 03 40 02 84``. Safe."""
    return read_register(address, REG_LIGHT_TEMPERATURE, 2)


def read_led_levels(address: int = AD_LIGHT) -> bytes:
    """Read back the 5-byte LED level array. ``01 03 40 05 81``. Safe."""
    return read_register(address, REG_LIGHT_LED_LEVELS, 5)


def read_led_duty_cycles(address: int = AD_LIGHT) -> bytes:
    """Read back the 12-byte LED duty-cycle array. ``01 03 40 0C 82``. Safe."""
    return read_register(address, REG_LIGHT_LED_DUTY, 12)


def set_led_levels(levels: bytes, address: int = AD_LIGHT) -> bytes:
    """Write the raw 5-byte LED level array.

    Slot order is ``[B, Ir, R, 0x00, G]`` -- see :func:`led_levels` for a
    named-argument builder that also enforces the hardware maxima. Prefer that.
    """
    levels = bytes(levels)
    if len(levels) != 5:
        raise ValueError(f"LED level array must be 5 bytes, got {len(levels)}")
    return write_register(address, REG_LIGHT_LED_LEVELS, levels)


# --------------------------------------------------------------------------
# Lamp drive: levels (0x81) and PWM (0x82)
#
# Derived in docs/15-calibration-read.md from TLB.dll fcn.1002c5f0
# (FN_bDrvLampOn), fcn.100203c0 (per-channel maxima) and fcn.1001e020 /
# fcn.10020230 (duty derivation). Everything in this block is
# VERIFIED-FROM-BINARY unless a comment says otherwise.
# --------------------------------------------------------------------------

#: Slot order shared by register 0x81 (bytes) and register 0x82 (u16 pairs).
#: fcn.1002c5f0 @ 0x1002cc04..0x1002cc38 and @ 0x1002cd2f..0x1002ce04.
#: Slot 3 is a hard-coded zero in both registers.
LED_SLOT_ORDER = ("B", "Ir", "R", None, "G")

#: Per-channel level maxima, clamped by fcn.1002c5f0 @ 0x1002c6fb..0x1002c736
#: using the values returned by fcn.100203c0. Keyed by (board_is_0x44, ir_on).
LED_LEVEL_MAX = {
    (True, True):   {"R": 8, "G": 24, "B": 24, "Ir": 8},   # F-135 Plus, IR on
    (True, False):  {"R": 4, "G": 20, "B": 20, "Ir": 0},   # F-135 Plus, IR off
    (False, True):  {"R": 8, "G": 8, "B": 8, "Ir": 8},     # non-0x44 board
    (False, False): {"R": 6, "G": 8, "B": 8, "Ir": 0},
}

#: Maximum accepted by the exposure clamp at fcn.1002c5f0 @ 0x1002c739.
EXPOSURE_MAX = 0xFFD  # 4093

#: Light-board PWM tick clock, .rdata:0x1005db68, used at 0x1002cb83.
LAMP_PWM_CLOCK_HZ = 833333.3

#: Compiled-in base exposures, fcn.10010760 @ 0x10010778..0x100107df.
#: Keyed by the dpiObj[+0x5c] mode selector; value is (non_ir, ir).
BASE_EXPOSURE = {
    0: (2323, 1549),
    1: (3485, 2323),
    None: (4080, 3098),   # the `else` branch
}

#: Per-film-type optical-density exponents from fcn.10020230, keyed by
#: [this+0x374]. base_ch = 10 ** -D_ch. Order is (R, G, B, Ir).
LAMP_DENSITY_EXPONENTS = {
    1: (0.144, 0.4, 0.715, 0.0),
    8: (0.1, 0.25, 0.25, 0.08),
    None: (0.0, 0.03, 0.0, 0.08),   # the `else` branch
}


def led_level_max(ir_on: bool, board_is_main: bool = True) -> dict:
    """Return the per-channel level maxima the firmware will clamp to."""
    return dict(LED_LEVEL_MAX[(bool(board_is_main), bool(ir_on))])


def led_levels(r: int = 0, g: int = 0, b: int = 0, ir: int = 0,
               ir_on: bool | None = None, board_is_main: bool = True,
               address: int = AD_LIGHT) -> bytes:
    """Build the register 0x81 write from named channel levels.

    Payload is ``[B, Ir, R, 0x00, G]``.

    Levels are small integers -- a drive-step index, not a DAC code. They are
    validated against :data:`LED_LEVEL_MAX`; exceeding a maximum raises rather
    than silently clamping, because a caller that overshoots has misunderstood
    the units.

    ``ir_on`` defaults to ``ir > 0``.
    """
    if ir_on is None:
        ir_on = ir > 0
    limits = led_level_max(ir_on, board_is_main)
    for name, value in (("R", r), ("G", g), ("B", b), ("Ir", ir)):
        if not 0 <= value <= limits[name]:
            raise ValueError(
                f"level_{name}={value} outside [0, {limits[name]}] "
                f"(board_is_main={board_is_main}, ir_on={ir_on})")
    return write_register(address, REG_LIGHT_LED_LEVELS,
                          bytes((b, ir, r, 0x00, g)))


def lamp_pwm_period(exposure: int) -> int:
    """PWM period N for register 0x82, from the exposure value.

    ``N = round(exposure * 1e6 / (2 * 833333.3))`` -- i.e. ``exposure * 0.6``.
    fcn.1002c5f0 @ 0x1002cb6d..0x1002cb97.
    """
    if not 0 <= exposure <= EXPOSURE_MAX:
        raise ValueError(
            f"exposure must be in [0, {EXPOSURE_MAX}], got {exposure}")
    return int(exposure * 1_000_000.0 / (2.0 * LAMP_PWM_CLOCK_HZ))


def lamp_on_count(period: int, duty: float) -> int:
    """On-count for one channel: ``floor(N * duty)``, clamped to ``N - 2``.

    The ``N - 2`` ceiling is fcn.1002c5f0 @ 0x1002cd17 (``lea edi,[ebx-2]``);
    it means 100% duty is not representable and the LED always gets at least
    two ticks of off-time. Do not remove it.
    """
    if not 0.0 <= duty <= 1.0:
        raise ValueError(f"duty must be in [0.0, 1.0], got {duty}")
    return max(0, min(int(math.floor(period * duty)), period - 2))


def led_pwm(exposure: int, duty_r: float = 0.0, duty_g: float = 0.0,
            duty_b: float = 0.0, duty_ir: float = 0.0,
            address: int = AD_LIGHT) -> bytes:
    """Build the register 0x82 write (12 B) from an exposure and four duties.

    Layout is six little-endian u16:
    ``[on_B, on_Ir, on_R, 0x0000, on_G, N]``.
    """
    period = lamp_pwm_period(exposure)
    on_b = lamp_on_count(period, duty_b)
    on_ir = lamp_on_count(period, duty_ir)
    on_r = lamp_on_count(period, duty_r)
    on_g = lamp_on_count(period, duty_g)
    payload = b"".join(
        v.to_bytes(2, "little")
        for v in (on_b, on_ir, on_r, 0x0000, on_g, period))
    return write_register(address, REG_LIGHT_LED_DUTY, payload)


def lamp_duty_from_current(current: int, base: float = 1.0) -> float:
    """The fcn.1001e020 duty derivation for one channel.

    ``duty = base * (n-1)/n`` for ``n >= 3``, else ``base * 0.5``.

    ``base`` is *not* 1.0 in the driver -- it is ``10 ** -D`` for the film
    type, see :data:`LAMP_DENSITY_EXPONENTS` and :func:`lamp_duty_bases`.
    Writes ``DutyCycleOpenGate_*`` (CiConfigLight +0x90/98/a0/a8).
    """
    if current < 0:
        raise ValueError(f"current must be >= 0, got {current}")
    return base * ((current - 1) / current) if current >= 3 else base * 0.5


def lamp_duty_bases(film_mode: int | None = None) -> dict:
    """Per-channel ``base`` factors from fcn.10020230: ``10 ** -D``."""
    exps = LAMP_DENSITY_EXPONENTS.get(film_mode, LAMP_DENSITY_EXPONENTS[None])
    names = ("R", "G", "B", "Ir")
    return {n: 10.0 ** -d for n, d in zip(names, exps)}


def lamp_bring_up_sequence(exposure: int, r: int = 0, g: int = 0, b: int = 0,
                           ir: int = 0, duty_r: float = 0.0,
                           duty_g: float = 0.0, duty_b: float = 0.0,
                           duty_ir: float = 0.0,
                           board_is_main: bool = True,
                           address: int = AD_LIGHT) -> list:
    """The safe ordered packet list to bring the lamp up.

    ``lamp off -> PWM (0x82) -> levels (0x81) -> lamp on (0x80)``.

    FN_bDrvLampOn itself writes 0x80 first, but it caches previous state and
    skips unchanged registers, so its levels are already correct when it
    asserts the enable. A host starting from unknown firmware state has no
    such guarantee, so this order programs the drive while the lamp is
    provably dark. Same end state, strictly safer.

    Returns ``[(label, packet), ...]``. Sends nothing.

    NOTE: thermal registers 0x8B/0x8C/0x8D/0x8E/0x8F/0xD0/0xD1 are
    deliberately absent. FN_bDrvLampOn never touches them and
    FN_bDrvInitLampTemperatures is not on the lamp-on path, so the lamp
    lights without them. LampTempWorking is a per-unit registry value that
    is UNKNOWN here, and it drives a TEC.
    """
    ir_on = ir > 0
    return [
        ("lamp off", lamp_set_mask(LAMP_OFF, address)),
        ("PWM 0x82", led_pwm(exposure, duty_r, duty_g, duty_b, duty_ir,
                             address)),
        ("levels 0x81", led_levels(r, g, b, ir, ir_on=ir_on,
                                   board_is_main=board_is_main,
                                   address=address)),
        ("lamp on", lamp_on(visible=True, ir=ir_on, address=address)),
    ]


# --------------------------------------------------------------------------
# Lamp temperature -- setpoint encoders.
#
# NOT part of the lamp-on path. FN_bDrvInitLampTemperatures (fcn.1002d190) is
# called only from fcn.10028d30. Do not send these without a real
# LampTempWorking read from a calibrated install's registry: they command a
# TEC and a wrong value can cook the LED array.
# --------------------------------------------------------------------------

#: Register unit is 1/16 degC (.rdata:0x1005c3b0 = 0.0625, used at 0x10020a31).
LAMP_TEMP_UNITS_PER_C = 16

#: Clamps applied unconditionally after the registry read, fcn.10010cc0
#: @ 0x100110a3..0x10011151. No registry value can escape these.
LAMP_TEMP_WORKING_MIN = 0x250   # 592 = 37.0 degC
LAMP_TEMP_WORKING_MAX = 0x300   # 768 = 48.0 degC
LAMP_TEMP_BAND_MIN = 8          # 0.5 degC
LAMP_TEMP_BAND_MAX = 32         # 2.0 degC


def lamp_temp_c(raw: int) -> float:
    """Convert a raw register-0x84 reading to degrees C."""
    return raw / LAMP_TEMP_UNITS_PER_C


def _temp_pair(low: int, high: int) -> bytes:
    """``[i16 LE(-low), i16 LE(+high)]`` -- the 0x8C / 0x8F payload shape."""
    return ((-low) & 0xFFFF).to_bytes(2, "little") + \
           (high & 0xFFFF).to_bytes(2, "little")


def lamp_temp_warning_band(warning_low: int, warning_high: int,
                           address: int = AD_LIGHT) -> bytes:
    """Register 0x8F: signed warning offsets around the working setpoint.

    Payload ``[i16 -LampTempWarningLow, i16 +LampTempWarningHigh]``.
    Both bounds must be in [8, 32] (0.5 - 2.0 degC).
    """
    for name, v in (("warning_low", warning_low), ("warning_high", warning_high)):
        if not LAMP_TEMP_BAND_MIN <= v <= LAMP_TEMP_BAND_MAX:
            raise ValueError(
                f"{name}={v} outside [{LAMP_TEMP_BAND_MIN}, "
                f"{LAMP_TEMP_BAND_MAX}]")
    return write_register(address, REG_LIGHT_TEMP_SET_8F,
                          _temp_pair(warning_low, warning_high))


def lamp_temp_fault_band(fault_low: int, fault_high: int,
                         warning_low: int, warning_high: int,
                         address: int = AD_LIGHT) -> bytes:
    """Register 0x8C: signed fault offsets around the working setpoint.

    Payload ``[i16 -LampTempFaultLow, i16 +LampTempFaultHigh]``.
    Each fault bound must sit 8..32 units beyond its warning bound.
    """
    if not warning_low + 8 <= fault_low <= warning_low + 32:
        raise ValueError(
            f"fault_low={fault_low} must be in "
            f"[{warning_low + 8}, {warning_low + 32}]")
    if not warning_high + 8 <= fault_high <= warning_high + 32:
        raise ValueError(
            f"fault_high={fault_high} must be in "
            f"[{warning_high + 8}, {warning_high + 32}]")
    return write_register(address, REG_LIGHT_TEMP_SET_8C,
                          _temp_pair(fault_low, fault_high))


def mainboard_temp_warning_band(low: int, high: int,
                                address: int = AD_LIGHT) -> bytes:
    """Register 0x8B: absolute motherboard warning limits, ``[i16 lo, i16 hi]``.

    Unlike 0x8C/0x8F these are NOT negated -- they are absolute readings.
    """
    return write_register(
        address, REG_LIGHT_TEMP_SET_8B,
        (low & 0xFFFF).to_bytes(2, "little") +
        (high & 0xFFFF).to_bytes(2, "little"))


def mainboard_temp_fault_band(low: int, high: int,
                              address: int = AD_LIGHT) -> bytes:
    """Register 0x8D: absolute motherboard fault limits, ``[i16 lo, i16 hi]``."""
    return write_register(
        address, REG_LIGHT_TEMP_SET_8D,
        (low & 0xFFFF).to_bytes(2, "little") +
        (high & 0xFFFF).to_bytes(2, "little"))


def lamp_temp_working(setpoint: int, address: int = AD_LIGHT) -> bytes:
    """Register 0x8E: the absolute working setpoint, u16 LE.

    Only written when UseTemperatureSetpoints != 0. Must be in
    [592, 768] = [37.0, 48.0] degC -- the driver clamps to this range and so
    do we.

    DANGER: the correct per-unit value is UNKNOWN from static analysis. Read
    it from ``HKLM\\Software\\Pakon\\TLB\\Test\\LampTempWorking`` on a
    calibrated install. Do not guess.
    """
    if not LAMP_TEMP_WORKING_MIN <= setpoint <= LAMP_TEMP_WORKING_MAX:
        raise ValueError(
            f"LampTempWorking={setpoint} outside "
            f"[{LAMP_TEMP_WORKING_MIN}, {LAMP_TEMP_WORKING_MAX}] "
            f"({lamp_temp_c(LAMP_TEMP_WORKING_MIN):.1f}-"
            f"{lamp_temp_c(LAMP_TEMP_WORKING_MAX):.1f} degC)")
    return write_register_u16(address, 0x8E, setpoint)


def lamp_temp_latch(address: int = AD_LIGHT) -> list:
    """The 0xD0=0 / 0xD1=1 pair that closes FN_bDrvInitLampTemperatures.

    INFERRED: these latch/enable the setpoints just loaded.
    """
    return [
        ("0xD0 := 0", write_register_u8(address, REG_LIGHT_TEMP_D0, 0)),
        ("0xD1 := 1", write_register_u8(address, REG_LIGHT_TEMP_D1, 1)),
    ]


def dx_stop(address: int = AD_LIGHT) -> bytes:
    """Stop the DX reader. ``04 03 40 00 92``."""
    return command(address, CMD_LIGHT_DX_STOP)


# --- the DX read path -----------------------------------------------------
# The DX board is not a separate packet address: it is the light board, and its
# code words come back from ordinary register reads. Both halves were read out
# of TLB.dll rather than guessed:
#
#   FN_bDrvGetPpbInterruptStatus (fcn.1000bdd0) calls fcn.10009700 at
#   0x1000bed8 with register = 2 and count = 1 (`push 2` at 0x1000bed2), and
#   fcn.10009700 hands that straight to the packet builder fcn.10009410, which
#   lays out `01 03 <addr> <count> <reg>` at 0x10009428-0x1000943a. Then
#   0x1000bf80 `test byte [esp+0x24], 0xa4` gates the DX read and 0x1000bfe6
#   `test byte [esp+0x24], 0x5b` gates the lamp/temperature read -- the same
#   byte, so one register-2 read services both.
#
#   FN_bDrvGetHardwareStatusDx (fcn.10009790) calls the same builder with
#   register 0x90 (`push 0x90` at 0x100097d0) and count 0x1e (`push 0x1e` at
#   0x100097c9), i.e. `01 03 40 1E 90` -> `01 20 40 <status> <30 bytes>`.
#
# The payload decoder for those 30 bytes is tools/dx_decode.py; the poller is
# tools/dx_read.py. docs/53-edge-data.md has the evidence in full.

#: Bytes of DX hardware status returned by :func:`read_dx_code`.
DX_RESPONSE_LEN = 0x1E

#: Bits of :data:`REG_LIGHT_INTERRUPT_STATUS` that mean "DX events waiting".
#: 0x1000bf80. Poll ``0x90`` only when one of these is set.
DX_GATE_DX = 0xA4
#: Bits that mean "lamp status / temperature waiting". 0x1000bfe6.
DX_GATE_LAMP = 0x5B

#: ``format`` byte of :func:`dx_start`. TLB reads it from ``*(byte*)[drv+0x10]``
#: (fcn.1000a7b0 @ 0x1000a7c6); the value 35 mm uses is UNKNOWN from the
#: binary. 0 is what the one recorded live sequence used -- docs/06 line 172,
#: ``02 06 40 03 91 01 00 00``.
DX_FORMAT_DEFAULT = 0


def read_interrupt_status(address: int = AD_LIGHT) -> bytes:
    """Read the 1-byte interrupt-status byte. ``01 03 40 01 02``. Safe.

    Test it against :data:`DX_GATE_DX` before reading :func:`read_dx_code`,
    and against :data:`DX_GATE_LAMP` before reading lamp status.
    """
    return read_register(address, REG_LIGHT_INTERRUPT_STATUS, 1)


def read_dx_code(address: int = AD_LIGHT) -> bytes:
    """Read the 30-byte DX event packet. ``01 03 40 1E 90``. Safe.

    A read, so it changes nothing -- but the DX board's event queue is drained
    by it, and the packet holds at most five events, so poll faster than events
    arrive or code words are lost. See docs/53 s1.1.1.
    """
    return read_register(address, REG_LIGHT_DX_CODE, DX_RESPONSE_LEN)


def dx_start(speed: int, film_format: int = DX_FORMAT_DEFAULT,
             address: int = AD_LIGHT) -> bytes:
    """Start the DX reader. ``02 06 40 03 91 <speed lo> <speed hi> <format>``.

    fcn.1000a7b0: speed is the 16 bits of ``[drv+0x58]`` (0x1000a7b4 /
    0x1000a7d5) and format the byte at ``*[drv+0x10]`` (0x1000a7c6). The same
    three bytes are appended to the CCD-acquire packet by
    FN_bDrvCcdAcquireAndDxStart (fcn.10009bf0, 0x10009c77-0x10009cb8).
    """
    if not 0 <= speed <= 0xFFFF:
        raise ValueError(f"DX speed must fit in 16 bits, got {speed}")
    _check_u8("film_format", film_format)
    return write_register(address, REG_LIGHT_DX_START,
                          int(speed).to_bytes(2, "little")
                          + bytes((film_format,)))


def light_fifo_reset(address: int = AD_LIGHT) -> bytes:
    """Light-board half of bDrvResetFifos. ``04 03 40 00 8A``."""
    return command(address, CMD_LIGHT_FIFO_RESET)


# ==========================================================================
# Motor / main board (0x44)
# ==========================================================================

REG_MOTOR_SPEED = 0xA5          # 2 B, film-drive speed / rate

CMD_MOTOR_FORWARD = 0xA0
CMD_MOTOR_REVERSE = 0xA1
CMD_MOTOR_STOP = 0xA2

#: Clamp applied by bDriveMotorAdvanceFilm when the motor board is 0x44.
MOTOR_SPEED_MIN_PLUS = 0x03E8   # 1000
MOTOR_SPEED_MAX_PLUS = 0x7FFE   # 32766
#: Clamp applied for the legacy (non-Plus) motor board.
MOTOR_SPEED_MIN_LEGACY = 0x0190  # 400
MOTOR_SPEED_MAX_LEGACY = 0x251C  # 9500

# Physical units of REG_MOTOR_SPEED are UNKNOWN. The COM layer speaks in tenths
# of mm/s and divides by 1000 before reaching the driver, so this register is
# NOT tenths of mm/s. Start at MOTOR_SPEED_MIN_PLUS.


def set_motor_speed(speed: int, address: int = AD_MOTOR) -> bytes:
    """Set the film-drive speed register. Does **not** start the motor.

    ``02 05 44 02 A5 <lo> <hi>``.
    """
    lo, hi = ((MOTOR_SPEED_MIN_PLUS, MOTOR_SPEED_MAX_PLUS)
              if address == AD_MOTOR
              else (MOTOR_SPEED_MIN_LEGACY, MOTOR_SPEED_MAX_LEGACY))
    if not lo <= speed <= hi:
        raise ValueError(
            f"speed {speed} outside the driver's clamp [{lo}, {hi}] "
            f"for board 0x{address:02X}"
        )
    return write_register_u16(address, REG_MOTOR_SPEED, speed)


def motor_forward(address: int = AD_MOTOR) -> bytes:
    """Start the film drive forward. ``04 03 44 00 A0``. Film will move."""
    return command(address, CMD_MOTOR_FORWARD)


def motor_reverse(address: int = AD_MOTOR) -> bytes:
    """Start the film drive in reverse. ``04 03 44 00 A1``. Film will move."""
    return command(address, CMD_MOTOR_REVERSE)


def motor_stop(address: int = AD_MOTOR) -> bytes:
    """Stop the film drive. ``04 03 44 00 A2``."""
    return command(address, CMD_MOTOR_STOP)


def advance_film(speed: int, reverse: bool = False,
                 address: int = AD_MOTOR) -> list[bytes]:
    """The two packets bDriveMotorAdvanceFilm sends, in order.

    Returns ``[set_speed, start_command]``. The caller is responsible for the
    dwell and for sending :func:`motor_stop` afterwards -- the driver does the
    same thing from the host side, there is no on-board timer.

    A negative ``speed`` selects reverse, matching the driver's own
    ``jge / neg`` logic.
    """
    if speed < 0:
        speed = -speed
        reverse = True
    start = motor_reverse(address) if reverse else motor_forward(address)
    return [set_motor_speed(speed, address), start]


# ==========================================================================
# CCD / FPGA register files (on the motor board, 0x44)
# ==========================================================================

REG_CCD_FPGA = 0x82     # indexed 16-bit FPGA register file
REG_CCD_ADC = 0x84      # indexed 16-bit A/D register file

FPGA_IDX_CONTROL = 0x00           # 10-bit control register
FPGA_IDX_ZERO_1 = 0x01            # := 0 at InitCcd
FPGA_IDX_ZERO_2 = 0x02
FPGA_IDX_ZERO_3 = 0x03
FPGA_IDX_PIXEL_OFFSET = 0x04      # uiCcdPixelOffset
FPGA_IDX_PIXEL_END = 0x05         # offset + uiCcdPixelHeight  (INFERRED)
FPGA_IDX_INTEGRATION_TIME = 0x06  # uiCcdIntegrationTime
FPGA_IDX_STATUS_LEDS = 0x09       # front-panel status LEDs
FPGA_IDX_0A = 0x0A                # := 0x400 at InitCcd
FPGA_IDX_0B = 0x0B                # := 0 in PutCcdFpgaSettings

FPGA_CTRL_WIDTH_MASK = 0x3FF      # the register is 10 bits wide
FPGA_CTRL_ACQUIRE = 0x001         # CCD acquire enable  <-- start of a scan
FPGA_CTRL_BIT1 = 0x002            # INFERRED: unknown, set by PutCcdFpgaSettings
FPGA_CTRL_MASK_60 = 0x060         # INFERRED: unknown, set by PutCcdFpgaSettings
FPGA_CTRL_IR_MODE = 0x100         # bDrvPutCcdIrMode

ADC_IDX_78 = 0x00                 # := 0x78 at InitCcd
ADC_IDX_80 = 0x01                 # := 0x80 at InitCcd
ADC_IDX_GAIN_R = 0x02             # INFERRED channel order
ADC_IDX_GAIN_G = 0x03
ADC_IDX_GAIN_B = 0x04
ADC_IDX_EXPOSURE_R = 0x05         # INFERRED channel order
ADC_IDX_EXPOSURE_G = 0x06
ADC_IDX_EXPOSURE_B = 0x07

ADC_GAIN_MAX = 0x3F               # driver clamps gains to 63


def fpga_write(index: int, value: int, address: int = AD_MOTOR) -> bytes:
    """Write an FPGA register. ``02 06 44 03 82 <idx> <lo> <hi>``."""
    return write_ccd_register(REG_CCD_FPGA, index, value, address)


def adc_write(index: int, value: int, address: int = AD_MOTOR) -> bytes:
    """Write a CCD A/D register. ``02 06 44 03 84 <idx> <lo> <hi>``."""
    return write_ccd_register(REG_CCD_ADC, index, value, address)


def fpga_set_control(control_word: int, address: int = AD_MOTOR) -> bytes:
    """Write the whole 10-bit FPGA control register.

    The driver keeps a software shadow and always writes the full word -- there
    is no read path for this register anywhere in TLB.dll, so the shadow cannot
    be recovered from the device. Track it host-side.
    """
    if control_word & ~FPGA_CTRL_WIDTH_MASK:
        raise ValueError(
            f"FPGA control register is 10 bits; 0x{control_word:X} overflows"
        )
    return fpga_write(FPGA_IDX_CONTROL, control_word, address)


def ccd_acquire_start(control_shadow: int, address: int = AD_MOTOR) -> bytes:
    """Set the acquire bit in the FPGA control register.

    ``control_shadow`` is your host-side copy of the current 10-bit word.
    Mirrors bDrvCcdAcquireAndDxStart, which computes ``shadow | 1``.
    """
    return fpga_set_control(
        (control_shadow | FPGA_CTRL_ACQUIRE) & FPGA_CTRL_WIDTH_MASK, address
    )


def set_status_leds(value: int, address: int = AD_MOTOR) -> bytes:
    """Front-panel status LEDs, FPGA index 9. Encoding is UNKNOWN."""
    return fpga_write(FPGA_IDX_STATUS_LEDS, value, address)


# ==========================================================================
# Host / FX2 (0x10)
# ==========================================================================

REG_HOST_ADDRESS_PTR = 0x01     # 3 B, 24-bit block-read pointer
REG_HOST_BLOCK_DATA = 0x07      # n B, block-read data window
REG_HOST_STATUS = 0x03          # 2 B, read-only status word
REG_HOST_FIFO_RESET = 0x84      # 1 B
REG_HOST_8F = 0x8F              # 1 B, toggled 0->1->0 during bInit2; meaning UNKNOWN

CMD_HOST_CLEAR = 0x85           # sent when host status bit 5 (0x20) is set

HOST_FIFO_RESET_VALUE = 0x02


def reset_fifos() -> list[bytes]:
    """The two packets of bDrvResetFifos, in order.

    ``[02 04 10 01 84 02, 04 03 40 00 8A]``
    """
    return [
        write_register_u8(AD_HOST, REG_HOST_FIFO_RESET, HOST_FIFO_RESET_VALUE),
        light_fifo_reset(),
    ]


def read_host_status() -> bytes:
    """Read the 16-bit host status word. ``01 03 10 02 03``. Safe.

    If the response status byte has bit 5 (0x20) set, the driver follows up with
    :func:`host_clear` and retries up to 100 times.
    """
    return read_register(AD_HOST, REG_HOST_STATUS, 2)


def host_clear() -> bytes:
    """Host clear / ack. ``04 03 10 00 85``."""
    return command(AD_HOST, CMD_HOST_CLEAR)


def poll_host() -> bytes:
    """Type 3 poll of the FX2. ``03 01 10``. Safe."""
    return poll_status(AD_HOST)


# ==========================================================================
# Identity / firmware versions
# ==========================================================================

REG_DEVINFO_SELECT = 0x03       # write 1 to select the device-info source
REG_DEVINFO_DATA = 0x07         # then read 12 bytes
REG_INFO_STRING = 0x90          # 30-byte info string

DEVINFO_LENGTH = 12
DEVINFO_VERSION_MAJOR_INDEX = 1  # devinfo[1]
DEVINFO_VERSION_MINOR_INDEX = 2  # devinfo[2]

DEVINFO_SELECT_VALUE = 0x01


def devinfo_select(address: int) -> bytes:
    """Step 1 of bDrvGetDevInfo. ``02 04 AA 01 03 01``."""
    return write_register_u8(address, REG_DEVINFO_SELECT, DEVINFO_SELECT_VALUE)


def devinfo_read(address: int) -> bytes:
    """Step 2 of bDrvGetDevInfo. ``01 03 AA 0C 07``. Safe."""
    return read_register(address, REG_DEVINFO_DATA, DEVINFO_LENGTH)


def devinfo_sequence(address: int) -> list[bytes]:
    """Both bDrvGetDevInfo packets, in order."""
    return [devinfo_select(address), devinfo_read(address)]


def devinfo_version(devinfo: bytes) -> tuple[int, int]:
    """Extract the ``(major, minor)`` firmware version from a devinfo payload."""
    devinfo = bytes(devinfo)
    if len(devinfo) < DEVINFO_LENGTH:
        raise ValueError(
            f"devinfo must be {DEVINFO_LENGTH} bytes, got {len(devinfo)}"
        )
    return (devinfo[DEVINFO_VERSION_MAJOR_INDEX],
            devinfo[DEVINFO_VERSION_MINOR_INDEX])


def read_info_string(address: int) -> bytes:
    """Read the 30-byte info string. ``01 03 AA 1E 90``. Safe."""
    return read_register(address, REG_INFO_STRING, 30)


# ==========================================================================
# Curated "safe to send first" list -- see docs/12-command-protocol.md §8
# ==========================================================================

#: ``(label, packet, expected-response description, safe_readonly)``, ordered
#: most-confident first.
SAFE_FIRST_PACKETS = [
    ("read lamp status",
     read_lamp_status(),
     "01 03 40 88 <status>", True),
    ("read lamp temperature",
     read_lamp_temperature(),
     "01 04 40 88 <lo> <hi>", True),
    ("read LED levels",
     read_led_levels(),
     "01 07 40 88 <5 bytes>", True),
    ("read LED duty cycles",
     read_led_duty_cycles(),
     "01 0E 40 88 <12 bytes>", True),
    ("light board devinfo: select",
     devinfo_select(AD_LIGHT),
     "07 02 40 00", False),
    ("light board devinfo: read",
     devinfo_read(AD_LIGHT),
     "01 0E 40 88 <12 bytes>", True),
    ("motor board devinfo: select",
     devinfo_select(AD_MOTOR),
     "07 02 44 00", False),
    ("motor board devinfo: read",
     devinfo_read(AD_MOTOR),
     "01 0E 44 08 <12 bytes>", True),
    ("LAMP ON (visible)",
     lamp_on(),
     "07 02 40 00", False),
    ("LAMP OFF",
     lamp_off(),
     "07 02 40 00", False),
    ("read host status word",
     read_host_status(),
     "01 04 10 08 <lo> <hi>", True),
    ("set motor speed to minimum (does not move film)",
     set_motor_speed(MOTOR_SPEED_MIN_PLUS),
     "07 02 44 00", False),
    ("MOTOR FORWARD -- film will move, have stop ready",
     motor_forward(),
     "07 02 44 00", False),
    ("MOTOR STOP",
     motor_stop(),
     "07 02 44 00", False),
]


if __name__ == "__main__":  # pragma: no cover - convenience dump only
    print("Pakon F-135 Plus -- safe-to-send-first packets\n")
    for label, pkt, expect, readonly in SAFE_FIRST_PACKETS:
        tag = "R " if readonly else "W "
        print(f"{tag}{pkt.hex(' ').upper():<28}  {label}")
        print(f"  {'':<28}  expect: {expect}")
