# chromiq-chartread — ChromIQ's chart-reading engine (issue #126).
#
# A fork of ArgyllCMS chartread.c (AGPL-3.0, Graeme W. Gill) linked against
# the vendored standalone instrument library under ../instlib (GPLv2+, the
# file set of Graeme's own instlib.ksh packaging). Library sources are
# compiled byte-identical to upstream except recorded patches: rspl1.c's
# set_rspl grid index (iv[-0-1], not upstream's iv[-1-1]; without it every
# -K/-I chart's .ti3 got an all-nan CAL table), conv.c's #148 beep, and the
# i1Pro 2 indicator lights (i1pro_imp.c/.h, i1pro.c; Preferences > Beta,
# inert unless the helper is started with --i1pro2-lights). All are listed
# in ../instlib/PROVENANCE.md and re-applied by scripts/vendor_instlib.py. Every other ChromIQ change lives in
# chromiq_chartread.c / chromiq_json.c behind CHROMIQ_EXT, so a new Argyll
# release rebases by re-vendoring + re-applying a small diff.
cmake_minimum_required(VERSION 3.15)
project(chromiq_chartread C)

set(CMAKE_C_STANDARD 99)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

set(INSTLIB "${CMAKE_CURRENT_SOURCE_DIR}/../instlib")

# Mirror of spectro/Makefile.SA: OBJS + INSOBJS + SUPOBJS.
set(INSTLIB_UNITS
  conv sa_conv aglob inst numsup rspl1 icoms usbio hidio insttypes
  disptechs rspec xrga pollem xspect xdg_bds ccss ccmx pars cgats
  xcolorants xcal
  dtp20 dtp22 dtp41 dtp51 dtp92 ss ss_imp i1disp i1d3 i1pro i1pro_imp
  i1pro3 i1pro3_imp munki munki_imp hcfr huey colorhug spyd2 spydX
  specbos kleink10 smcube spydX2
  instappsup
)
set(INSTLIB_SOURCES "")
foreach(u ${INSTLIB_UNITS})
  list(APPEND INSTLIB_SOURCES "${INSTLIB}/${u}.c")
endforeach()

# The non-macOS USB/HID backends need icmUTF16 / icmUTF16toUTF8 from Argyll's
# icc library (macOS's IOKit backend doesn't). We supply them ourselves rather
# than vendor 4600 lines of icc_util.c — see chromiq_utf_compat.[ch].
add_library(instlib STATIC ${INSTLIB_SOURCES}
  ${CMAKE_CURRENT_SOURCE_DIR}/chromiq_utf_compat.c)
target_include_directories(instlib PUBLIC ${INSTLIB} ${CMAKE_CURRENT_SOURCE_DIR})
# Makefile.SA CCDEFINES, verbatim.
target_compile_definitions(instlib PUBLIC
  SALONEINSTLIB ALLINSTS ENABLE_SERIAL ENABLE_FAST_SERIAL ENABLE_USB)
if(WIN32)
  # EN_LIBUSB0: select Argyll's libusb0 USB backend (usbio_w0.c) — the driver
  # ChromIQ already installs via core/usb_driver_installer.py, and Argyll's own
  # default (Jamtop USE_LIBUSB0 = true). Without it usbio.c #errors out.
  target_compile_definitions(instlib PUBLIC NT EN_LIBUSB0)
  # Force-include the UTF compat shim so usbio_w0/hidio see icmUTF16.
  # -Wno-implicit-function-declaration: same as the mac/Linux branches —
  # Argyll 3.5.0 SALONEINSTLIB misses a few prototypes (sa_Clamp3); upstream
  # warns, modern clang errors. No source patch for it.
  target_compile_options(instlib PRIVATE
    -Wno-implicit-function-declaration
    -include "${CMAKE_CURRENT_SOURCE_DIR}/chromiq_utf_compat.h")
elseif(APPLE)
  # NOT UNIX_APPLE. That symbol also selects Argyll's macOS HID/USB code paths
  # (hidio.c, icoms_ux.c, usbio.c — 81 uses across 20 files), and this engine
  # talks to instruments perfectly well through the generic UNIX ones. Swapping
  # the whole communication layer to fix a beep would be a very poor trade.
  #
  # CHROMIQ_APPLE_BEEP is scoped to exactly one thing: conv.c's msec_beep. Under
  # plain UNIX that writes a BEL character to stdout — and ChromIQ reads the
  # engine's stdout as its JSON channel, so the "ready to scan" cue after you
  # press the instrument's button went into the pipe and was never heard
  # (#148, Knut: "The sound of the instrument button click … does not play when
  # clicking button during measurement. This worked before through 200 beta
  # releases"). Stock ArgyllCMS is built with UNIX_APPLE and so beeped; this
  # engine never was. AudioToolbox is already linked below.
  target_compile_definitions(instlib PUBLIC UNIX CHROMIQ_APPLE_BEEP)
  # -Wno-implicit-function-declaration: Argyll 3.5.0's SALONEINSTLIB mode
  # misses a few prototypes (e.g. sa_Clamp3); upstream builds treat that as
  # a warning, modern clang as an error. No source patch for it.
  target_compile_options(instlib PRIVATE -fpascal-strings -Wno-sign-compare
    -Wno-implicit-function-declaration)
else()
  target_compile_definitions(instlib PUBLIC UNIX)
  # Linux uses usbio_lx.c — same icmUTF16 need as Windows.
  target_compile_options(instlib PRIVATE -Wno-sign-compare
    -Wno-implicit-function-declaration
    -include "${CMAKE_CURRENT_SOURCE_DIR}/chromiq_utf_compat.h")
endif()

add_executable(chromiq-chartread
  ${CMAKE_CURRENT_SOURCE_DIR}/chromiq_chartread.c
  ${CMAKE_CURRENT_SOURCE_DIR}/chromiq_json.c
  ${CMAKE_CURRENT_SOURCE_DIR}/chromiq_replay.c
  ${CMAKE_CURRENT_SOURCE_DIR}/chromiq_cal.c
  ${CMAKE_CURRENT_SOURCE_DIR}/chromiq_stubs.c
  ${INSTLIB}/alphix.c
)
target_include_directories(chromiq-chartread PRIVATE
  ${INSTLIB} ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(chromiq-chartread PRIVATE instlib)

# The i1Pro 2 lights test (Preferences > Beta, 2026-11-13): the real vendored
# driver on a fake USB layer. Not part of a normal build (EXCLUDE_FROM_ALL);
# tests/test_i1pro2_lights_driver.py builds it with
#   cmake --build <build> --target i1pro2_lights_test
add_executable(i1pro2_lights_test EXCLUDE_FROM_ALL
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/i1pro2_lights_test.c
  ${CMAKE_CURRENT_SOURCE_DIR}/chromiq_stubs.c
  ${INSTLIB}/alphix.c
)
target_include_directories(i1pro2_lights_test PRIVATE
  ${INSTLIB} ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(i1pro2_lights_test PRIVATE instlib)

# ...and the same test against Argyll's own, UNPATCHED i1pro_imp.c, i1pro.c and
# i1pro_imp.h, for the option-off wire trace to be compared byte for byte. The
# test writes those three files (the vendored ones with the recorded patches
# undone, checked against PROVENANCE.md's upstream sha256) into a folder of
# its own and configures with -DCQ_UPSTREAM_I1PRO_DIR=<that folder>.
if(CQ_UPSTREAM_I1PRO_DIR)
  set(_cq_up_sources ${INSTLIB_SOURCES})
  list(REMOVE_ITEM _cq_up_sources "${INSTLIB}/i1pro.c" "${INSTLIB}/i1pro_imp.c")
  add_library(instlib_upstream_i1pro STATIC EXCLUDE_FROM_ALL ${_cq_up_sources}
    "${CQ_UPSTREAM_I1PRO_DIR}/i1pro.c" "${CQ_UPSTREAM_I1PRO_DIR}/i1pro_imp.c"
    ${CMAKE_CURRENT_SOURCE_DIR}/chromiq_utf_compat.c)
  get_target_property(_cq_defs instlib COMPILE_DEFINITIONS)
  get_target_property(_cq_idefs instlib INTERFACE_COMPILE_DEFINITIONS)
  get_target_property(_cq_opts instlib COMPILE_OPTIONS)
  target_compile_definitions(instlib_upstream_i1pro PUBLIC ${_cq_defs} ${_cq_idefs})
  if(_cq_opts)
    target_compile_options(instlib_upstream_i1pro PRIVATE ${_cq_opts})
  endif()
  target_include_directories(instlib_upstream_i1pro BEFORE PUBLIC
    "${CQ_UPSTREAM_I1PRO_DIR}")
  target_include_directories(instlib_upstream_i1pro PUBLIC
    ${INSTLIB} ${CMAKE_CURRENT_SOURCE_DIR})
  add_executable(i1pro2_lights_test_upstream EXCLUDE_FROM_ALL
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/i1pro2_lights_test.c
    ${CMAKE_CURRENT_SOURCE_DIR}/chromiq_stubs.c
    ${INSTLIB}/alphix.c
  )
  target_compile_definitions(i1pro2_lights_test_upstream PRIVATE CQ_UPSTREAM)
  target_link_libraries(i1pro2_lights_test_upstream PRIVATE instlib_upstream_i1pro)
endif()

# Windows: a VERSIONINFO like ChromIQ.exe's (native/win_version.cmake).
include(${CMAKE_CURRENT_SOURCE_DIR}/../win_version.cmake)
chromiq_add_win_version(chromiq-chartread
  "ChromIQ chart-reading engine (ArgyllCMS chartread)"
  "Copyright (c) Graeme W. Gill (ArgyllCMS) and Sebastian Reiprich, AGPL-3.0")

set(_cq_link_targets chromiq-chartread i1pro2_lights_test)
if(CQ_UPSTREAM_I1PRO_DIR)
  list(APPEND _cq_link_targets i1pro2_lights_test_upstream)
endif()
foreach(_tgt ${_cq_link_targets})
if(APPLE)
  # Makefile.OSX LINKFLAGSDEF, verbatim.
  target_link_libraries(${_tgt} PRIVATE
    "-framework Carbon" "-framework Cocoa" "-framework IOKit"
    "-framework CoreFoundation" "-framework AudioToolbox" "-framework AppKit"
    m)
elseif(WIN32)
  target_link_libraries(${_tgt} PRIVATE
    winmm setupapi ws2_32 gdi32 user32 advapi32 shell32 ole32)
else()
  find_package(Threads REQUIRED)
  target_link_libraries(${_tgt} PRIVATE Threads::Threads m rt)
endif()
endforeach()
