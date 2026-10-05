# chromiq-gammap — bit-exact gamut-mapping helper (ArgyllCMS 3.5.0, AGPL-3.0).
#
# Self-contained build of a minimal ArgyllCMS subset (vendored under
# ../argyll) + the helper. No Jam / no Argyll build tree required. The unit
# list mirrors the upstream Jamfile libraries EXACTLY; six #include-only .c
# fragments (icc_pe/icc_util/icc_xf, xlut/xmatrix/xmono) are deliberately not
# compiled as translation units. See ../argyll/PROVENANCE.md and
# workflow/profile_engine/gammap_port/portmap.md for how the recipe was
# recovered and verified byte-identical to Argyll's own gmcloud proof.
cmake_minimum_required(VERSION 3.15)
project(chromiq_gammap C)

set(CMAKE_C_STANDARD 99)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

set(ARGYLL "${CMAKE_CURRENT_SOURCE_DIR}/../argyll")

# --- Vendored Argyll translation units (upstream Jamfile library lists) ------
set(ARGYLL_UNITS
  numlib/numsup numlib/dnsq numlib/powell numlib/dhsx numlib/varmet
  numlib/ludecomp numlib/svd numlib/zbrent numlib/rand numlib/sobol
  numlib/aatree numlib/quadprog numlib/gnewt numlib/roots
  icc/icc icc/iccstd
  cgats/pars cgats/cgats cgats/parsstd cgats/cgatsstd
  rspl/rspl rspl/scat rspl/rev rspl/gam rspl/spline rspl/opt
  gamut/gamut gamut/gammap gamut/nearsmth
  xicc/xicc xicc/xspect xicc/xcolorants xicc/xcam xicc/cam97s3 xicc/cam02
  xicc/xfit xicc/moncurve xicc/xcal
  xicc/bt1886 xicc/tm3015
  plot/vrml
)
# NOT compiled: spectro/conv, xicc/mpp, xicc/ccmx, xicc/ccss. They are members
# of the upstream Jamfile libraries but are *unreferenced* by the gamut-mapping
# path — the static-lib link never pulls them (proven: dropping them yields a
# byte-identical binary). conv.c in particular is the one platform-fragile unit
# (Win32 conio/tlhelp32/process vs POSIX termios/pwd), so excluding it from the
# compile is what makes the Windows/Linux cross-builds portable. The four .c
# files stay vendored under ../argyll for provenance; they are simply not built.
set(ARGYLL_SOURCES "")
foreach(u ${ARGYLL_UNITS})
  list(APPEND ARGYLL_SOURCES "${ARGYLL}/${u}.c")
endforeach()

set(ARGYLL_INCLUDES
  ${ARGYLL}/h ${ARGYLL}/numlib ${ARGYLL}/icc ${ARGYLL}/cgats
  ${ARGYLL}/rspl ${ARGYLL}/gamut ${ARGYLL}/xicc ${ARGYLL}/spectro
  ${ARGYLL}/plot
)

# Build the Argyll subset as a STATIC library so the final link pulls only the
# objects the helper actually references — matching the archive-based recipe
# that was verified byte-identical to Argyll's own gmcloud proof.
add_library(argyllgm STATIC ${ARGYLL_SOURCES})
target_include_directories(argyllgm PRIVATE ${ARGYLL_INCLUDES})
target_compile_definitions(argyllgm PRIVATE ARGYLLCMS ALLINSTS)

add_executable(chromiq-gammap ${CMAKE_CURRENT_SOURCE_DIR}/gammap_helper.c)
target_include_directories(chromiq-gammap PRIVATE ${ARGYLL_INCLUDES})
target_compile_definitions(chromiq-gammap PRIVATE ARGYLLCMS ALLINSTS)
target_link_libraries(chromiq-gammap argyllgm)

# --- Per-platform defines, warnings and link libraries -----------------------
# Platform macros must reach the Argyll units (argyllgm) as well as the helper.
if(APPLE)
  set(PLATFORM_DEFS UNIX UNIX_APPLE)
elseif(UNIX)
  set(PLATFORM_DEFS UNIX)
elseif(WIN32)
  set(PLATFORM_DEFS NT _CRT_SECURE_NO_WARNINGS)
endif()
target_compile_definitions(argyllgm PRIVATE ${PLATFORM_DEFS})
target_compile_definitions(chromiq-gammap PRIVATE ${PLATFORM_DEFS})

# Argyll's sources rely on pre-C99 implicit declarations and lax int/pointer
# conversions; silence them rather than patch vendored code.
if(MSVC)
  set(RELAX_FLAGS /w)
else()
  # -fno-strict-aliasing (F-08): gamut.c reads a single-triangle BSP leaf
  # through `(gtri **)&np`; clang >= 20 pointer TBAA deletes the store and the
  # Release helper segfaults. Argyll's own Jam build is not -O3 + clang 20.
  set(RELAX_FLAGS -w -Wno-error=implicit-function-declaration
                  -Wno-error=int-conversion -fno-strict-aliasing)
endif()
target_compile_options(argyllgm PRIVATE ${RELAX_FLAGS})
target_compile_options(chromiq-gammap PRIVATE ${RELAX_FLAGS})

if(APPLE)
  target_link_libraries(chromiq-gammap
    m objc
    "-framework CoreFoundation" "-framework Foundation"
    "-framework IOKit" "-framework CoreServices"
  )
elseif(UNIX)
  target_link_libraries(chromiq-gammap m pthread rt dl)
elseif(WIN32)
  target_link_libraries(chromiq-gammap winmm)
  # Static-link the mingw runtime so the .exe depends only on the system CRT
  # (api-ms-win-crt-*, KERNEL32) and needs no libgcc/libwinpthread DLLs beside
  # it — verified via objdump on a local x86_64-w64-mingw32 cross-build.
  if(MINGW)
    target_link_options(chromiq-gammap PRIVATE -static -static-libgcc)
  endif()
endif()
