# Template: every question, and where the hands-off confirmation is asked

Copy this file next to your instrument's specification and fill it in before the panel is
built. It is a CONTRACT: the job, the panel and the tests are checked against it, and a
reviewer reads it first. The i1iO 2 table's version of it is what
`tests/i1io_table/test_final_m1_hands_off_after_every_question.py` walks, page by page.

## The rule

After ANY question the person answers, the next movement is preceded by a hands-off
confirmation. Either a GO page ("The arm is about to move. Please take your hands away from
<the device>", one button **Go**), or the question's own answer IS that confirmation; then its
button says so in words ("<answer>, my hands are away") and its page names the move that
follows at once.

How it is enforced (fill in your own names):

* the job: every answer marks a confirmation as owed unless it is one of the hands-off answers
  (`<job>.HANDS_OFF_ANSWERS`); every step start and every movement inside a step asks GO while
  one is owed;
* the single place that writes to the device refuses any movement line while a confirmation is
  owed (a bug guard: the session stops, nothing moves); a test fixture fails every test in which
  that guard ever fired;
* the panel: every button of its own pages tells the job that the person answered;
* no answer is a default button; Enter, Return and Space never answer; Esc never answers with a
  move; a hands-off answer is accepted only after it has been visible for a moment (the i1iO
  table holds it for 0.6 s), so a double click cannot answer the next page.

## Hands-off answers (the button IS the confirmation)

| question | button text | the move that follows at once |
|---|---|---|
| <start the device> | Start <the device>, my hands are away | <the recorded start-up> |
| <the sheet is laid> | The page is laid, and my hands are away from <the device> | <homing, the drive out> |
| <a move into ground no recording reached> | Make this move, my hands are away | that move |
| go | Go | the step's move |

## The job's questions

| question (page id) | what the person may be touching | what moves next | where GO is asked |
|---|---|---|---|
| <in use marker found> | the power switch | nothing (the device is not open yet) | the first move's GO |
| <ready to open> (ticks) | the device, checking it | nothing | the next hands-off answer |
| <aim at mark N> | the free arm | nothing between the aims | GO after the last aim |
| <row failed>: again | the bed, the arm | the row again | GO right after it |
| <row failed>: skip | the bed | the next row | the next row's GO |
| <end of session>: save / discard | anything | nothing; the homing is offered | the homing's GO |

## The panel's own questions

| page (buttons) | what the person may be touching | what moves next | where GO is asked |
|---|---|---|---|
| consent, prepare | nothing is open | nothing | none |
| stopped (Next step / Bring the arm home) | anything | the next step / the homing | its GO |
| problem (Cancel / Send nothing more / Something looks or sounds wrong) | anything | nothing, or only the homing | the homing's GO |
| done (Close) | anything | nothing; the device is let go | none |

## Checks before you call it done

- [ ] every page the job or the panel can show is a row here (compare with the page ids in the
      code: a test can list them);
- [ ] every row says where GO is asked, and "none" only where nothing can move afterwards;
- [ ] a planted fault that skips one hands-off clear is caught by a test;
- [ ] the texts of the hands-off answers say "my hands are away" and name the move.
