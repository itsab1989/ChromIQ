# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental raw-only session orchestration with preserved failure evidence."""
import hashlib,json
from pathlib import Path
from .client import Instrument
from .motion import RawAcquisition,line_command


def capture_raw(host,rows,output,*,name='INDEPENDENT',enable_experimental_motion=False,socket_factory=None):
    """Explicit input geometry only. No reflectance/CGATS claim or live default.

    Validate geometry before registering. The complete pre-scan checks the
    vertical bounds again. Caller must establish that these coordinates match
    the physical chart; there is no arbitrary-chart recognition in this API.
    """
    if not enable_experimental_motion:raise ValueError('Experimental motion requires explicit opt-in')
    encoded=name.encode('ascii')
    if not 1<=len(encoded)<=16 or b'\0' in encoded:raise ValueError('Chart name must fit sixteen ASCII bytes')
    if not 1<=len(rows)<=128:raise ValueError('Expected 1..128 geometry rows')
    for i,row in enumerate(rows):line_command(row,i%6==0,i<len(rows)-1)
    if any(min(p[1] for p in rows[i])>=min(p[1] for p in rows[i+1]) for i in range(len(rows)-1)):raise ValueError('Rows must follow acquisition order')
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    (root/'geometry.json').write_text(json.dumps(rows,indent=2)+'\n')
    kwargs={} if socket_factory is None else {'socket_factory':socket_factory}
    instrument=Instrument(host,**kwargs);workflow=RawAcquisition(instrument,enable_experimental_motion=True)
    report={'success':False,'host':host,'expected_raw_samples':sum(map(len,rows)),'spectral_units':'uninterpreted device float32 blocks','calibrated_reflectance':False,'experimental':True}
    try:
        with instrument:
            workflow.prepare(name)
            pixels=workflow.prescan()
            with (root/'scan.pgm').open('xb') as image:image.write(f'P5\n3638 {len(workflow.image)}\n255\n'.encode()+pixels)
            workflow.measure(rows)
            report['success']=True
    except Exception as error:report['error']=str(error)
    finally:
        instrument.close();report['phase']=workflow.phase.value
        if workflow.calibration:(root/'instrument-calibration.bin').write_bytes(workflow.calibration)
        report['raw_samples']=[{'header':s.header,'blocks':s.blocks} for s in workflow.raw_samples]
        (root/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        instrument.save_transcript(root/'wire')
        (root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n' for p in sorted(root.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
    return report
