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

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
$ python -m pytest -q
........................................................................ [ 21%]
........................................................................ [ 42%]
........................................................................ [ 64%]
........................................................................ [ 85%]
...............................................                          [100%]
335 passed in 5.88s
```

Tests live in four files:

| File | Tests | Covers |
|------|-------|--------|
| `test_pawpal_system.py` | 226 | The logic layer — sorting, filtering, conflicts, recurrence, completion, edge cases |
| `test_app.py` | 77 | The Streamlit glue — session state, form handling, table rows |
| `test_ui.py` | 30 | The real app, driven through Streamlit's `AppTest` harness |
| `tests/test_pawpal.py` | 2 | Quick checks for task completion and task addition |

`test_ui.py` runs `app.py` the same way `streamlit run` does, with real session
state and real reruns. It is the only layer that can catch a broken wire-up —
a button calling the wrong method, or an `Owner` being rebuilt empty on every
click.

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

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
