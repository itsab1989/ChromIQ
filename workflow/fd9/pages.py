"""Sheet handoff for an ordinary multi-page ChromIQ chart.

One chart and TI3, with the existing checked single-sheet reader used for each
physical page. No transport, conversion or printer implementation lives here.

THE SHEET CHECK ASKS (4.3.25, F7). After each sheet, `page_check.check_sheet`
compares the readings with what the chart should give. When they clearly fit
the page turned round, or another page, the worker PAUSES and asks the person
through *on_mismatch* (the strip check's way, M-STRIP-READ-TWICE), instead of
ending the measurement:

* "again" (the safe answer, and what closing the window does): these readings
  are set aside and the same page is asked for again;
* "refile": a sheet turned round is saved turned round, and another page is
  saved as that page (replacing its earlier readings), after which the page
  that was asked for is asked for again. Offered only for a COMPLETE sheet
  read in one go, so no reading can land on the wrong patch;
* "keep": the readings are saved as read.

No device command is added: "again" is the next sheet of the same kind the
FD-9 is already asked for between pages. Without *on_mismatch* (a caller from
before 4.3.25) a mismatch ends the measurement as it did.
"""
from dataclasses import replace
import json
import shutil
from pathlib import Path


def _order_of(pages):
    return {p['id']: i for i, p in enumerate(
        p for page in pages for row in page['rows'] for p in row)}


def measure_pages(chart, settings, session, *, progress, cancelled, on_readings,
                  on_scan, on_patch, on_page, capture, on_mismatch=None):
    from .chart import chart_pages
    from .measurement import (checked_chart, resume_plan, first_table, _keywords,
                              _write_rows, sha, measure_chart)
    from .independent import CaptureFailed
    from . import page_check as pc

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
    # What the sheet check found, per page, carried over from a Resume.
    notes = {}
    if base:
        identity = _keywords(base.read_text(encoding='utf-8'))
        notes = {k: v for k, v in identity.items()
                 if k.startswith('FD9_SHEET_CHECK_PAGE_')}
    completed_ids = {int(r['SAMPLE_ID']) for r in prior}
    prior_ids = set(completed_ids)
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
    stop_all = False

    def check_inputs():
        if any(sha(p) != digest for p, digest in watched.items()):
            raise ValueError('Chart or measurement changed during FD-9 measurement')

    def file_rows(rows, page_ids):
        """Put *rows* in for the patches *page_ids*, replacing any readings
        of them there were (a page saved as another page)."""
        nonlocal all_rows, original_count
        replaced = [r for r in all_rows if int(r['SAMPLE_ID']) in page_ids]
        original_count -= sum(1 for r in replaced
                              if int(r['SAMPLE_ID']) in prior_ids)
        prior_ids.difference_update(page_ids)
        all_rows = [r for r in all_rows if int(r['SAMPLE_ID']) not in page_ids]
        all_rows += rows
        completed_ids.difference_update(page_ids)
        completed_ids.update(int(r['SAMPLE_ID']) for r in rows)

    for page_index, page in enumerate(pages):
        patches = [p for row in page['rows'] for p in row]
        attempt = 0
        while not stop_all:
            if all(p['id'] in completed_ids for p in patches):
                break
            offset = len(all_rows) - original_count
            # A page measured again gets a folder of its own beside the
            # first, ending in the page number as the first one does.
            page_dir = root / (f'page-{page_index+1:03d}' if not attempt
                               else f'again{attempt}-page-{page_index+1:03d}')
            page_dir.mkdir()
            page_chart = page_dir/'chart.ti2'
            page_layout = page_chart.with_suffix('.fd9.json')
            page_layout.write_text(json.dumps(page)+'\n', encoding='utf-8')
            _write_rows(chart, page_chart, [design[p['id']] for p in patches],
                        {'PASSES_IN_STRIPS2': str(len(page['rows'][0]))})
            ids = {p['id'] for p in patches}
            existing = [r for r in all_rows if int(r['SAMPLE_ID']) in ids]
            local = replace(settings, resume=bool(existing), resume_source=None)
            if existing:
                local_source = page_chart.with_suffix('.ti3')
                _write_rows(base or template, local_source, existing,
                            {'FD9_LAYOUT_SHA256': sha(page_layout)})
                local = replace(local, resume_source=local_source)

            def scan_ready(event, page_index=page_index, patches=patches,
                           offset=offset):
                adapted = dict(event, session=str(root.resolve()),
                               layout_sha256=watched[layout_path], page=page_index,
                               pages=len(pages), locations=[locations[p['id']] for p in patches],
                               reading_offset=offset)
                # Keep the latest actual scan beside the parent metadata for reopening.
                shutil.copyfile(event['image'], root/'scan-preview.png')
                saved = dict(adapted, image='scan-preview.png')
                (root/'scan-preview.json').write_text(json.dumps(saved)+'\n', encoding='utf-8')
                on_scan(adapted)

            def patch_ready(event, page_index=page_index):
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
                    on_readings=lambda n, offset=offset: on_readings(offset+n),
                    on_scan=scan_ready,
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
                # Is it the sheet that was asked for (review of #214, M4)? A
                # sheet whose readings clearly fit another page, or this page
                # turned round, is not filed before the person has said what
                # it is (4.3.25, F7).
                target_index = page_index
                note = pc.MATCHED
                try:
                    skipped = pc.check_sheet(pages, page_index, design, measured)
                    if skipped:
                        progress(pc.SKIPPED_LINE + skipped)
                        note = pc.NOT_CHECKED
                except pc.SheetMismatch as mismatch:
                    if on_mismatch is None or cancelled():
                        raise
                    read_now = {int(r['SAMPLE_ID']) for r in measured} - {
                        int(r['SAMPLE_ID']) for r in existing}
                    whole = bool(result['complete']) and not existing \
                        and read_now == ids
                    answer = on_mismatch({
                        'kind': mismatch.kind, 'page': page_index + 1,
                        'found': mismatch.found, 'pages': len(pages),
                        'turned': mismatch.turned, 'complete': whole,
                        'measured': len(read_now), 'total': len(ids),
                        'reason': str(mismatch),
                        # In grid order, so the live preview can move or
                        # drop this sheet's colours with the answer (L6).
                        'locations': [locations[p['id']] for p in patches],
                        'found_locations': [
                            locations[p['id']]
                            for row in pages[mismatch.found - 1]['rows']
                            for p in row]})
                    if answer not in (pc.REFILE, pc.KEEP) or (
                            answer == pc.REFILE and not whole):
                        answer = pc.AGAIN
                    if answer == pc.AGAIN:
                        progress(f'Sheet check: page {page_index+1} set aside '
                                 'to be measured again')
                        attempt += 1
                        continue
                    if answer == pc.KEEP:
                        note = (pc.TURNED_KEPT if mismatch.kind == 'turned'
                                else pc.OTHER_PAGE_KEPT.format(
                                    found=mismatch.found))
                    else:
                        target_index = mismatch.found - 1
                        measured = pc.refile(measured, pages, page_index,
                                             target_index, mismatch.turned,
                                             design, locations)
                        note = (pc.TURNED_SAVED_TURNED
                                if target_index == page_index
                                else pc.FROM_SHEET_ASKED_AS.format(
                                    page=page_index + 1))
                notes[pc.PROVENANCE_KEY.format(page=target_index + 1)] = note
                if target_index != page_index:
                    target_ids = {p['id'] for row in pages[target_index]['rows']
                                  for p in row}
                    file_rows(measured, target_ids)
                    page_records.append({'page': target_index+1,
                                         'session': str(Path(result['session']).relative_to(root)),
                                         'complete': True, 'patches': len(measured),
                                         'read_as_page': page_index+1})
                    progress(f'Sheet check: the sheet was saved as page '
                             f'{target_index+1}; page {page_index+1} is asked for again')
                    attempt += 1
                    continue
                new = [r for r in measured if int(r['SAMPLE_ID']) not in completed_ids
                       or (note == pc.TURNED_SAVED_TURNED)]
                if note == pc.TURNED_SAVED_TURNED:
                    file_rows(new, ids)
                else:
                    all_rows += new
                    completed_ids.update(int(r['SAMPLE_ID']) for r in new)
                page_records.append({'page': page_index+1, 'session': str(Path(result['session']).relative_to(root)),
                                     'complete': result['complete'], 'patches': len(measured)})
                failure = result.get('acquisition_error')
                cause = result.get('acquisition_exception')
                if not result['complete']:
                    stop_all = True
                break
            except Exception as error:
                if not all_rows or (isinstance(error, pc.SheetMismatch)
                                    and len(all_rows) == original_count):
                    # Nothing new from this Start: a refused sheet leaves
                    # nothing to save, so no ending question offers to file the
                    # unchanged measurement again (review r1 L8).
                    raise
                failure, cause = str(error), error
                stop_all = True
                break
        if stop_all:
            break
    check_inputs()
    if not template or not all_rows:
        raise CaptureFailed(root, failure or 'No complete FD-9 rows measured', cause=cause)
    # The chart's own order, whatever order the sheets were filed in (a
    # page saved as a later page goes in ahead of the pages before it).
    order = _order_of(pages)
    all_rows.sort(key=lambda r: order[int(r['SAMPLE_ID'])])
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
        **dict(sorted(notes.items(),
                      key=lambda kv: int(kv[0].rsplit('_', 1)[1]))),
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
