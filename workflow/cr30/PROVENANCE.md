# workflow/cr30 — vendored CR30 reference implementation

Source: <https://github.com/itsab1989/chromiq-cr30-research>, `src/cr30/`.
Licence: **MIT**. ChromIQ is GPLv3; MIT code may be incorporated provided the
notice travels with it, which is what this file is for. Same pattern as
`native/instlib/PROVENANCE.md`.

    MIT License — Copyright (c) 2026 chromiq-cr30-research contributors
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

## What this is

The hardware-verified CR30 protocol implementation: framing, identity,
measurement decoding, both transports (USB serial and BLE), and the guards that
keep an untrustworthy reading out of a profile.

**Do not edit these files here.** Fix upstream in the research repository, where
the replay tests and captures live, and re-vendor. The upstream suite runs with
no hardware attached.

## What it is NOT

It is not a colour-management layer. `colour.py` exists only to turn a spectrum
into XYZ/Lab for ChromIQ; ChromIQ's own colour handling is unchanged.

## The one thing to know before using it

`Measurement.check_usable()` **raises** rather than returning a doubtful reading.
That is deliberate: a magnet near the aperture makes the CR30 return a stored
constant instead of measuring, and the transaction is indistinguishable from a
real one at the protocol level — correct framing, valid checksum, plausible
spectrum, no error. Detection is behavioural and it lives in that method.
Never downgrade it to a warning.
