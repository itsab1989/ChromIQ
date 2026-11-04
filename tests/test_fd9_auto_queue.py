"""Next-page queuing waits for observed exit clearance, without another click."""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
import threading

import pytest
from tests.test_fd9_partial import setup
from tests.test_fd9_normal_measurement import tab


def test_worker_queues_next_page_without_waiting_for_continue(setup,qtbot):
    from ui.fd9_measurement import FD9Job
    s=setup;job=FD9Job(s.chart,s.settings,s.tmp/'queue')
    seen=[];job.page_requested.connect(lambda p,n:seen.append((p,n)))
    # It returns immediately; a sheet-clear wait belongs to the acquisition.
    job.queue_page(2,3)
    assert seen==[(2,3)]
    job.request_stop()
    with pytest.raises(InterruptedError):job.queue_page(3,3)


def test_notice_has_no_continue_and_closes_when_insertion_is_ready(tab,setup):
    tab._fd9_live=True
    tab._fd9_page_requested(2,3)
    assert not tab._page_pause_panel.isHidden()
    assert tab._page_pause_continue_btn.isHidden()
    tab._fd9_progress('FD9 insertion screen ready. Insert chart arrow first, printed face up.')
    assert tab._page_pause is None and tab._page_pause_panel.isHidden()
    assert not tab._page_pause_continue_btn.isHidden()  # restored for other instruments
    tab._fd9_close_insert_window();tab._fd9_live=False


def test_stop_during_queued_wait_restores_shared_page_controls(tab,setup):
    tab._fd9_page_requested(2,2)
    tab._fd9_restore_controls()
    assert tab._page_pause is None and tab._page_pause_panel.isHidden()
    assert not tab._page_pause_continue_btn.isHidden()


def test_multi_page_capture_waits_for_clearance_only_after_first_sheet(setup):
    from types import SimpleNamespace
    import json
    from tests.test_fd9_multipage import make_chart
    from tests.test_fd9_bidirectional import acquisition
    from tests.test_fd9_factory_workflow import native_settings
    from workflow.fd9.measurement import measure_chart
    s=setup;s.chart=make_chart(s.tmp,count=21).ti2_path
    waits=[]
    def capture(package,definition,root,host,**kw):
        page=json.loads(definition.read_text(encoding='utf-8'))
        waits.append(kw.get('wait_for_sheet_clear',False))
        local=SimpleNamespace(**(s.__dict__|{'layout':page}))
        return acquisition(local,sum(map(len,page['rows'])))(package,definition,root,host,**kw)
    result=measure_chart(s.chart,native_settings(s),s.tmp/'automatic',capture=capture)
    assert result['complete'] and waits==[False,True,True]


def test_stop_during_next_sheet_clearance_keeps_the_completed_page(setup):
    from types import SimpleNamespace
    import json
    from tests.test_fd9_multipage import make_chart
    from tests.test_fd9_bidirectional import acquisition
    from tests.test_fd9_factory_workflow import native_settings
    from workflow.fd9.independent import CaptureFailed
    from workflow.fd9.measurement import measure_chart,first_table,publish_measurement,resume_plan
    from dataclasses import replace
    s=setup;s.chart=make_chart(s.tmp).ti2_path
    stopped=threading.Event()
    def capture(package,definition,root,host,**kw):
        if kw.get('wait_for_sheet_clear'):
            stopped.set()
            raise CaptureFailed(root,'Invented stop waiting for sheet clearance',
                                cause=InterruptedError())
        page=json.loads(definition.read_text(encoding='utf-8'))
        local=SimpleNamespace(**(s.__dict__|{'layout':page}))
        return acquisition(local,9)(package,definition,root,host,**kw)
    settings=native_settings(s)
    result=measure_chart(s.chart,settings,s.tmp/'stopped',capture=capture,
                         cancelled=stopped.is_set)
    assert result['cancelled'] and not result['complete'] and result['patches']==9
    assert len(first_table(result['staged'])[2])==9
    publish_measurement(result['staged'],result['destination'],s.chart,allow_partial=True)
    assert len(resume_plan(s.chart,replace(settings,resume=True))[1])==9


def test_a_resume_that_starts_at_a_later_page_does_not_wait_for_the_sensor(setup):
    """M3 (review of #214): the exit-sensor wait is for a sheet this Start has
    ejected. A Resume beginning at page 2 starts like a first page, so it
    cannot sit under "Prepare page 2" for an hour waiting for a notification
    an empty sensor may never send."""
    from dataclasses import replace
    from tests.test_fd9_multipage import capture_pages, make_chart
    from tests.test_fd9_factory_workflow import native_settings
    from workflow.fd9.measurement import measure_chart, publish_measurement
    s = setup
    s.chart = make_chart(s.tmp, count=21).ti2_path        # three pages
    settings = native_settings(s)
    capture, _ = capture_pages(s, stop_page=2)
    waits = []

    def watched(*a, **kw):
        waits.append(kw.get('wait_for_sheet_clear', False))
        return capture(*a, **kw)
    partial = measure_chart(s.chart, settings, s.tmp / 'first', capture=watched)
    assert not partial['complete'] and waits == [False, True]
    publish_measurement(partial['staged'], partial['destination'], s.chart,
                        allow_partial=True)
    capture, calls = capture_pages(s)
    waits.clear()
    final = measure_chart(s.chart, replace(settings, resume=True),
                          s.tmp / 'resumed', capture=watched)
    assert final['complete']
    assert [c[0] for c in calls] == [2, 3]
    assert waits == [False, True]      # page 2 starts fresh, page 3 waits
