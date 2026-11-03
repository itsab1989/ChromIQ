"""Invented FD-9 wire with distinct per-column spectra, shared by GUI tests."""
import hashlib
import json
import struct
from tests.test_fd9_row_workflow import fixture_rows

FORWARD = "increasing-x-v1"
ALTERNATING = "alternating-x-v1"


def fixture(s, root, selected, count, complete=True, policy=ALTERNATING):
    """Give every physical column its own spectrum, in the requested wire order."""
    from fd9_independent.instrument_model import InstrumentModel
    from fd9_independent.protocol import RawSpectrum

    root = fixture_rows(s, root, selected, count, complete)
    columns = len(s.layout['rows'][0])
    report = json.loads((root/'progress.json').read_text(encoding='utf-8'))
    model_dir = root/'spectral-model'
    model = InstrumentModel((model_dir/'matrix.bin').read_bytes(),
                            (model_dir/'conditions.bin').read_bytes(),
                            (model_dir/'sensor-info.bin').read_bytes(),
                            report['factory_sections_sha256'])
    raw_samples = []
    for side in ('sent', 'received'):
        wire = (root/'wire'/f'{side}.bin').read_bytes()
        offset, line, changed = 0, 0, bytearray()
        while offset+4 <= len(wire):
            kind, continuation, size = struct.unpack_from('<BBH', wire, offset)
            if offset+4+size > len(wire):
                break
            payload = wire[offset+4:offset+4+size]
            command = struct.unpack_from('<I', payload)[0]
            if side == 'sent' and command == 0x106:
                if policy == ALTERNATING and line % 2:
                    points = [payload[i:i+16] for i in range(36, len(payload), 16)]
                    payload = payload[:36]+b''.join(reversed(points))
                line += 1
            if side == 'received' and command == 0x305:
                row, column = divmod(len(raw_samples), columns)
                if policy == ALTERNATING and row % 2:
                    column = columns-1-column
                value = .2 + .01*selected[row] + .0005*column
                payload = payload[:12]+struct.pack('<152f', *(
                    [value]*38+[value+.4]*38+[1.0]*76))
                sample = RawSpectrum.decode(payload)
                raw_samples.append({'header':list(sample.header),
                                    'blocks':[list(b) for b in sample.blocks]})
            changed += struct.pack('<BBH', kind, continuation, len(payload))+payload
            offset += 4+size
        (root/'wire'/f'{side}.bin').write_bytes(changed+wire[offset:])
    report['raw_samples'] = raw_samples
    report['native_samples'] = [model.convert(RawSpectrum(
        tuple(r['header']), tuple(tuple(b) for b in r['blocks']))).to_dict()
        for r in raw_samples]
    report['row_order'] = policy
    (root/'progress.json').write_text(json.dumps(report), encoding='utf-8')
    manifest = json.loads((root/'wire/manifest.json').read_text(encoding='utf-8'))
    for side in ('sent', 'received'):
        manifest[side+'_sha256'] = hashlib.sha256(
            (root/'wire'/f'{side}.bin').read_bytes()).hexdigest()
    (root/'wire/manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return root
