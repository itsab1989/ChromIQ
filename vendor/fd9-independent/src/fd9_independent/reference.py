# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict single-table spectral CGATS reader for independently measured data."""
from dataclasses import dataclass
import math
import shlex
from .spectral import Curve


@dataclass(frozen=True)
class ReferenceSample:
    sample_id: str
    curve: Curve


def read_cgats(text,*,normalization=None):
    """Read nmNNN or SPEC_NNN fields; require explicit normalization.

    Argyll spectral files normally specify SPECTRAL_NORM (typically 100 for
    reflectance percent). Files without it require a caller-provided scale;
    the parser never guesses percent vs fraction from numerical magnitude.
    """
    metadata={};fields=[];data=[];stage='header';complete=False
    for line in text.splitlines():
        tokens=shlex.split(line,comments=True)
        if not tokens:continue
        marker=tokens[0]
        if complete:raise ValueError('Multiple/trailing CGATS tables are unsupported')
        if marker=='BEGIN_DATA_FORMAT':
            if stage!='header' or fields:raise ValueError('Unexpected data format')
            stage='fields';continue
        if marker=='END_DATA_FORMAT':
            if stage!='fields' or not fields:raise ValueError('Missing data fields')
            stage='header';continue
        if marker=='BEGIN_DATA':
            if stage!='header' or not fields:raise ValueError('Unexpected data start')
            stage='data';continue
        if marker=='END_DATA':
            if stage!='data':raise ValueError('Unexpected data end')
            complete=True;continue
        if stage=='fields':fields.extend(tokens)
        elif stage=='data':data.append(tokens)
        elif len(tokens)>=2:metadata[marker]=' '.join(tokens[1:])
    if not complete or int(metadata.get('NUMBER_OF_FIELDS','-1'))!=len(fields) or int(metadata.get('NUMBER_OF_SETS','-1'))!=len(data) or not data:
        raise ValueError('Incomplete CGATS table or count mismatch')
    norm=float(metadata['SPECTRAL_NORM']) if 'SPECTRAL_NORM' in metadata else normalization
    if norm is None or not math.isfinite(norm) or norm<=0:raise ValueError('Explicit positive spectral normalization is required')
    if normalization is not None and 'SPECTRAL_NORM' in metadata and norm!=normalization:raise ValueError('Conflicting normalization values')
    spectral=[]
    for i,f in enumerate(fields):
        suffix=f[5:] if f.startswith('SPEC_') else f[2:] if f.startswith('nm') else None
        if suffix is not None:
            try:w=float(suffix)
            except ValueError:raise ValueError('Invalid spectral field wavelength') from None
            spectral.append((w,i))
    spectral.sort();wavelengths=tuple(w for w,i in spectral)
    if len(spectral)<2 or len(set(wavelengths))!=len(wavelengths):raise ValueError('Missing or duplicate spectral wavelengths')
    if 'SPECTRAL_BANDS' in metadata and int(metadata['SPECTRAL_BANDS'])!=len(spectral):raise ValueError('Spectral band count mismatch')
    for key,value in [('SPECTRAL_START_NM',wavelengths[0]),('SPECTRAL_END_NM',wavelengths[-1])]:
        if key in metadata and float(metadata[key])!=value:raise ValueError('Spectral range mismatch')
    if fields.count('SAMPLE_ID')>1:raise ValueError('Ambiguous sample identifier field')
    id_col=fields.index('SAMPLE_ID') if 'SAMPLE_ID' in fields else None
    samples=[];seen=set()
    for row_num,row in enumerate(data):
        if len(row)!=len(fields):raise ValueError('CGATS row width mismatch')
        sid=row[id_col] if id_col is not None else str(row_num+1)
        if sid in seen:raise ValueError('Duplicate sample identifier')
        seen.add(sid);values=tuple(float(row[i])/norm for w,i in spectral)
        samples.append(ReferenceSample(sid,Curve(wavelengths,values)))
    return metadata,tuple(samples)
