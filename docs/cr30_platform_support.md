# The CR30 on macOS, Windows and Linux

ChromIQ drives the CR30 over **USB** and **Bluetooth**. This page says what
each platform needs, and — for the one case that has caught somebody out — what
to do when the instrument is plugged in and ChromIQ still says it is not there.

## macOS

Nothing to install. The CR30 appears as a serial device on its own, and
Bluetooth needs only the system permission macOS asks for the first time.

## Windows

The CR30 talks through a **CH340-class USB-to-serial chip** (`VID 1A86`,
`PID 7523`). Windows needs WCH's driver for it, and then the instrument appears
as an ordinary COM port that ChromIQ finds by itself.

**Verified working on Windows 11 ARM64**, from a source checkout and from a
packaged build: identified, calibrated white and black, and patches measured.

### If ChromIQ says the instrument is not there

Check Device Manager first. If you see a device with a warning triangle, or an
"Unknown device", the cable and the instrument are fine — Windows simply has no
driver for the chip inside it.

Install WCH's `CH341SER` package from **wch-ic.com**, then unplug and replug the
instrument. On ARM64 you need a **current** version: the 2019 package declares
only x86 and x64, so it installs and does nothing. Version 4.0.2026.02 (11 Feb
2026) declares ARM64 and works. No test-signing, no Secure Boot change and no
reboot are needed.

> ⚠ **Do not use ChromIQ's "Install USB Driver…" button for the CR30.** That
> button installs **WinUSB**, which is right for the colorimeters it lists and
> wrong here: it would replace the serial driver and destroy the COM port the
> CR30 is found through. The button does not offer the CR30 and should not be
> pointed at it by hand.

**Known limitation, and the reason this page exists:** when the driver is
missing, ChromIQ says only that no instrument was found — the same thing it says
when nothing is plugged in at all. The natural conclusion is that the cable or
the instrument is broken, which is the one thing that is not true. Telling those
two apart inside the app is planned; until then, this page is the answer.

## Linux

The CH340 driver is part of the kernel, so the instrument appears as
`/dev/ttyUSB0` (or similar) with nothing to install. Your user needs permission
to open it — on most distributions that means being in the `dialout` group:

```bash
sudo usermod -aG dialout "$USER"      # log out and back in afterwards
```

Not yet verified on hardware.

## Bluetooth

Bluetooth works on every platform ChromIQ supports and needs no driver.

Two things are worth knowing:

* **A phone app that is merely CONNECTED takes the button press exclusively.**
  It does not have to be in use. While a phone holds the connection, a USB
  session sees nothing at all — no readings, not even the ones you take. Close
  the vendor app, or turn the phone's Bluetooth off, before measuring.
* The first connection of a session is made when you calibrate, and can take a
  few seconds.
