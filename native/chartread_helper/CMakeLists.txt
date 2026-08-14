# chromiq-chartread — ChromIQ's chart-reading engine (issue #126).
#
# A fork of ArgyllCMS chartread.c (AGPL-3.0, Graeme W. Gill) linked against
# the vendored standalone instrument library under ../instlib (GPLv2+, the
# file set of Graeme's own instlib.ksh packaging). Library sources are
# compiled byte-identical to upstream — every ChromIQ change lives in
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
  # warns, modern clang errors. Sources stay byte-identical.
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
  # a warning, modern clang as an error. Sources stay byte-identical.
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

if(APPLE)
  # Makefile.OSX LINKFLAGSDEF, verbatim.
  target_link_libraries(chromiq-chartread PRIVATE
    "-framework Carbon" "-framework Cocoa" "-framework IOKit"
    "-framework CoreFoundation" "-framework AudioToolbox" "-framework AppKit"
    m)
elseif(WIN32)
  target_link_libraries(chromiq-chartread PRIVATE
    winmm setupapi ws2_32 gdi32 user32 advapi32 shell32 ole32)
else()
  find_package(Threads REQUIRED)
  target_link_libraries(chromiq-chartread PRIVATE Threads::Threads m rt)
endif()
