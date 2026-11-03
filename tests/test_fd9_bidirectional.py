"""Alternating rows keep logical patch identities; all wire data is invented."""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
from dataclasses import replace
import json

import pytest

from tests.test_fd9_partial import setup, configure
from tests.test_fd9_normal_measurement import tab
from tests.test_fd9_factory_workflow import native_settings
from tests.test_fd9_row_workflow import fixture_rows
from tests._fd9_bidirectional_wire import fixture
from workflow.fd9.independent import CaptureFailed
from workflow.fd9.measurement import (first_table, measure_chart,
                                     publish_measurement, resume_plan)
from workflow.fd9.factory_evidence import verified_factory_rows
from workflow.fd9.native_export import export_native

FORWARD = "increasing-x-v1"
ALTERNATING = "alternating-x-v1"


def ordered(rows, selected, policy):
    return [list(reversed(rows[i])) if policy == ALTERNATING and n % 2 else list(rows[i])
            for n, i in enumerate(selected)]


def acquisition(s, count, complete=True, policies=None):
    def run(source, definition, destination, host, **kw):
        policy = kw.get('row_order', FORWARD)
        assert policy == ALTERNATING
        if policies is not None:
            policies.append((kw['row_indices'], policy))
        root = fixture(s, destination, kw['row_indices'], count, complete, policy)
        kw['on_scan'](root)
        from tests.test_fd9_live_colour import colours
        for n, sample in enumerate(colours(s, root), 1):
            kw['on_readings'](n)
            if kw.get('on_sample'):
                kw['on_sample'](n, sample, root)
        if not complete:
            raise CaptureFailed(root, 'Invented operator stop')
        return root
    return run


def test_descending_line_keeps_the_same_header_and_reverses_only_points(setup):
    from fd9_independent.motion import line_command
    points = [(100., 200.), (200., 201.), (300., 202.)]
    forward = line_command(points, True, True)
    reverse = line_command(list(reversed(points)), True, True)
    assert reverse[:36] == forward[:36]
    assert reverse[36:] == b''.join(forward[i:i+16] for i in (68,52,36))


@pytest.mark.parametrize('points', [
    [(300,200),(200,200),(250,200)], [(300,200),(200,200),(200,200)],
    [(300,200),(float('nan'),200)], [(300,200),(12,200)],
])
def test_bad_descending_geometry_is_still_refused(setup, points):
    from fd9_independent.motion import line_command
    with pytest.raises(ValueError):
        line_command(points, False, False)


def test_alternating_wire_exports_identical_per_patch_spectra_in_all_conditions(setup):
    s=setup
    forward=fixture(s,s.tmp/'forward',[0,1,2],36,policy=FORWARD)
    alternating=fixture(s,s.tmp/'alternating',[0,1,2],36)
    evidence=verified_factory_rows(s.settings.driver_source,alternating,
                                   s.chart.with_suffix('.fd9.json'))
    assert [p['id'] for p in evidence['patches']] == [
        p['id'] for row in ordered(s.layout['rows'],[0,1,2],ALTERNATING) for p in row]
    for mode in ('M0','M1','M2'):
        results=[]
        for root in (forward,alternating):
            out=root/f'{mode}.ti3'
            export_native(s.settings.driver_source,root,s.chart.with_suffix('.fd9.json'),out,mode)
            records=first_table(out)[2]
            assert [int(r['SAMPLE_ID']) for r in records] == list(range(1,37))
            results.append(records)
        assert results[0] == results[1]


@pytest.mark.parametrize('policy',[FORWARD,'unknown',None])
def test_alternating_wire_cannot_be_relabelled_as_another_policy(setup,policy):
    s=setup;root=fixture(s,s.tmp/'mismatch',[0,1,2],36)
    path=root/'progress.json';report=json.loads(path.read_text(encoding='utf-8'))
    if policy is None:
        report.pop('row_order')
    else:
        report['row_order']=policy
    path.write_text(json.dumps(report),encoding='utf-8')
    with pytest.raises(ValueError):
        verified_factory_rows(s.settings.driver_source,root,s.chart.with_suffix('.fd9.json'))


def test_legacy_unmarked_forward_wire_remains_readable(setup):
    s=setup;root=fixture_rows(s,s.tmp/'legacy',[0,1,2],36,True)
    assert 'row_order' not in json.loads((root/'progress.json').read_text(encoding='utf-8'))
    got=verified_factory_rows(s.settings.driver_source,root,s.chart.with_suffix('.fd9.json'))
    assert [p['id'] for p in got['patches']] == list(range(1,37))


def test_live_colour_events_follow_the_actual_acquisition_order(setup):
    s=setup;events=[];scans=[]
    got=measure_chart(s.chart,native_settings(s),s.tmp/'live',capture=acquisition(s,36),
                      on_patch=events.append,on_scan=scans.append)
    records={r['SAMPLE_LOC']:r for r in first_table(got['staged'])[2]}
    from workflow.fd9.measurement import checked_chart
    locations=checked_chart(s.chart)[2]
    expected=[locations[p['id']] for row in ordered(s.layout['rows'],[0,1,2],ALTERNATING) for p in row]
    assert [e['patches'][0]['loc'] for e in events] == expected
    assert scans[0]['measurement_locations'] == expected
    for event in events:
        patch=event['patches'][0];row=records[patch['loc']]
        assert patch['xyz']==pytest.approx([float(row[k]) for k in ('XYZ_X','XYZ_Y','XYZ_Z')],abs=1e-8)


@pytest.mark.parametrize('completed_rows',[1,2])
def test_resume_after_odd_or_even_prefix_starts_forward_and_keeps_values(setup,completed_rows):
    s=setup;settings=native_settings(s);policies=[]
    first=measure_chart(s.chart,settings,s.tmp/'first',capture=acquisition(s,12*completed_rows+5,False))
    original=first_table(first['staged'])[2]
    assert [int(r['SAMPLE_ID']) for r in original] == list(range(1,12*completed_rows+1))
    publish_measurement(first['staged'],first['destination'],s.chart,allow_partial=True)
    resumed=replace(settings,resume=True)
    assert resume_plan(s.chart,resumed)[2]==list(range(completed_rows,3))
    last=measure_chart(s.chart,resumed,s.tmp/'resumed',
        capture=acquisition(s,12*(3-completed_rows),policies=policies))
    assert last['complete'] and first_table(last['staged'])[2][:len(original)]==original
    assert policies==[(list(range(completed_rows,3)),ALTERNATING)]


def test_progress_highlights_the_reverse_row_from_its_measured_end(tab,setup):
    from types import SimpleNamespace
    s=setup;configure(tab,s)
    root=s.tmp/'ui';tab._fd9_job=SimpleNamespace(session=root)
    tab._fd9_live=True
    def counts(n):
        tab._fd9_count_changed(n)
        if n==13:
            assert tab._fd9_ordered_locations[23] in tab._progress_locs
            assert tab._fd9_ordered_locations[12] not in tab._progress_locs
    try:
        measure_chart(s.chart,native_settings(s),root,capture=acquisition(s,36),
                      on_scan=tab._fd9_scan_ready,on_readings=counts)
        assert tab._preview.measurement_progress()==100
    finally:
        tab._fd9_live=False


def test_three_pages_restart_direction_and_keep_global_progress(tab,setup):
    from types import SimpleNamespace
    from tests.test_fd9_multipage import make_chart
    from workflow.fd9.measurement import checked_chart
    from workflow.fd9.chart import chart_pages
    s=setup;s.chart=make_chart(s.tmp,count=21).ti2_path
    _,layout,locations=checked_chart(s.chart)
    pages=chart_pages(layout)
    assert len(pages)==3
    configure(tab,s)
    destination=s.tmp/'pages';tab._fd9_job=SimpleNamespace(session=destination)
    tab._fd9_live=True
    scans=[];events=[];counts=[]
    def scan(event):
        scans.append(event)
        tab._fd9_scan_ready(event)
    def count(n):
        counts.append(n);tab._fd9_count_changed(n)
        if n==13:
            # Page 2 also starts forward, then its second row starts at column 3.
            patch=pages[1]['rows'][1][-1]
            assert locations[patch['id']] in tab._progress_locs
            assert len(tab._progress_locs)==13
    def capture(source,definition,output,host,**kw):
        page=json.loads(definition.read_text(encoding='utf-8'))
        local=SimpleNamespace(**(s.__dict__|{'layout':page}))
        return acquisition(local,sum(map(len,page['rows'])))(source,definition,output,host,**kw)
    try:
        result=measure_chart(s.chart,native_settings(s),destination,capture=capture,
            on_scan=scan,on_readings=count,on_patch=events.append)
        assert result['complete'] and result['patches']==21
        assert counts==list(range(1,22))
        assert [e['reading_offset'] for e in scans]==[0,9,18]
        assert tab._preview.current_page()==2
        assert tab._preview.measurement_progress()==100
        expected=[locations[p['id']] for page in pages for row in
                  ordered(page['rows'],range(len(page['rows'])),ALTERNATING) for p in row]
        assert [e['patches'][0]['loc'] for e in events]==expected
    finally:
        tab._fd9_live=False


@pytest.mark.parametrize('options',[{'row_order':'unknown'},
    {'row_order':ALTERNATING,'native_factory':True,'factory_row_sequencing':False}])
def test_unsupported_policy_fails_before_connecting_or_creating_output(setup,monkeypatch,options):
    import fd9_independent
    from workflow.fd9.independent import capture_layout
    calls=[]
    monkeypatch.setattr(fd9_independent,'Instrument',lambda *a,**kw:calls.append(a))
    root=setup.tmp/'not-created'
    with pytest.raises(ValueError):
        capture_layout(setup.settings.driver_source,setup.chart.with_suffix('.fd9.json'),
                       root,'invented',allow_experimental=True,**options)
    assert not calls and not root.exists()


@pytest.mark.parametrize('policy',[ALTERNATING,'unknown'])
def test_legacy_native_point_evidence_cannot_claim_alternating_order(setup,policy):
    from tests.test_fd9_factory_workflow import fixture_native
    from workflow.fd9.native_evidence import verified_native_rows
    s=setup;root=fixture_native(s,s.tmp/'legacy-native',[0,1,2],36,True)
    path=root/'progress.json';report=json.loads(path.read_text(encoding='utf-8'))
    report['row_order']=policy
    path.write_text(json.dumps(report),encoding='utf-8')
    with pytest.raises(ValueError,match='forward row order'):
        verified_native_rows(s.settings.driver_source,root,s.chart.with_suffix('.fd9.json'))
