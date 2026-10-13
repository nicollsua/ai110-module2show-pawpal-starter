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

Terminal output from `python main.py`. One owner, two pets, seven tasks, and a
150-minute morning. The second half shows what happens after a task is marked
complete — the freed time lets a previously skipped task fit.

```
==============================================================
  PawPal+ - Today's Schedule
==============================================================
  Owner : Jordan
  Pets  : Mochi (cat), Biscuit (dog)
  Day   : Monday, October 12, 2026  (07:30-10:00, 150 min)

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
    - Nail trim (25 min) - needs 25 min but the largest free gap left is 15 min

  6 task(s) scheduled, 1 left out.
  Using 135 of 150 minutes (15 min spare).
==============================================================

  >> Marking 'Vet checkup' complete and re-planning...

--------------------------------------------------------------
  TIME          TASK             PET       WHY
--------------------------------------------------------------
  07:30-07:35   Insulin shot     Mochi     pinned to 07:30
  07:35-07:45   Litter box       Mochi     medium priority, earliest free 10 min slot
  08:00-08:10   Breakfast        Biscuit   pinned to 08:00
  08:10-08:40   Morning walk     Biscuit   high priority, earliest free 30 min slot
  08:40-09:00   Brush coat       Biscuit   low priority, earliest free 20 min slot
  09:00-09:25   Nail trim        Biscuit   low priority, earliest free 25 min slot
--------------------------------------------------------------

  6 task(s) scheduled, 0 left out.
  Using 100 of 150 minutes (50 min spare).
==============================================================
```

Worth noticing in that output: **Litter box (medium) is scheduled before Morning
walk (high)**. That is not a priority bug. Morning walk is considered first, but
needs 30 minutes and the 07:35–08:00 gap only has 25, so it lands at 08:10.
Litter box then backfills the small gap. Higher priority wins the *choice* of
slot, not necessarily the earliest clock time.

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
........................................................................ [ 50%]
........................................................................ [100%]
144 passed in 0.16s
```

Tests live in two files:

- `test_pawpal_system.py` — the full suite (142 tests), grouped by the unit under test
- `tests/test_pawpal.py` — two quick checks for task completion and task addition

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Schedule.generate()`, `Priority.rank()` | Pinned tasks first in `fixed_time` order, then flexible tasks by priority descending, duration ascending, title. Shortest-first on a priority tie fits more tasks into the day. |
| Filtering | `Scheduler.tasks_due_on()`, `Task.is_due_on()`, `Task.mark_complete()` | Tasks are dropped before planning if they are not due today or already complete. Tasks that are due but do not fit go to `Schedule.skipped` with a reason, so nothing silently disappears. |
| Conflict handling | `Schedule.generate()` | Two pinned tasks that overlap: the earlier one wins, the later is skipped and told why. Tasks that touch exactly (09:00–10:00 and 10:00–10:30) do not count as a conflict. Anything falling outside the owner's window is skipped. |
| Recurring tasks | `Task.is_due_on()`, `Frequency` | `DAILY` is always due. `WEEKLY` matches on `weekday` (0 = Monday). `ONCE` matches on `due_date`. A recurring task missing its field returns `False` rather than defaulting to every day. |
| Gap filling | `Schedule.generate()` | Free gaps between pinned tasks are computed, then flexible tasks take the earliest gap large enough. This is why a shorter medium-priority task can land before a longer high-priority one. |
| Explanation | `Schedule.explain()`, `ScheduledTask.reason` | Every scheduled task carries the reason it landed where it did, and every skipped task carries why it was left out. |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
