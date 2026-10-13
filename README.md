# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## ✨ Features

**Scheduling**

- **Time-window planning** — the owner sets when their day starts and ends, and nothing is ever planned outside it
- **Pinned vs. flexible tasks** — a task can be fixed to a time (meds at 8am) or left for the scheduler to place
- **Gap filling** — free gaps between pinned tasks are computed, then flexible tasks take the earliest gap they fit in
- **Priority ordering** — high before medium before low, and on a tie the shorter task first, which fits more into the day
- **Nothing disappears silently** — a task that cannot fit is listed separately with the reason, including how long it needed and how much was actually free

**Sorting** — `Scheduler.sort_by_time()`, `sort_by_priority()`

- Pinned tasks in clock order, flexible ones last, ties broken by title so the output is stable
- Sorts a copy, so a pet's own task list keeps its entry order

**Filtering** — `Scheduler.filter_by_pet()`, `filter_by_status()`, `filter_by_priority()`

- By pet, by done/outstanding, or by priority level
- Pet names match case-insensitively and an unknown name returns nothing rather than raising

**Recurring tasks** — `Task.next_occurrence()`, `Scheduler.complete_task()`

- Daily, weekly (on a chosen weekday), or a one-off on a specific date
- Completing a recurring task automatically queues the next occurrence: daily rolls to tomorrow, weekly to the next matching weekday
- The new copy is not due until its date, so tomorrow's feeding does not appear in today's plan
- The completed task is kept, so each pet's list doubles as a record of what was done

**Conflict detection** — `Scheduler.find_conflicts()`

- Flags any two fixed-time tasks that overlap, with a plain-English warning naming both tasks and both pets
- Warns rather than raising — a clash never stops the app
- Tasks that touch exactly (08:00–09:00 then 09:00–) are back to back, not a conflict
- Conflicts across different pets still count: two pets, one owner, one pair of hands

**Explanation**

- Every scheduled task carries the reason it landed where it did
- Every skipped task carries why it was left out
- `Schedule.explain()` renders the whole thing as readable text

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Terminal output from `python main.py`. One owner, two pets, eight tasks
added deliberately out of order, and a 150-minute morning. It walks
through sorting, filtering, conflict detection, the plan itself, and a
daily task regenerating when it is completed.

```
==============================================================
  PawPal+ - Today's Schedule
==============================================================
  Owner : Jordan
  Pets  : Mochi (cat), Biscuit (dog)
  Day   : Monday, October 12, 2026  (07:30-10:00, 150 min)


==============================================================
  SORTING - Scheduler.sort_by_time()
==============================================================
  As entered:
     flexible  Vet checkup
        07:30  Insulin shot
     flexible  Litter box
        08:05  Eye drops
     flexible  Nail trim
        08:00  Breakfast
     flexible  Morning walk
     flexible  Brush coat

  Sorted by time (pinned first, flexible last):
        07:30  Insulin shot
        08:00  Breakfast
        08:05  Eye drops
     flexible  Brush coat
     flexible  Litter box
     flexible  Morning walk
     flexible  Nail trim
     flexible  Vet checkup

==============================================================
  FILTERING - by pet, and by status
==============================================================
  Mochi (cat)            4 task(s)
          07:30  Insulin shot
          08:05  Eye drops
       flexible  Litter box
       flexible  Vet checkup
  Biscuit (dog)          4 task(s)
          08:00  Breakfast
       flexible  Brush coat
       flexible  Morning walk
       flexible  Nail trim

  Outstanding : 8
  Completed   : 0

==============================================================
  CONFLICTS - Scheduler.find_conflicts()
==============================================================
  1 clash(es) found. The app keeps running:
    ! Biscuit and Mochi overlap: Breakfast runs 08:00-08:10 but Eye drops starts 08:05

==============================================================
  THE PLAN - Scheduler.plan_for()
==============================================================
--------------------------------------------------------------
  TIME          TASK             PET       WHY
--------------------------------------------------------------
  07:30-07:35   Insulin shot     Mochi     pinned to 07:30
  07:35-07:45   Litter box       Mochi     medium priority, earliest free 10 min slot
  08:00-08:10   Breakfast        Biscuit   pinned to 08:00
  08:10-08:40   Morning walk     Biscuit   high priority, earliest free 30 min slot
  08:40-09:40   Vet checkup      Mochi     high priority, earliest free 60 min slot
  09:40-10:00   Brush coat       Biscuit   low priority, earliest free 20 min slot
--------------------------------------------------------------

  NOT SCHEDULED
    - Eye drops (15 min) - fixed time 08:05 overlaps Breakfast
    - Nail trim (25 min) - needs 25 min but the largest free gap left is 15 min

  6 task(s) scheduled, 2 left out.
  Using 135 of 150 minutes (15 min spare).
==============================================================

==============================================================
  RECURRING - completing a task queues the next one
==============================================================
  Added 'Evening feed' (daily).
  Outstanding copies today: 1

  Marked complete on Mon 12 Oct.
  A repeat was created, starting Tue 13 Oct.

  The completed original drops out and the repeat has not
  started yet, so today is clear -- but tomorrow is covered:
    outstanding today    : 0
    outstanding tomorrow : 1
```

## 🧪 Testing PawPal+

Run the whole suite:

```bash
python -m pytest
```

Or just one layer:

```bash
python -m pytest tests/          # the behaviour suite
python -m pytest -q              # quiet, one line per file
python -m pytest -k conflict     # only conflict tests
```

### What the tests cover

| File | Tests | Covers |
|------|-------|--------|
| `test_pawpal_system.py` | 226 | The logic layer, grouped by method — every branch of sorting, filtering, conflicts, recurrence, completion and planning |
| `test_app.py` | 77 | The Streamlit glue, grouped by helper — session state, form handling, table rows |
| `tests/test_pawpal.py` | 66 | The same system grouped by *behaviour*, readable top to bottom as a description of what PawPal+ guarantees |
| `test_ui.py` | 30 | The real app, driven through Streamlit's `AppTest` harness |

The four areas `tests/test_pawpal.py` pins down:

- **Sorting correctness** — pinned tasks come back in clock order, flexible
  ones last. Covers identical times, midnight (`time(0,0)` is falsy, so a
  truthiness check would bury it), minutes rather than just hours, and that
  sorting never reorders a pet's own list.
- **Recurrence logic** — completing a daily task creates tomorrow's. Covers
  month ends, year ends, leap days, and the subtle one: a weekly task
  finished *on* its own weekday must wait a full 7 days, not 0.
- **Conflict detection** — tasks at the same time are flagged with a warning
  rather than an exception. Covers exact matches, one-minute overlaps,
  touching exactly (*not* a conflict), clashes across different pets, and
  that completed or not-due tasks are excluded.
- **Empty states** — an owner with no pets, a pet with no tasks, a task with
  no pet. None of them crash.

`test_ui.py` runs `app.py` the same way `streamlit run` does, with real
session state and real reruns. It is the only layer that can catch a broken
wire-up — a button calling the wrong method, or an `Owner` being rebuilt
empty on every click. It already caught one: a time picker disabled by a
checkbox in the same form, which meant a pinned task could never be created
through the UI at all.

### Test output

```
$ python -m pytest
test_app.py ............................................................ [ 15%]
.................                                                        [ 19%]
test_pawpal_system.py .................................................. [ 31%]
........................................................................ [ 49%]
........................................................................ [ 67%]
................................                                         [ 75%]
test_ui.py ..............................                                [ 83%]
tests\test_pawpal.py ................................................... [ 96%]
...............                                                          [100%]

============================= 399 passed in 6.08s =============================
```

### Confidence level

**★★★★☆ (4 / 5)**

Four rather than five, and the missing star is deliberate.

**What earns the four:** 399 tests across four layers, including the real
Streamlit app. The edge cases that actually break schedulers are covered
explicitly, not assumed — falsy `0` values for midnight and Monday, exact
window boundaries, leap days, and double-submission. I also sanity-checked
the suite by deliberately breaking four things in `pawpal_system.py` (weekly
repeats landing same-day, touching tasks counting as overlaps, flexible tasks
losing their sort position, and repeats being due immediately). All four
mutations were caught, so the tests are doing real work rather than passing
by luck.

**What costs the fifth star:** I wrote both the code and the tests, so they
agree with each other by construction — a misunderstanding of the *problem*
would appear in both and the tests would happily confirm it. The scheduler
has also never run against a real person's actual week. Specific gaps I know
about: nothing is tested across a daylight-saving boundary, nothing covers
hundreds of tasks, and there is no test for two people using the app at once
because `st.session_state` is per-session by design. The terminal output in
the Sample Output section above is the real check on whether the plans are
sensible, and that is a human reading it, not an assertion.

## 📐 Smarter Scheduling

### Sorting

| Method | Behavior |
|--------|----------|
| `Scheduler.sort_by_time()` | Pinned tasks in clock order first, flexible tasks last, ties broken by title. Sorts a copy, so each pet's own list keeps its entry order. |
| `Scheduler.sort_by_priority()` | Most urgent first, then shortest first on a tie, then title. |
| `Priority.rank()` | Turns the enum into a sortable integer. Sorting the names alphabetically would put `high` before `low` before `medium` — meaningless. |

The sort key in `sort_by_time()` is a three-part tuple:
`(fixed_time is None, fixed_time or time.min, title)`. `False` sorts before
`True`, so the first element alone pushes every flexible task to the back.

### Filtering

| Method | Behavior |
|--------|----------|
| `Scheduler.filter_by_pet(name)` | Tasks for one pet, matched case-insensitively. Returns `[]` for an unknown name rather than raising, since it is driven by user input. |
| `Scheduler.filter_by_status(completed)` | Done (`True`) or outstanding (`False`). |
| `Scheduler.filter_by_priority(priority)` | Tasks at exactly one level. |
| `Scheduler.tasks_due_on(day)` | The planning filter: outstanding **and** due today. |
| `Scheduler.pending_tasks()` / `completed_tasks()` | The two halves of the full list. |

### Conflict detection

| Method | Behavior |
|--------|----------|
| `Scheduler.find_conflicts(day)` | Returns a list of plain-English warnings, one per clashing pair. Never raises and never changes anything — the caller decides whether to show them. |
| `Scheduler.has_conflicts(day)` | The same check as a single boolean. |

Compares every pair of pinned tasks with `itertools.combinations`. Only pinned
tasks can clash, since a flexible task has no fixed time yet. Tasks that touch
exactly (08:00–09:00 and 09:00–09:30) are back to back, not in conflict.
Conflicts across *different* pets are still reported — two pets, one owner.

### Recurring tasks

| Method | Behavior |
|--------|----------|
| `Task.is_due_on(day)` | `DAILY` always, `WEEKLY` on a matching weekday, `ONCE` on `due_date`. A task missing the field its frequency needs returns `False` rather than defaulting to every day. |
| `Task.next_occurrence_date(on)` | Daily → tomorrow. Weekly → the next matching weekday, always at least 7 days out. Once → `None`. |
| `Task.next_occurrence(on)` | A fresh uncompleted copy stamped with that date. |
| `Scheduler.complete_task(task, on)` | Marks it done **and** attaches the next occurrence to the same pet. Completing twice cannot stack up duplicates. |

The `starts_on` field is what makes this work: a repeat is not due before that
date. Without it, completing a daily task would immediately put an identical
copy back into *today's* plan. The completed original is kept rather than
deleted, so a pet's task list doubles as a record of what was done.

### Planning and explanation

| Method | Behavior |
|--------|----------|
| `Schedule.generate()` | Places pinned tasks first, computes the free gaps between them, then fills those gaps with flexible tasks by priority. |
| `Schedule.explain()` | The whole plan as readable text. |
| `ScheduledTask.reason` / `SkippedTask.reason` | Why each task landed where it did, or why it was left out. |

## 📸 Demo Walkthrough

Start the app with:

```bash
streamlit run app.py
```

### The interface

**Sidebar — your day.** Your name, the time your day starts, and the time it
ends. That window is the constraint everything else works against, and the
caption underneath tells you how many minutes you have. Below it, a date
picker for which day you are planning, with the weekday named underneath
(which matters for weekly tasks). Set the end before the start and it tells
you so rather than producing a nonsensical plan.

**Pets.** A form for name, species, breed and age. Added pets appear as chips
underneath, and each one becomes selectable in the task form.

**Tasks.** Appears once you have at least one pet. Pick the pet, give the task
a title, a duration and a priority, and choose whether it repeats daily,
weekly or once. Tick *"This has to happen at a specific time"* and set a time
to pin it; leave it unticked and the scheduler decides when.

**Your task list.** Three controls across the top — filter by pet, filter by
status (outstanding / completed / all), and sort by time, priority or pet.
Each row shows the task's duration, priority, recurrence and whether it is
pinned or flexible, with a **Done** button on the right.

**Conflicts.** Above the plan, either a green *"No clashing appointments
today"* or an amber warning listing each clashing pair by name.

**Today's plan.** A table of what happens when, each row carrying the reason
it was placed there. Underneath, either a green *"Everything fits"* or an
amber warning saying how many did not. Anything left out gets its own table
with the reason. An expander holds the full written explanation.

### An example workflow

1. **Set your day.** In the sidebar, set it to run 07:30 to 10:00 — a tight
   morning. The caption reads *150 minutes available*.
2. **Add two pets.** Mochi, a cat. Biscuit, a dog. Both appear as chips and
   both become options in the task form.
3. **Add a pinned task.** Mochi's insulin shot, 5 minutes, high priority,
   ticked as needing a specific time: 07:30. It must happen exactly then.
4. **Add flexible tasks.** Biscuit's morning walk (30 min, high), Mochi's
   litter box (10 min, medium), Biscuit's nail trim (25 min, low). No times —
   the scheduler decides.
5. **Add a recurring task.** Biscuit's coat brushing, 20 minutes, set to
   repeat *weekly* on Monday. It only appears on Mondays.
6. **Create a clash on purpose.** Add Biscuit's breakfast pinned to 08:00
   (10 min) and Mochi's eye drops pinned to 08:05 (15 min). They overlap.
7. **Read the warning.** An amber box appears above the plan:
   *"Biscuit and Mochi overlap: Breakfast runs 08:00-08:10 but Eye drops
   starts 08:05."* The app keeps working — it schedules the earlier task and
   lists the other as left out.
8. **Read the plan.** Insulin at 07:30 because it is pinned. Litter box at
   07:35 — a medium task landing before a high one, because the walk needs 30
   minutes and only 25 were free before breakfast. Breakfast at 08:00, pinned.
   Then the walk, then the brushing.
9. **Tick something off.** Press **Done** on a task. A toast confirms it, and
   for a daily or weekly task it tells you when the next one is due. The plan
   rebuilds, and time freed up may let a previously skipped task fit.
10. **Change the day.** Move the date picker to Tuesday. The weekly brushing
    disappears; the daily tasks remain.

### Scheduler behaviors you can see in that run

| Behavior | Where it shows up |
|---|---|
| **Sorting** | Change *Sort by* to Priority and the list reorders; the plan itself always runs in clock order |
| **Filtering** | Set *Show* to one pet, or *Status* to Completed |
| **Gap filling** | Litter box at 07:35 beating Morning walk, because the walk did not fit the 25-minute gap |
| **Conflict warning** | The amber box naming Breakfast and Eye drops |
| **Recurrence** | Pressing Done on a daily task; the toast names tomorrow's date |
| **Skipping with a reason** | *"needs 25 min but the largest free gap left is 15 min"* |
| **Explanation** | The *Why this plan?* expander below the table |

### Sample CLI output

The same logic, driven from the terminal with `python main.py`. This is the
full output of the demo script, which walks through sorting, filtering,
conflict detection, the plan, and a recurring task regenerating itself.

```
==============================================================
  PawPal+ - Today's Schedule
==============================================================
  Owner : Jordan
  Pets  : Mochi (cat), Biscuit (dog)
  Day   : Monday, October 12, 2026  (07:30-10:00, 150 min)


==============================================================
  SORTING - Scheduler.sort_by_time()
==============================================================
  As entered:
     flexible  Vet checkup
        07:30  Insulin shot
     flexible  Litter box
        08:05  Eye drops
     flexible  Nail trim
        08:00  Breakfast
     flexible  Morning walk
     flexible  Brush coat

  Sorted by time (pinned first, flexible last):
        07:30  Insulin shot
        08:00  Breakfast
        08:05  Eye drops
     flexible  Brush coat
     flexible  Litter box
     flexible  Morning walk
     flexible  Nail trim
     flexible  Vet checkup

==============================================================
  FILTERING - by pet, and by status
==============================================================
  Mochi (cat)            4 task(s)
          07:30  Insulin shot
          08:05  Eye drops
       flexible  Litter box
       flexible  Vet checkup
  Biscuit (dog)          4 task(s)
          08:00  Breakfast
       flexible  Brush coat
       flexible  Morning walk
       flexible  Nail trim

  Outstanding : 8
  Completed   : 0

==============================================================
  CONFLICTS - Scheduler.find_conflicts()
==============================================================
  1 clash(es) found. The app keeps running:
    ! Biscuit and Mochi overlap: Breakfast runs 08:00-08:10 but Eye drops starts 08:05

==============================================================
  THE PLAN - Scheduler.plan_for()
==============================================================
--------------------------------------------------------------
  TIME          TASK             PET       WHY
--------------------------------------------------------------
  07:30-07:35   Insulin shot     Mochi     pinned to 07:30
  07:35-07:45   Litter box       Mochi     medium priority, earliest free 10 min slot
  08:00-08:10   Breakfast        Biscuit   pinned to 08:00
  08:10-08:40   Morning walk     Biscuit   high priority, earliest free 30 min slot
  08:40-09:40   Vet checkup      Mochi     high priority, earliest free 60 min slot
  09:40-10:00   Brush coat       Biscuit   low priority, earliest free 20 min slot
--------------------------------------------------------------

  NOT SCHEDULED
    - Eye drops (15 min) - fixed time 08:05 overlaps Breakfast
    - Nail trim (25 min) - needs 25 min but the largest free gap left is 15 min

  6 task(s) scheduled, 2 left out.
  Using 135 of 150 minutes (15 min spare).
==============================================================

==============================================================
  RECURRING - completing a task queues the next one
==============================================================
  Added 'Evening feed' (daily).
  Outstanding copies today: 1

  Marked complete on Mon 12 Oct.
  A repeat was created, starting Tue 13 Oct.

  The completed original drops out and the repeat has not
  started yet, so today is clear -- but tomorrow is covered:
    outstanding today    : 0
    outstanding tomorrow : 1
```

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
