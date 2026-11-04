"""Sheet handoff for an ordinary multi-page ChromIQ chart.

One chart and TI3, with the existing checked single-sheet reader used for each
physical page. No transport, conversion or printer implementation lives here.
"""
from dataclasses import replace
import json
import shutil
from pathlib import Path


def measure_pages(chart, settings, session, *, progress, cancelled, on_readings,
                  on_scan, on_patch, on_page, capture):
    from .chart import chart_pages
    from .measurement import (checked_chart, resume_plan, first_table, _keywords,
                              _write_rows, sha, measure_chart)
    from .independent import CaptureFailed

    chart, root = Path(chart), Path(session)
    layout_path, layout, locations = checked_chart(chart)
    pages = chart_pages(layout)
    base, prior, remaining = resume_plan(chart, settings)
    watched = {p: sha(p) for p in (chart, layout_path)}
    destination = chart.with_suffix('.ti3')
    base_sha = sha(destination) if destination.exists() else None
    if base:
        watched[base] = sha(base)
    root.mkdir(parents=True, exist_ok=False)
    (root/'chart-definition.json').write_bytes(layout_path.read_bytes())
    design = {int(r['SAMPLE_ID']): r for r in first_table(chart)[2]}
    all_rows = list(prior)
    original_count = len(prior)
    template = base
    failure = cause = None
    last = None
    identity = None
    if base:
        identity = _keywords(base.read_text(encoding='utf-8'))
    completed_ids = {int(r['SAMPLE_ID']) for r in prior}
    page_records = []
    # One colour calculation for the whole chart (4.3.24): the saved rows'
    # when this is a Resume, ArgyllCMS's method for a new measurement.
    from .native_export import XYZ_METHOD_ARGYLL, xyz_method_of
    xyz_method = (xyz_method_of(_keywords(base.read_text(encoding='utf-8')))
                  if base else XYZ_METHOD_ARGYLL)
    # The exit-sensor wait is only for a sheet THIS Start has just ejected
    # (review of #214, M3). A Resume that begins at page 2 or later starts
    # like any first page: the earlier sheet was taken out long ago, and the
    # wait returns only on a sensor notification that a fresh connection with
    # an empty sensor may never send, which could hold the job for the full
    # hour. No command is added or removed: the first page of a Start never
    # waited.
    ejected_here = False

    def check_inputs():
        if any(sha(p) != digest for p, digest in watched.items()):
            raise ValueError('Chart or measurement changed during FD-9 measurement')

    for page_index, page in enumerate(pages):
        patches = [p for row in page['rows'] for p in row]
        if all(p['id'] in completed_ids for p in patches):
            continue
        offset = len(all_rows) - original_count
        page_dir = root / f'page-{page_index+1:03d}'
        page_dir.mkdir()
        page_chart = page_dir/'chart.ti2'
        page_layout = page_chart.with_suffix('.fd9.json')
        page_layout.write_text(json.dumps(page)+'\n', encoding='utf-8')
        _write_rows(chart, page_chart, [design[p['id']] for p in patches],
                    {'PASSES_IN_STRIPS2': str(len(page['rows'][0]))})
        existing = [r for r in prior if int(r['SAMPLE_ID']) in {p['id'] for p in patches}]
        local = replace(settings, resume=bool(existing), resume_source=None)
        if existing:
            local_source = page_chart.with_suffix('.ti3')
            _write_rows(base, local_source, existing,
                        {'FD9_LAYOUT_SHA256': sha(page_layout)})
            local = replace(local, resume_source=local_source)

        def scan_ready(event):
            adapted = dict(event, session=str(root.resolve()),
                           layout_sha256=watched[layout_path], page=page_index,
                           pages=len(pages), locations=[locations[p['id']] for p in patches],
                           reading_offset=offset)
            # Keep the latest actual scan beside the parent metadata for reopening.
            shutil.copyfile(event['image'], root/'scan-preview.png')
            saved = dict(adapted, image='scan-preview.png')
            (root/'scan-preview.json').write_text(json.dumps(saved)+'\n', encoding='utf-8')
            on_scan(adapted)

        def patch_ready(event):
            if on_patch:
                on_patch(dict(event, session=str(root.resolve()),
                              layout_sha256=watched[layout_path], page=page_index))

        try:
            check_inputs()
            if cancelled():
                raise InterruptedError('Operator stopped between FD-9 pages')
            # Announce the queued sheet. The capture waits read-only for the
            # old sheet to clear before beginning a new loading job.
            on_page(page_index+1, len(pages))
            check_inputs()
            result = measure_chart(page_chart, local, page_dir/'capture',
                progress=progress, cancelled=cancelled,
                on_readings=lambda n: on_readings(offset+n), on_scan=scan_ready,
                on_patch=patch_ready if on_patch else None, capture=capture,
                _expected_identity=identity, _wait_for_sheet_clear=ejected_here,
                _sheet_check=False, _xyz_method=xyz_method)
            ejected_here = True
            last = result
            template = Path(result['staged'])
            metadata = _keywords(template.read_text(encoding='utf-8'))
            if identity is None:
                identity = metadata
            _, _, measured = first_table(template)
            # Is it the sheet that was asked for (review of #214, M4)? A sheet
            # whose readings clearly fit another page, or this page turned
            # round, stops here, before any of it is filed.
            from .page_check import SKIPPED_LINE, check_sheet
            skipped = check_sheet(pages, page_index, design, measured)
            if skipped:
                progress(SKIPPED_LINE + skipped)
            new = [r for r in measured if int(r['SAMPLE_ID']) not in completed_ids]
            all_rows += new
            completed_ids.update(int(r['SAMPLE_ID']) for r in new)
            page_records.append({'page': page_index+1, 'session': str(Path(result['session']).relative_to(root)),
                                 'complete': result['complete'], 'patches': len(measured)})
            failure = result.get('acquisition_error')
            cause = result.get('acquisition_exception')
            if not result['complete']:
                break
        except Exception as error:
            from .page_check import SheetMismatch
            if not all_rows or (isinstance(error, SheetMismatch)
                                and len(all_rows) == original_count):
                # Nothing new from this Start: a refused sheet leaves
                # nothing to save, so no ending question offers to file the
                # unchanged measurement again (review r1 L8).
                raise
            failure, cause = str(error), error
            break
    check_inputs()
    if not template or not all_rows:
        raise CaptureFailed(root, failure or 'No complete FD-9 rows measured', cause=cause)
    staged = root/'measurement.ti3'
    sources = []
    if base:
        old = _keywords(base.read_text(encoding='utf-8'))
        sources = old.get('FD9_SOURCE_SESSIONS', old.get('CHROMIQ_FD9_SESSION','')).split(',')
    sources = [s for s in sources if s] + [root.name]
    _write_rows(template, staged, all_rows, {
        'FD9_LAYOUT_SHA256': watched[layout_path],
        'FD9_SOURCE_SESSIONS': ','.join(sources),
        'CHROMIQ_FD9_SESSION': root.name,
        'FD9_PARENT_MEASUREMENT_SHA256': watched.get(base, ''),
    })
    meta = _keywords(staged.read_text(encoding='utf-8'))
    result = dict(last or {}, chart=str(chart), session=str(root), staged=str(staged),
                  destination=str(destination), condition=settings.condition,
                  chart_sha256=watched[chart], layout_sha256=watched[layout_path],
                  base_sha256=base_sha, staged_sha256=sha(staged),
                  patches=len(all_rows), new_readings=len(all_rows)-original_count,
                  complete=len(all_rows)==len(locations), acquisition_error=failure,
                  cancelled=bool(cancelled()), SDK_runtime_dependency=False,
                  research_only=False, conversion_source=('instrument_model' if
                    meta.get('FD9_CONVERSION_SOURCE')=='INSTRUMENT_MODEL' else 'instrument_firmware'),
                  model_sha256=meta.get('FD9_MODEL_SHA256'),
                  factory_sections_sha256=meta.get('FD9_FACTORY_SHA256'), pages=page_records)
    result.pop('acquisition_exception', None)
    (root/'measurement-metadata.json').write_text(json.dumps(result,indent=2)+'\n', encoding='utf-8')
    return result | {'acquisition_exception': cause}
