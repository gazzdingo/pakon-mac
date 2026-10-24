cmake_minimum_required(VERSION 3.16)
project(pakon C)
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
add_compile_options(-std=c99 -O2 -ffp-contract=off -Wall -Wextra -Werror)

enable_testing()

# Digital ICE (C9). src/ice/variants.c is generated from Kodak's DMLDICELib code (lab/ice/gen_c.py) and is not in the public tree.
# PK_WITH_ICE defaults to ON when that file is present (the owner's private build) and OFF when it is not (the public tree);
# OFF builds src/ice/ice_stub.c: pk_ice_available() is 0 and pk_ice_apply() returns PK_E_UNSUPPORTED.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/src/ice/variants.c")
  option(PK_WITH_ICE "build Digital ICE (needs src/ice/variants.c)" ON)
else()
  option(PK_WITH_ICE "build Digital ICE (needs src/ice/variants.c)" OFF)
endif()
if(PK_WITH_ICE)
  if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/src/ice/variants.c")
    message(FATAL_ERROR "PK_WITH_ICE=ON needs core/src/ice/variants.c, which is not in the public tree")
  endif()
  set(PK_ICE_SRC src/ice/ice.c src/ice/tables.c src/ice/variants.c)
else()
  message(STATUS "libpakon: PK_WITH_ICE is OFF, Digital ICE is not built")
  set(PK_ICE_SRC src/ice/ice_stub.c)
endif()
set(PK_COLOUR_SRC ${PK_ICE_SRC} src/colour/data/diag.c src/colour/data/kodak_text.c src/colour/data/kodak_map.c src/colour/front.c
  src/colour/data/kct.c src/colour/icc.c src/colour/nra.c src/colour/falloff.c src/colour/render.c src/colour/adjust.c
  src/colour/analysis/image.c src/colour/analysis/dmin.c
  src/colour/analysis/sba_vm.c src/colour/analysis/sba_measure.c src/colour/analysis/fos.c src/colour/analysis/scplut.c
  src/colour/analysis/sba_pref.c src/colour/analysis/flesh.c src/colour/analysis/fugc.c src/colour/analysis/exposure.c
  src/colour/analysis/roll.c src/colour/export.c src/colour/colour.c)
find_package(Threads REQUIRED)
add_library(pakon_colour STATIC)
target_sources(pakon_colour PRIVATE ${PK_COLOUR_SRC})
target_include_directories(pakon_colour PUBLIC include PRIVATE src/colour src)
target_link_libraries(pakon_colour PUBLIC Threads::Threads m)

# Ruling R4: the same sources as a shared library, for lab scripts that call the port through ctypes
# (lab/oracle/scripts/prep_inputs.py --film-base kodak). Lab only; no test links it.
add_library(pakon_colour_shared SHARED ${PK_COLOUR_SRC})
target_include_directories(pakon_colour_shared PUBLIC include PRIVATE src/colour src)
target_link_libraries(pakon_colour_shared PUBLIC Threads::Threads m)

# Kodak-match tests need Kodak-derived inputs that the public tree does not carry (vectors, the user's own PSI install, vendor/derived).
# pk_need_files scans the test source for the files it opens and defines PK_NEED_FILES; tests/colour/pkv.c then exits 77 (skipped)
# before main() when one is missing, and every test carries SKIP_RETURN_CODE 77.
function(pk_need_files name src vecdir)
  file(READ "${CMAKE_CURRENT_SOURCE_DIR}/${src}" body)
  set(need "")
  string(REGEX MATCHALL "/[A-Za-z0-9_]+\\.pkv\"" pkvs "${body}")
  foreach(p ${pkvs})
    string(REGEX REPLACE "\"$" "" p "${p}")
    list(APPEND need "${vecdir}${p}")
  endforeach()
  if(body MATCHES "VENDOR_ROOT")
    list(APPEND need "${PK_VENDOR_NEED}")
  endif()
  if(body MATCHES "DERIVED_ROOT")
    list(APPEND need "${CMAKE_CURRENT_SOURCE_DIR}/../vendor/derived")
  endif()
  string(REPLACE ";" "|" need "${need}")
  if(need)
    target_compile_definitions(${name} PRIVATE "PK_NEED_FILES=\"${need}\"")
  endif()
  set_tests_properties(${name} PROPERTIES SKIP_RETURN_CODE 77)
endfunction()

function(pk_add_test name src)
  add_executable(${name} ${src} tests/colour/pkv.c ${ARGN})
  target_link_libraries(${name} PRIVATE pakon_colour)
  target_include_directories(${name} PRIVATE tests tests/colour src/colour)
  target_compile_definitions(${name} PRIVATE
    "PKV_DIR=\"${CMAKE_CURRENT_SOURCE_DIR}/tests/colour/vectors\""
    "DERIVED_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/derived\""
    "VENDOR_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/pakon-psi-3.0.4.27/F-X35 COM SERVER\"")
  add_test(NAME ${name} COMMAND ${name})
  set(PK_VENDOR_NEED "${CMAKE_CURRENT_SOURCE_DIR}/../vendor/pakon-psi-3.0.4.27/F-X35 COM SERVER")
  if(NOT name STREQUAL "test_pkv")            # the PKV reader's own test opens only files it writes (and one that must not exist)
    pk_need_files(${name} ${src} "${CMAKE_CURRENT_SOURCE_DIR}/tests/colour/vectors")
  else()
    set_tests_properties(${name} PROPERTIES SKIP_RETURN_CODE 77)
  endif()
endfunction()

pk_add_test(test_pkv tests/colour/test_pkv.c)
pk_add_test(kodak_text tests/colour/test_kodak_text.c)
pk_add_test(front tests/colour/test_front.c)
pk_add_test(icc tests/colour/test_icc.c)
pk_add_test(nra tests/colour/test_nra.c)
pk_add_test(falloff tests/colour/test_falloff.c)
pk_add_test(render tests/colour/test_render.c)
pk_add_test(adjust tests/colour/test_adjust.c)
pk_add_test(analysis_image tests/colour/test_analysis_image.c)
pk_add_test(dmin tests/colour/test_dmin.c)
pk_add_test(sba_measure tests/colour/test_sba_measure.c)
pk_add_test(fos tests/colour/test_fos.c)
pk_add_test(scplut tests/colour/test_scplut.c)
pk_add_test(sba_pref tests/colour/test_sba_pref.c)
pk_add_test(flesh tests/colour/test_flesh.c tests/colour/synframe.c)
pk_add_test(fugc tests/colour/test_fugc.c)
pk_add_test(exposure tests/colour/test_exposure.c)
pk_add_test(roll tests/colour/test_roll.c tests/colour/synframe.c)
pk_add_test(branches tests/colour/test_branches.c tests/colour/synframe.c)
pk_add_test(reentrant tests/colour/test_reentrant.c)
pk_add_test(export tests/colour/test_export.c tests/colour/synframe.c)

# Scanner core (libpakon): util helpers, status/error scaffold; later tasks append sources here.
set(PK_CORE_SRC src/util/error.c src/util/sha256.c src/util/base64.c src/util/jsonl.c src/util/fsutil.c src/util/json.c
  src/stream/ring.c src/stream/stream.c src/stream/sidecar.c
  src/link/guard.c src/link/link.c
  src/transport/trace.c src/transport/record.c src/transport/replay.c src/transport/usb.c src/transport/usb_errmap.c
  src/vendor/vendor.c
  src/boards/ccd_cfg.c src/boards/light.c src/boards/motor.c src/boards/host.c src/boards/dx.c
  src/boards/film.c src/boards/leds.c src/boards/lamp.c src/boards/guides.c
  src/session/session.c src/session/idle.c src/session/events.c src/session/scan.c src/session/config.c src/session/warn.c
  src/device/models.c src/device/discover.c src/device/ihex.c src/device/fwload.c src/device/eeprom_store.c src/calib/eeprom.c
  src/util/zip.c src/calib/record.c src/calib/store.c src/calib/pakoncal.c src/calib/psi_import.c src/calib/derive.c
  src/calib/capture.c src/calib/afe.c src/calib/measure.c src/calib/tests.c src/calib/policy.c src/session/cal.c
  ${PK_ICE_SRC}
  src/decode/sync.c src/decode/kernel.c src/decode/lores.c src/decode/lores_weights.c src/decode/readout.c
  src/framing/frame.c
  src/roll/geometry.c src/roll/roll.c src/roll/colour_input.c)
add_library(pakon_core STATIC ${PK_CORE_SRC})
target_include_directories(pakon_core PUBLIC include PRIVATE src ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(pakon_core PUBLIC Threads::Threads m)

# USB backend: libusb 1.0, linked dynamically (never vendored). -DPK_NO_LIBUSB=ON, or no libusb found, builds the
# stub path (pk_usb_list / pk_usb_open return PK_E_UNSUPPORTED).
option(PK_NO_LIBUSB "build without libusb (USB backend stubbed)" OFF)
if(PK_NO_LIBUSB)
  message(STATUS "libpakon: PK_NO_LIBUSB set, USB backend is a stub")
else()
  find_package(PkgConfig QUIET)
  if(PkgConfig_FOUND)
    pkg_check_modules(LIBUSB QUIET IMPORTED_TARGET libusb-1.0)
  endif()
  if(LIBUSB_FOUND)
    message(STATUS "libpakon: libusb ${LIBUSB_VERSION} found, USB backend enabled")
    target_compile_definitions(pakon_core PRIVATE PK_HAVE_LIBUSB)
    target_link_libraries(pakon_core PUBLIC PkgConfig::LIBUSB)
  else()
    message(WARNING "libpakon: libusb-1.0 not found (brew install libusb pkg-config); USB backend is a stub")
  endif()
endif()

function(pk_add_core_test name src)
  add_executable(core_${name} ${src} tests/colour/pkv.c ${ARGN})
  target_link_libraries(core_${name} PRIVATE pakon_core)
  target_include_directories(core_${name} PRIVATE tests tests/core tests/colour src)
  target_compile_definitions(core_${name} PRIVATE
    "PKV_DIR=\"${CMAKE_CURRENT_SOURCE_DIR}/tests/core/vectors\""
    "VENDOR_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/pakon-psi-3.0.4.27\""
    "DERIVED_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/derived\""
    "CORPUS_DIR=\"${CMAKE_CURRENT_SOURCE_DIR}/../corpus\"")
  add_test(NAME core_${name} COMMAND core_${name})
  set(PK_VENDOR_NEED "${CMAKE_CURRENT_SOURCE_DIR}/../vendor/pakon-psi-3.0.4.27")
  pk_need_files(core_${name} ${src} "${CMAKE_CURRENT_SOURCE_DIR}/tests/core/vectors")
endfunction()

# Task 6: Kodak-match for the calibration-EEPROM copy header (TLB FUN_10016A90 under Unicorn, vectors from
# lab/vectors/gen_eeprom_header.py).
pk_add_core_test(eeprom_header_kodak tests/core/test_eeprom_header_kodak.c)

# Task 8: Kodak-match for the DX parser, votes, frame numbers and strip hand-off (TLB.dll FUN_10009790 and friends under Unicorn,
# vectors from lab/vectors/gen_dx.py).
pk_add_core_test(dx_kodak tests/core/test_dx_kodak.c)

# Task 15: Kodak-match for the calibration tables (TLB FN_bCalibrateFixedPatternDark/Bright under Unicorn, vectors from
# lab/vectors/gen_calib_golden.py; RE 30 sec 13).
pk_add_core_test(calib_tables tests/core/test_calib_tables.c)

# Digital ICE port (RE 44): Kodak-match for DMLDICEProcess against the 42 Wine-oracle vectors (lab/vectors/gen_ice_golden.py). The
# port's bit-exactness rests on -ffp-contract=off (set for the whole project above): no fused multiply-add, every float32 store a
# (float) cast, double arithmetic otherwise.
if(PK_WITH_ICE)          # the test reaches into the ICE tables (src/ice/tables.c), which the PK_WITH_ICE=OFF stub does not have
  pk_add_core_test(ice_kodak tests/core/test_ice_kodak.c)
endif()

# S-R45 d: the Digital ICE save composition against Kodak (DMLDICELib -> TLB LUT + polynomial -> PakonIMAu balance / rotation / adjust, vector from
# lab/vectors/gen_ice_save_golden.py, docs/re/45 sec 4.4) versus the port's pk_roll_input.ice render.
pk_add_core_test(ice_save_kodak tests/core/test_ice_save_kodak.c)
target_link_libraries(core_ice_save_kodak PRIVATE pakon_colour)
target_compile_definitions(core_ice_save_kodak PRIVATE "DERIVED_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/derived\"")
set_tests_properties(core_ice_save_kodak PROPERTIES TIMEOUT 600)

# Task 16: Kodak-match for the scan-line kernel (TLB FUN_100246d0 under Unicorn, vectors from lab/vectors/gen_kernel.py; RE 30). Task 17 adds cases.
pk_add_core_test(decode_kodak tests/core/test_decode_kodak.c)

# Task 10: the minimal `pakon` command line (ruling C18; Task 22 extends it). cli/fake.c compiles to nothing under NDEBUG: the
# --fake developer flag exists in debug builds only.
add_executable(pakon cli/pakon.c cli/args.c cli/hw1.c cli/hw2e.c cli/cmd_decode.c cli/fake.c)
target_include_directories(pakon PRIVATE cli src)
target_link_libraries(pakon PRIVATE pakon_core pakon_colour)
target_compile_definitions(pakon PRIVATE
  "DERIVED_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/derived\""
  "VENDOR_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/pakon-psi-3.0.4.27/F-X35 COM SERVER\"")

# Task 21: the roll-directory CLI (tools/pakon_render.c) used by the end-to-end corpus check (core/tests/colour/e2e.py).
add_executable(pakon_render ../tools/pakon_render.c)
target_link_libraries(pakon_render PRIVATE pakon_colour)
target_compile_definitions(pakon_render PRIVATE
  "DERIVED_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/derived\""
  "VENDOR_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/pakon-psi-3.0.4.27/F-X35 COM SERVER\"")

# Task 23: performance bench, run by hand (build/colour_bench <roll_dir> [n_frames]); not registered with ctest.
add_executable(colour_bench tests/colour/bench.c)
target_link_libraries(colour_bench PRIVATE pakon_colour)
target_compile_definitions(colour_bench PRIVATE
  "DERIVED_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/derived\""
  "VENDOR_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/pakon-psi-3.0.4.27/F-X35 COM SERVER\"")

# Task 21: the end-to-end corpus check (core/tests/colour/e2e.py) needs the corpus roll directories (or the owner's
# captures and the scratch tree's v1 copy to rebuild them) and takes minutes, so it is registered only on request:
# cmake -DPK_E2E=ON. It exits 77 (skipped) when a roll directory can be neither found nor rebuilt.
option(PK_E2E "register the end-to-end corpus check against Kodak's recorded hashes" OFF)
if(PK_E2E)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME e2e COMMAND Python3::Interpreter -I ${CMAKE_CURRENT_SOURCE_DIR}/tests/colour/e2e.py --build ${CMAKE_BINARY_DIR})
  set_tests_properties(e2e PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 7200 LABELS e2e)
endif()

# Task 18: Kodak-match for the frame detection pass (TLB FUN_100079c0 / FUN_100072c0 under Unicorn, vectors from lab/vectors/gen_frame.py; RE 31).
pk_add_core_test(frame_kodak tests/core/test_frame_kodak.c)

# Task 20: the roll hand-off exporter (a libpakon roll to the roll directory pakon_render reads; public headers pakon/roll.h and pakon/colour.h only) and the
# Kodak-match check of the hand-off. The check needs the imported roll fixture (tools/v1_import_roll.py -> ${ROLLS_DIR}/r4) and exits 77 (skipped) without it.
set(ROLLS_DIR "${CMAKE_BINARY_DIR}/rolls")
add_executable(pakon_roll_export ../tools/pakon_roll_export.c)
target_link_libraries(pakon_roll_export PRIVATE pakon_core pakon_colour)
target_compile_definitions(pakon_roll_export PRIVATE "DERIVED_ROOT=\"${CMAKE_CURRENT_SOURCE_DIR}/../vendor/derived\"")
pk_add_core_test(roll_kodak tests/core/test_roll_kodak.c)
target_compile_definitions(core_roll_kodak PRIVATE "ROLLS_DIR=\"${ROLLS_DIR}\"")
set_tests_properties(core_roll_kodak PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 600)
