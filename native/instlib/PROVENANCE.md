# Vendored ArgyllCMS standalone instrument library

These files are a subset of ArgyllCMS 3.5.0 by Graeme W. Gill, copied
byte-identical from the official source distribution (except the two
patched files listed below), following the file list of Graeme's own
standalone packaging script
`spectro/instlib.ksh` (the "instlib" distribution, GPLv2-or-later —
see License2.txt; `chartread.c.orig` is from the main tree, AGPLv3 —
see License.txt). `sa_config.h` is `h/aconfig.h` renamed, exactly as
instlib.ksh does.

ChromIQ's fork lives in `../chartread_helper/` and diffs against
`chartread.c.orig`. To bump Argyll: re-run `scripts/vendor_instlib.py`
against the new source tree and rebuild.

## ChromIQ patches

Two library files depart from upstream. `scripts/vendor_instlib.py`
re-applies both patches on every re-vendor (its `PATCHES` table), and
stops if one no longer applies.

- **`rspl1.c`, `set_rspl`**: upstream writes the grid index at
  `iv[-1-1]`. The function's own comment, `rspl.h` and the full `rspl.c`
  put it at `iv[-e-1]`, which for this 1-D spline is `iv[-0-1]`, and
  `xcal.c` reads it there. Unpatched, every calibration curve the engine
  resamples comes from an uninitialised index, so the `.ti3` of any chart
  carrying a printer calibration (`-K`/`-I`) got an all-`nan` CAL table
  that colprof refuses. The fix is needed for ChromIQ's use of rspl1:
  stock Argyll links the full rspl and never reaches this line.
- **`conv.c`, `msec_beep`/`normal_beep`** (#148): under
  `CHROMIQ_APPLE_BEEP` the beep plays through AudioToolbox instead of
  writing a BEL to stdout, which is the engine's JSON channel. The macOS
  build is deliberately not `UNIX_APPLE` (see `CMakeLists.txt`).

| patched file | upstream sha256 (first 16) | shipped sha256 (first 16) |
|---|---|---|
| `rspl1.c` | `5c7b0509abf97f44…` | `d53a8d37b30b6e14…` |
| `conv.c` | `c6b04014888cb6f4…` | `1b88327ee6e6d9df…` |

## Files

- Upstream: https://www.argyllcms.com/ (Argyll_V3.5.0)

| vendored file | upstream path | upstream sha256 (first 16) |
|---|---|---|
| `sort.h` | `h/sort.h` | `fa7c1dc3df402cd0…` |
| `numsup.h` | `numlib/numsup.h` | `c74dcb83472eb941…` |
| `numsup.c` | `numlib/numsup.c` | `cf361c4acf302de8…` |
| `pars.h` | `cgats/pars.h` | `fa2a16d349020edd…` |
| `pars.c` | `cgats/pars.c` | `58aaac3ee979e522…` |
| `parsstd.c` | `cgats/parsstd.c` | `ae32ffd37c61c35c…` |
| `cgats.h` | `cgats/cgats.h` | `c26446f743f16868…` |
| `cgats.c` | `cgats/cgats.c` | `71ab80027ca71486…` |
| `cgatsstd.c` | `cgats/cgatsstd.c` | `160d473be5d4879e…` |
| `xspect.h` | `xicc/xspect.h` | `10d1adf61cd5e247…` |
| `xspect.c` | `xicc/xspect.c` | `ec494fe4a87f3498…` |
| `ccss.h` | `xicc/ccss.h` | `222a0627fea1e46b…` |
| `ccss.c` | `xicc/ccss.c` | `9d14e965c1ca61d8…` |
| `ccmx.h` | `xicc/ccmx.h` | `b533ab7d79d62f43…` |
| `ccmx.c` | `xicc/ccmx.c` | `efacd1f04ba9e524…` |
| `xcolorants.h` | `xicc/xcolorants.h` | `785d5d2420c0255b…` |
| `xcolorants.c` | `xicc/xcolorants.c` | `944ad3fb8945ad5e…` |
| `xcal.h` | `xicc/xcal.h` | `a68e26e3f490010a…` |
| `xcal.c` | `xicc/xcal.c` | `01259ba8882861cc…` |
| `rspl1.h` | `rspl/rspl1.h` | `3192a783f005659c…` |
| `rspl1.c` | `rspl/rspl1.c` | `5c7b0509abf97f44…` |
| `License2.txt` | `spectro/License2.txt` | `b1a57182be3d861a…` |
| `pollem.h` | `spectro/pollem.h` | `56753dbe66e5a2fe…` |
| `pollem.c` | `spectro/pollem.c` | `7bacf20cba9a8728…` |
| `conv.h` | `spectro/conv.h` | `be569df7feee81da…` |
| `conv.c` | `spectro/conv.c` | `c6b04014888cb6f4…` |
| `sa_conv.h` | `spectro/sa_conv.h` | `b8a46e5797f3a2cf…` |
| `sa_conv.c` | `spectro/sa_conv.c` | `a1042fec995dd14b…` |
| `aglob.c` | `spectro/aglob.c` | `28025ece58dd39f6…` |
| `aglob.h` | `spectro/aglob.h` | `a4dbf05ddd971ef5…` |
| `hidio.h` | `spectro/hidio.h` | `1df1e34b65cc6a5c…` |
| `hidio.c` | `spectro/hidio.c` | `3bf1019968a388e3…` |
| `icoms.h` | `spectro/icoms.h` | `adcccbdec3b3d463…` |
| `dev.h` | `spectro/dev.h` | `846cc76a63dd0581…` |
| `inst.h` | `spectro/inst.h` | `8f0c69beee979a00…` |
| `inst.c` | `spectro/inst.c` | `5c57222a05ce6dc5…` |
| `insttypes.c` | `spectro/insttypes.c` | `c6a7645a3e0f3b22…` |
| `insttypes.h` | `spectro/insttypes.h` | `89a7c677e894a065…` |
| `insttypeinst.h` | `spectro/insttypeinst.h` | `3f11fa767758213a…` |
| `instappsup.c` | `spectro/instappsup.c` | `249e0bfdb8904f8e…` |
| `instappsup.h` | `spectro/instappsup.h` | `476f1d33cf9fa70e…` |
| `disptechs.h` | `spectro/disptechs.h` | `b3fc33302397f671…` |
| `disptechs.c` | `spectro/disptechs.c` | `8f37cdaa7ee2262e…` |
| `dtp20.c` | `spectro/dtp20.c` | `e2f15f0814b37aec…` |
| `dtp20.h` | `spectro/dtp20.h` | `1bd3ff0c55b7d644…` |
| `dtp22.c` | `spectro/dtp22.c` | `6abedc3c8dad7f44…` |
| `dtp22.h` | `spectro/dtp22.h` | `45b296525b675efa…` |
| `dtp41.c` | `spectro/dtp41.c` | `7de062ca76cc153d…` |
| `dtp41.h` | `spectro/dtp41.h` | `14ec46f93acc1dd2…` |
| `dtp51.c` | `spectro/dtp51.c` | `a938a8c294849ea6…` |
| `dtp51.h` | `spectro/dtp51.h` | `e996756118a4b813…` |
| `dtp92.c` | `spectro/dtp92.c` | `d717cbd8af5fbd2d…` |
| `dtp92.h` | `spectro/dtp92.h` | `ae0ac45fc7321691…` |
| `ss.h` | `spectro/ss.h` | `98a3f9d4a9df327e…` |
| `ss.c` | `spectro/ss.c` | `594dfa78d9611dc2…` |
| `ss_imp.h` | `spectro/ss_imp.h` | `9860268d0a59c798…` |
| `ss_imp.c` | `spectro/ss_imp.c` | `22533a5cadbc2bce…` |
| `i1disp.c` | `spectro/i1disp.c` | `5363429e9e0b5638…` |
| `i1disp.h` | `spectro/i1disp.h` | `9c99b8eb48cdbfa2…` |
| `i1d3.h` | `spectro/i1d3.h` | `fa31795186e5f8ac…` |
| `i1d3.c` | `spectro/i1d3.c` | `65839017319d335a…` |
| `i1pro.h` | `spectro/i1pro.h` | `ae0039277095a8c6…` |
| `i1pro.c` | `spectro/i1pro.c` | `ac75b6e3f47537b8…` |
| `i1pro_imp.h` | `spectro/i1pro_imp.h` | `c37813e4b43a9bff…` |
| `i1pro_imp.c` | `spectro/i1pro_imp.c` | `8b8516cdd89e21de…` |
| `i1pro3.h` | `spectro/i1pro3.h` | `69a2d55f6497898d…` |
| `i1pro3.c` | `spectro/i1pro3.c` | `9c4b1ac9f8af507a…` |
| `i1pro3_imp.h` | `spectro/i1pro3_imp.h` | `190cceb46fe8bc33…` |
| `i1pro3_imp.c` | `spectro/i1pro3_imp.c` | `42c684afa3bbb15d…` |
| `munki.h` | `spectro/munki.h` | `d1f0beacb316e9a8…` |
| `munki.c` | `spectro/munki.c` | `775ba17c71e42d9c…` |
| `munki_imp.h` | `spectro/munki_imp.h` | `8901bd6bb0649eda…` |
| `munki_imp.c` | `spectro/munki_imp.c` | `1086372fd9cfbd42…` |
| `hcfr.c` | `spectro/hcfr.c` | `4a683b27c1c066d1…` |
| `hcfr.h` | `spectro/hcfr.h` | `277258fde188dea3…` |
| `huey.c` | `spectro/huey.c` | `853ef8bcf7b432fd…` |
| `huey.h` | `spectro/huey.h` | `b12f6b74191760a9…` |
| `colorhug.c` | `spectro/colorhug.c` | `e0e9f66251fbdf00…` |
| `colorhug.h` | `spectro/colorhug.h` | `ca317921021e107e…` |
| `spyd2.c` | `spectro/spyd2.c` | `2e2db17447747404…` |
| `spyd2.h` | `spectro/spyd2.h` | `f056d27b3f925086…` |
| `spydX.c` | `spectro/spydX.c` | `21c52591efbd0b92…` |
| `spydX.h` | `spectro/spydX.h` | `c8076680be02d930…` |
| `specbos.h` | `spectro/specbos.h` | `695f5e781227c55f…` |
| `specbos.c` | `spectro/specbos.c` | `c7e17ec2634d2573…` |
| `kleink10.h` | `spectro/kleink10.h` | `e381c8eda6e36dc8…` |
| `kleink10.c` | `spectro/kleink10.c` | `aa0c3d46052800c6…` |
| `ex1.c` | `spectro/ex1.c` | `b440a4723cf72c9e…` |
| `ex1.h` | `spectro/ex1.h` | `3a46f70b86f6a05a…` |
| `smcube.h` | `spectro/smcube.h` | `efffd3206945ee64…` |
| `smcube.c` | `spectro/smcube.c` | `b52bb0c8bfcb98bc…` |
| `cubecal.h` | `spectro/cubecal.h` | `eb8ff9c89816725f…` |
| `spydX2.c` | `spectro/spydX2.c` | `0605716f89cdd298…` |
| `spydX2.h` | `spectro/spydX2.h` | `8a6732a325c6a16c…` |
| `oemarch.c` | `spectro/oemarch.c` | `912582d709f2c126…` |
| `oemarch.h` | `spectro/oemarch.h` | `c8ad93e28512439a…` |
| `vinflate.c` | `spectro/vinflate.c` | `eb1e8b8e23df69e2…` |
| `inflate.c` | `spectro/inflate.c` | `6b4f772732165cdd…` |
| `LzmaDec.c` | `spectro/LzmaDec.c` | `728c28d31de4cdd2…` |
| `LzmaDec.h` | `spectro/LzmaDec.h` | `e58196c173619b39…` |
| `LzmaTypes.h` | `spectro/LzmaTypes.h` | `044fc75c27434710…` |
| `icoms.c` | `spectro/icoms.c` | `902638b0934ed263…` |
| `icoms_nt.c` | `spectro/icoms_nt.c` | `bef7cc35de665d96…` |
| `icoms_ux.c` | `spectro/icoms_ux.c` | `b9577a4473115022…` |
| `iusb.h` | `spectro/iusb.h` | `94679f69454a96ce…` |
| `usbio.h` | `spectro/usbio.h` | `dd93eeb1458070d2…` |
| `usbio.c` | `spectro/usbio.c` | `fd86ede3492ae1a0…` |
| `usbio_nt.c` | `spectro/usbio_nt.c` | `5002e541aa3d084a…` |
| `usbio_w0.c` | `spectro/usbio_w0.c` | `f385d1f26a7db3ed…` |
| `usbio_dk.c` | `spectro/usbio_dk.c` | `3de50d36d7c8a7cf…` |
| `usbio_ox.c` | `spectro/usbio_ox.c` | `24c3902f59c41d50…` |
| `usbio_lx.c` | `spectro/usbio_lx.c` | `1a686a7f35dc3fe0…` |
| `usbio_bsd.c` | `spectro/usbio_bsd.c` | `9780a8d810b5c42c…` |
| `rspec.h` | `spectro/rspec.h` | `f7f055437c880f65…` |
| `rspec.c` | `spectro/rspec.c` | `05adc19bb0df58a7…` |
| `xdg_bds.c` | `spectro/xdg_bds.c` | `48f089842d30a5d0…` |
| `xdg_bds.h` | `spectro/xdg_bds.h` | `5cd1d9c4183f607b…` |
| `base64.h` | `spectro/base64.h` | `b809980e7adb2851…` |
| `base64.c` | `spectro/base64.c` | `77bb80d24acd4c96…` |
| `xrga.h` | `spectro/xrga.h` | `b315a13a2066a301…` |
| `xrga.c` | `spectro/xrga.c` | `088ec6bdfb88d651…` |
| `driver_api.h` | `spectro/driver_api.h` | `0cb2a3579623ced6…` |
| `sa_config.h` | `h/aconfig.h` | `412a760437832929…` |
| `alphix.c` | `target/alphix.c` | `6042b3873f0ea83d…` |
| `alphix.h` | `target/alphix.h` | `26603e4931350bb4…` |
| `License.txt` | `License.txt` | `432d251a78dbc966…` |
| `chartread.c.orig` | `spectro/chartread.c` | `564d7efc32ee7f89…` |
