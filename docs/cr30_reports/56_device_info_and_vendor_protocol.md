STATUS: complete (2026-10-09). Kept for later: device information, the vendor protocol as far as it is known, and what is known about the firmware.

# CR30: device information, vendor protocol, firmware

## 1. Device information, read from Basti's CR30 on 2026-10-09

Run with `scripts/cr30_devinfo.py` (only whitelisted read frames; captures in `56_captures/`).

| Field | USB (`AA 0A 00..03`, ChromIQ's identity query) | Bluetooth (`BB 12 01`, the vendor app's device-info query) |
|---|---|---|
| Model / category | `CR30` (`AA 0A 00`) | `CR30` (@37) |
| Device code | bytes 7..8 of `AA 0A 00`, u16 LE = **793** | u16 LE @5 = **793** (vendor device database: CR30 = 793, CR20 = 792, CR10 = 791) |
| Internal id | `PT694D01E7` (`AA 0A 00` @9) | `PT694D01E7` (@7) |
| Serial / Bluetooth name | `CM454M0223` (`AA 0A 01` @19) | `CM454M0223` (@67; the vendor app calls it the serial number) |
| Software version | `V11.3.` (`AA 0A 01` @49) + build `0.0.20231219` (`AA 0A 02` @5) | `V11.3.0.0.20231219` (@97) |
| Hardware version | `V10.0.0.0` (`AA 0A 02` @29) | `V10.0.0.0` (@127) |
| Status / neutral flag | `AA 0A 03` @19 = 2 | @159 = 0 (not neutral) |

So the Bluetooth reply confirms the two USB guesses: bytes 7..8 of `AA 0A 00` are the device code, and `V11.3.` + the build date is the SOFTWARE version, `V10.0.0.0` the hardware version.

`BB 12 01` reply: 200 bytes, header `bb 12 01 56 00`, byte-sum checksum last, answered within 0.3 s after the wake byte `01`, no polls needed. After `stop_notify` + disconnect the unit advertised again.

## 2. Vendor Bluetooth protocol (ColorMeter app 2.4.27, from its shipped source maps)

Service FFE0, characteristic FFE1; the app writes `01` to wake; frames `BB cmd ...`, checksum = byte sum, last byte.

| cmd | meaning | ChromIQ |
|---|---|---|
| `BB 01 mode rnd4` | trigger a measurement | used |
| `BB 02 (mode+0x10)` | read measurement, 200 bytes | used |
| `BB 10 01` / `BB 11 01` | black / white calibration | used |
| `BB 12 01` | device info (table above) | **read once 2026-10-09, safe; not yet in ChromIQ** |
| `BB 14 t32 lang` | set clock and language | not used (writes) |
| `BB 16 ..` | stored standards and samples | not used |
| `BB 1A ..` | display settings (illuminant, observer, colour space, formula) | not used (writes) |
| `BB 1B 01` | tolerance settings | not used |
| `BB 1E` | calibration dates (white @3, black @8) | not used; possibly useful (when was the unit last calibrated) |
| `BB 21 00 w` | whiteness index | not used |
| `BB 22` | density settings | not used |
| `BB 23 ..` | adjustment ratios (read, write, delete) | not used (writes) |

## 3. Firmware: what is known

- No public firmware image or download URL exists in the vendor's software (ColorMeter Android 2.4.27 and 2.1.27, ColorExpert for Windows 6.0.21 including ColorQC2). The phone app only updates itself.
- ColorExpert has a device upgrade screen with a file picker (a `.duf` file): the firmware is handed to the user, not downloaded.
- ColorExpert's code names commands for entering DFU mode, upgrading the program and upgrading the firmware, and splitting into sub-packages. **No read-back, dump or verify-read command** is named anywhere. The byte values of these commands are not readable statically (the method bodies are protected); they were not decrypted.
- The USB side is a WCH CH554 running CDC firmware ("CH554_CDC"): only the USB-serial bridge, not the measuring processor.
- Consequences:
  - A protocol-level firmware read-out is not known to exist. Probing unknown commands is unsafe, because the DFU and upgrade commands lie somewhere in the same command range and their values are unknown.
  - Reading the measuring processor directly would need the device opened and a debug probe; if its read-out protection is on, removing it typically erases the flash and the factory calibration. Only worth it on an expendable unit.
  - Measured earlier: at most about 4 readings per second. With a ~4 mm aperture on ~6 mm patches, that makes a strip-reading mode no faster than patch-by-patch reading. Whether the limit is the sensor or the firmware is unknown; the firmware would tell (exposure time, continuous lighting or flash).

## 4. Ideas for ChromIQ

1. Note the firmware version at connect: over USB from the identity query ChromIQ already sends; over Bluetooth from `BB 12 01`. A one-time note when it is not `V11.3.0.0.20231219` / `V11.3.` + `0.0.20231219` (the version ChromIQ was tested with).
2. Use the serial (`CM454M0223`) or the internal id (`PT694D01E7`) rather than the Bluetooth name to key a unit's learned tile signature.
3. `BB 1E` (calibration dates) could show when a unit was last calibrated; read-only, but not yet tried on a unit.
