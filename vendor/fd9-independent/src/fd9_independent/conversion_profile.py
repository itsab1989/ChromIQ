# SPDX-License-Identifier: GPL-3.0-or-later
"""External, explicitly experimental M0/M1/M2 profiles; SDK-free at runtime."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from .m1_research import M1ResearchModel
from .m2_research import M2ResearchModel, OUTPUT_BANDS
from .spectral import Curve
from .source_calibration import SourceAdjustedM1


@dataclass(frozen=True)
class ResearchM0:
    spectrum: Curve
    calibrated: bool = False
    description: str = 'reference-scoped manufacturer M0 compatibility estimate'


@dataclass(frozen=True)
class ConversionProfile:
    host: str
    calibration_sha256: str
    conditions: dict
    profile_sha256: str

    @classmethod
    def load(cls, path):
        data = Path(path).read_bytes()
        if len(data) > 1024*1024: raise ValueError('Conversion profile exceeds size limit')
        p = json.loads(data)
        if type(p.get('schema')) is not int or p['schema'] != 1 or p.get('calibrated') is not False:
            raise ValueError('Require schema 1 uncalibrated research profile')
        host, digest = p.get('host'), p.get('calibration_sha256')
        if not isinstance(host,str) or not host or not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Profile requires endpoint and calibration-blob SHA256')
        conditions = p.get('conditions')
        if not isinstance(conditions,dict) or not {'M1','M2'}<=set(conditions)<= {'M0','M1','M2'}:
            raise ValueError('Require M1/M2 profiles with optional explicit M0 calibration')
        scope = f'{host}/{digest}'
        models = {}
        for mode, c in conditions.items():
            model_type = M1ResearchModel if mode in ('M0','M1') else M2ResearchModel
            c = conditions[mode]
            if mode in ('M0','M1') and 'source_jacobian' in c:
                models[mode] = SourceAdjustedM1(c['high_source_weights'],scope,c['reference_source'],
                    c['reference_sources'],c['source_jacobian'],c['allowed_source_delta'])
            else: models[mode] = model_type(c['high_source_weights'],scope,c['reference_source'])
        return cls(host,digest,models,hashlib.sha256(data).hexdigest())

    def convert(self, blocks, condition, *, host, calibration, allow_research=False):
        if allow_research is not True: raise ValueError('Explicit research conversion opt-in required')
        if host != self.host or hashlib.sha256(calibration).hexdigest()!=self.calibration_sha256:
            raise ValueError('Endpoint/calibration data does not match conversion profile')
        if condition not in self.conditions: raise ValueError('Condition is not calibrated by this external profile')
        if len(blocks)!=4 or any(len(b)!=38 for b in blocks) or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for b in blocks for v in b):
            raise ValueError('Require four finite 38-band raw arrays')
        model = self.conditions[condition]
        if isinstance(model,SourceAdjustedM1): result = model.apply_raw(blocks,scope=model.scope)
        else: result = model.apply(Curve(OUTPUT_BANDS,blocks[0][2:]),Curve(OUTPUT_BANDS,blocks[1][2:]),scope=model.scope)
        if condition == 'M0':
            # Explicit synthetic black-box probes establish the common M0/M1
            # edge construction and M0 reporting floor. All blend/source
            # calibration remains external; no illuminant or vendor tables.
            return ResearchM0(Curve(OUTPUT_BANDS,tuple(max(.0001,v) for v in result.spectrum.values)))
        return result
