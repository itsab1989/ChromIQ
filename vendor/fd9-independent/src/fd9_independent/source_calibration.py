# SPDX-License-Identifier: GPL-3.0-or-later
"""External local source-response calibration; no SDK or fitted data bundled."""
from dataclasses import dataclass
import math
from .m1_research import M1ResearchModel
from .m2_research import OUTPUT_BANDS
from .spectral import Curve


@dataclass(frozen=True)
class SourceAdjustedM1(M1ResearchModel):
    reference_sources: tuple
    source_jacobian: tuple
    allowed_source_delta: tuple

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self,'reference_sources',tuple(self.reference_sources))
        object.__setattr__(self,'allowed_source_delta',tuple(self.allowed_source_delta))
        object.__setattr__(self,'source_jacobian',tuple(tuple(row) for row in self.source_jacobian))
        if len(self.reference_sources)!=76 or len(self.allowed_source_delta)!=76 or len(self.source_jacobian)!=22 or any(len(row)!=76 for row in self.source_jacobian):
            raise ValueError('Source calibration requires 76 input channels and 22 blend bands')
        if not all(math.isfinite(v) for v in self.reference_sources+self.allowed_source_delta+tuple(v for row in self.source_jacobian for v in row)) or min(self.allowed_source_delta)<=0:
            raise ValueError('Source calibration requires finite values and positive domain bounds')

    def apply_raw(self,blocks,*,scope):
        if len(blocks)!=4 or any(len(b)!=38 for b in blocks) or not all(math.isfinite(v) for b in blocks for v in b):
            raise ValueError('Malformed raw input to source calibration')
        delta=tuple(v-r for v,r in zip(tuple(blocks[2])+tuple(blocks[3]),self.reference_sources))
        if any(abs(d)>limit for d,limit in zip(delta,self.allowed_source_delta)):
            raise ValueError('Source readings exceed the external profile validation domain')
        weights=tuple(w+math.fsum(j*d for j,d in zip(row,delta)) for w,row in zip(self.high_source_weights,self.source_jacobian))
        return M1ResearchModel(weights,self.scope,self.reference_source).apply(
            Curve(OUTPUT_BANDS,blocks[0][2:]),Curve(OUTPUT_BANDS,blocks[1][2:]),scope=scope)
