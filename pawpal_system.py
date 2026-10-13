"""PawPal+ logic layer.

Backend classes for the pet care planning assistant. The structure here matches
diagrams/uml.mmd one for one.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, time, timedelta
from enum import Enum
from itertools import combinations

MINUTES_PER_DAY = 24 * 60

# --- Time helpers -----------------------------------------------------------
# datetime.time is a clock reading, not a quantity, so it has no arithmetic:
# time(8, 0) + timedelta(minutes=30) raises TypeError, and so does subtracting
# one time from another. Since the scheduler is almost entirely "how long is
# this" and "what comes next", every calculation converts to minutes past
# midnight, does plain integer math, and converts back only to display.


def to_minutes(t: time) -> int:
    """Convert a clock time to minutes past midnight. 08:30 -> 510."""
    return t.hour * 60 + t.minute


def to_time(minutes: int) -> time:
    """Convert minutes past midnight back to a clock time. 510 -> 08:30.

    Raises ValueError outside 0..1439. A value of 1440 would be "midnight
    tomorrow", which this single-day planner has no way to represent, so it
    is better to fail loudly than to silently wrap around to 00:00.
    """
    if not 0 <= minutes < MINUTES_PER_DAY:
        raise ValueError(
            f"{minutes} is outside a single day (0 to {MINUTES_PER_DAY - 1})"
        )
    return time(minutes // 60, minutes % 60)


class Priority(Enum):
    """How important a task is.

    The values match the strings the Streamlit UI already uses in its
    selectbox, so converting between the two is just Priority(value).
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    def rank(self) -> int:
        """Return a sortable number where a higher number means more urgent.

        Needed because you cannot sort enum members directly, and sorting
        alphabetically would put "high" after "low" -- exactly backwards.
        """
        return _PRIORITY_RANKS[self]


_PRIORITY_RANKS = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2}


class Frequency(Enum):
    """How often a task repeats."""

    DAILY = "daily"
    WEEKLY = "weekly"
    ONCE = "once"


@dataclass
class Pet:
    """One animal, plus the tasks that animal needs done."""

    name: str
    species: str
    breed: str = ""
    age: int = 0
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet.

        Sets both sides of the link here, in one place, so the two references
        can never disagree.
        """
        self.tasks.append(task)
        task.pet = self

    def label(self) -> str:
        """Return a display string for the UI, e.g. "Mochi (cat)"."""
        return f"{self.name} ({self.species})"


@dataclass
class Task:
    """One thing that needs to get done for a pet.

    duration_minutes is how long it takes. fixed_time is when it must happen,
    and is None for a flexible task the scheduler can place wherever it fits.
    These are two different ideas and the scheduler treats them differently.

    Three fields only matter in certain cases:
      weekday   -> WEEKLY only, 0 = Monday through 6 = Sunday
      due_date  -> ONCE only, the single date this task is for
      starts_on -> set on a repeat created by next_occurrence(); the task is
                   not due before this date, which is what stops tomorrow's
                   copy of a daily task from also being due today
    """

    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    frequency: Frequency = Frequency.DAILY
    weekday: int | None = None
    due_date: date | None = None
    starts_on: date | None = None
    fixed_time: time | None = None
    completed: bool = False
    pet: Pet | None = None

    def mark_complete(self) -> None:
        """Mark this task done so it drops out of the remaining plan."""
        self.completed = True

    def mark_incomplete(self) -> None:
        """Undo mark_complete, for a task ticked off by mistake."""
        self.completed = False

    def next_occurrence_date(self, completed_on: date) -> date | None:
        """Return the next date this task comes round again, or None.

        DAILY  -> the day after it was completed
        WEEKLY -> the next matching weekday, always at least 7 days later so
                  that finishing Monday's bath does not make it due again the
                  same Monday
        ONCE   -> None, because a one-off does not come back
        """
        if self.frequency is Frequency.DAILY:
            return completed_on + timedelta(days=1)
        if self.frequency is Frequency.WEEKLY and self.weekday is not None:
            days_ahead = (self.weekday - completed_on.weekday()) % 7
            return completed_on + timedelta(days=days_ahead or 7)
        return None

    def next_occurrence(self, completed_on: date) -> Task | None:
        """Return a fresh, uncompleted copy of this task for its next date.

        Returns None when there is no next time (a one-off, or a weekly task
        with no weekday set). The copy deliberately drops the pet link: the
        caller attaches it with Pet.add_task(), which is the only place that
        is allowed to set both sides of that relationship.
        """
        next_date = self.next_occurrence_date(completed_on)
        if next_date is None:
            return None
        return replace(
            self,
            starts_on=next_date,
            due_date=next_date if self.frequency is Frequency.ONCE else None,
            completed=False,
            pet=None,
        )

    def is_pinned(self) -> bool:
        """Return True if this task must happen at a specific time."""
        return self.fixed_time is not None

    def is_due_on(self, day: date) -> bool:
        """Return True if this task needs doing on the given day.

        DAILY  -> always True
        WEEKLY -> True only when self.weekday matches day.weekday()
        ONCE   -> True only when self.due_date equals day

        When the field a frequency depends on is missing (a WEEKLY task with
        no weekday, a ONCE task with no due_date) this returns False. Leaving
        a task out of one day's plan is a much smaller mistake than silently
        scheduling it on every day forever.

        A task with starts_on set is never due before that date. That is what
        keeps a repeat generated on completion from showing up again today.
        """
        if self.starts_on is not None and day < self.starts_on:
            return False
        if self.frequency is Frequency.DAILY:
            return True
        if self.frequency is Frequency.WEEKLY:
            return self.weekday is not None and self.weekday == day.weekday()
        if self.frequency is Frequency.ONCE:
            return self.due_date is not None and self.due_date == day
        return False


@dataclass
class Owner:
    """The person using the app.

    day_start and day_end are the constraint the whole scheduler works
    against: nothing can be planned outside this window.
    """

    name: str
    day_start: time = time(8, 0)
    day_end: time = time(20, 0)
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        self.pets.append(pet)

    def available_minutes(self) -> int:
        """Return the total minutes between day_start and day_end.

        A backwards window (end before start) gives 0 rather than a negative
        number, so the scheduler just plans nothing instead of doing something
        strange with a negative amount of time.
        """
        return max(0, to_minutes(self.day_end) - to_minutes(self.day_start))

    def all_tasks(self) -> list[Task]:
        """Return every task across every pet, flattened into one list."""
        return [task for pet in self.pets for task in pet.tasks]


@dataclass
class ScheduledTask:
    """A task that has been placed in the day at a specific time.

    Separate from Task on purpose. A Task is always true ("walk the dog, 30
    minutes, high priority"). Where it landed today is a different fact, and
    storing it here means regenerating the plan never corrupts the task list.
    """

    task: Task
    start_time: time
    end_time: time
    reason: str = ""

    def describe(self) -> str:
        """Return one display line, e.g. "08:00-08:30  Morning walk (Mochi)".

        task.pet is only set by Pet.add_task(), so a Task built directly has
        none. The pet name is left off in that case rather than crashing.
        """
        who = f" ({self.task.pet.name})" if self.task.pet is not None else ""
        return (
            f"{self.start_time:%H:%M}-{self.end_time:%H:%M}  "
            f"{self.task.title}{who}"
        )


@dataclass
class SkippedTask:
    """A task that did not make it into the plan, and why.

    The mirror image of ScheduledTask. Storing these as (task, reason) tuples
    would work, but reading schedule.skipped[0][1] tells you nothing about
    what you are looking at, where skipped[0].reason explains itself.
    """

    task: Task
    reason: str

    def describe(self) -> str:
        """Return one display line, e.g. "Grooming (45 min) - no gap left"."""
        return (
            f"{self.task.title} ({self.task.duration_minutes} min) "
            f"- {self.reason}"
        )


@dataclass
class _Block:
    """A stretch of the day already taken by a pinned task.

    Start and end are minutes past midnight, because that is the only form
    the arithmetic works in. Internal to Schedule.generate().
    """

    start: int
    end: int
    task: Task

    def overlaps(self, start: int, end: int) -> bool:
        """Return True if this block shares any minute with start..end.

        Touching exactly does not count: a block ending at 10:00 and a task
        starting at 10:00 are back to back, not in conflict.
        """
        return start < self.end and self.start < end


@dataclass
class _Gap:
    """A stretch of free time left between pinned tasks.

    Mutable on purpose: filling a gap shrinks it from the front, so the next
    task sees what is actually left. Internal to Schedule.generate().
    """

    start: int
    end: int

    @property
    def length(self) -> int:
        """Return how many minutes long this gap is."""
        return self.end - self.start

    def fits(self, minutes: int) -> bool:
        """Return True if a task of this length would fit here."""
        return self.length >= minutes

    def take(self, minutes: int) -> int:
        """Claim the front of this gap and return the minute it starts at."""
        start = self.start
        self.start += minutes
        return start


@dataclass
class Schedule:
    """The plan for one day, and the logic that builds it.

    Belongs to the Owner rather than a Pet: with two pets you still only get
    one day, so everything has to fit inside the owner's single time window.
    """

    owner: Owner
    day: date
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: list[SkippedTask] = field(default_factory=list)

    def generate(self) -> None:
        """Build the plan, filling in self.scheduled and self.skipped.

        Four steps: work out what is due, put the pinned tasks at their fixed
        times, see what gaps that leaves, and fill those gaps with everything
        else. Each step has its own method below.

        Pinned tasks are placed before flexible ones even when a flexible task
        is more important. That is deliberate: medication at 8am is not
        negotiable, and a plan that quietly moves it is worse than useless.
        """
        # Streamlit re-runs the whole script on every button click, so without
        # this the plan would double each time Generate is pressed.
        self.scheduled = []
        self.skipped = []

        # Ask the Scheduler rather than reaching into pet.tasks directly, so
        # "which tasks count today" is decided in exactly one place.
        pinned, flexible = self._split(
            Scheduler(self.owner).tasks_due_on(self.day)
        )

        placed, blocks = self._place_pinned(pinned)
        placed += self._fill_gaps(flexible, self._free_gaps(blocks))

        placed.sort(key=lambda s: (s.start_time, s.task.title))
        self.scheduled = placed

    def _split(self, due: list[Task]) -> tuple[list[Task], list[Task]]:
        """Separate today's tasks into pinned and flexible, each in order.

        Pinned go in clock order, since they are placed as they come.
        Flexible go most urgent first, then shortest first on a tie, which
        fits more tasks into the day overall. Title breaks any remaining tie
        so the plan is stable rather than depending on insertion order.
        """
        pinned = sorted(
            (t for t in due if t.is_pinned()),
            key=lambda t: (to_minutes(t.fixed_time), t.title),
        )
        flexible = sorted(
            (t for t in due if not t.is_pinned()),
            key=lambda t: (-t.priority.rank(), t.duration_minutes, t.title),
        )
        return pinned, flexible

    def _place_pinned(
        self, pinned: list[Task]
    ) -> tuple[list[ScheduledTask], list[_Block]]:
        """Put each pinned task at its fixed time, or skip it with a reason.

        Returns what was placed, and the blocks of the day they now occupy.
        """
        placed: list[ScheduledTask] = []
        blocks: list[_Block] = []

        for task in pinned:
            start = to_minutes(task.fixed_time)
            end = start + task.duration_minutes

            refusal = self._why_pinned_cannot_fit(task, start, end, blocks)
            if refusal is not None:
                self.skipped.append(SkippedTask(task, refusal))
                continue

            blocks.append(_Block(start, end, task))
            placed.append(
                ScheduledTask(
                    task,
                    to_time(start),
                    to_time(end),
                    f"pinned to {task.fixed_time:%H:%M}",
                )
            )

        return placed, blocks

    def _why_pinned_cannot_fit(
        self, task: Task, start: int, end: int, blocks: list[_Block]
    ) -> str | None:
        """Return why a pinned task cannot be placed, or None if it can.

        Gathering the three refusals in one place keeps _place_pinned() to
        the shape of the thing it does, rather than burying it in checks.
        """
        if task.duration_minutes <= 0:
            return "duration must be at least 1 minute"

        if start < to_minutes(self.owner.day_start):
            return (
                f"fixed time {task.fixed_time:%H:%M} is before your "
                f"{self._window()} day starts"
            )

        if end > to_minutes(self.owner.day_end):
            return (
                f"fixed time {task.fixed_time:%H:%M} does not fit inside "
                f"your {self._window()} day"
            )

        clash = next((b for b in blocks if b.overlaps(start, end)), None)
        if clash is not None:
            return (
                f"fixed time {task.fixed_time:%H:%M} overlaps "
                f"{clash.task.title}"
            )

        return None

    def _free_gaps(self, blocks: list[_Block]) -> list[_Gap]:
        """Return the stretches of the owner's day the pinned tasks left.

        Walks a cursor through the day, and every time a block starts later
        than the cursor, the space between them is free.
        """
        day_end = to_minutes(self.owner.day_end)
        gaps: list[_Gap] = []
        cursor = to_minutes(self.owner.day_start)

        for block in sorted(blocks, key=lambda b: (b.start, b.end)):
            if block.start > cursor:
                gaps.append(_Gap(cursor, block.start))
            cursor = max(cursor, block.end)

        if cursor < day_end:
            gaps.append(_Gap(cursor, day_end))

        return gaps

    def _fill_gaps(
        self, flexible: list[Task], gaps: list[_Gap]
    ) -> list[ScheduledTask]:
        """Drop each flexible task into the earliest gap large enough.

        Greedy and single-pass: a task that does not fit anywhere is skipped
        rather than triggering a rearrangement of what is already placed.
        """
        placed: list[ScheduledTask] = []

        for task in flexible:
            if task.duration_minutes <= 0:
                self.skipped.append(
                    SkippedTask(task, "duration must be at least 1 minute")
                )
                continue

            gap = next(
                (g for g in gaps if g.fits(task.duration_minutes)), None
            )
            if gap is None:
                largest = max((g.length for g in gaps), default=0)
                self.skipped.append(
                    SkippedTask(
                        task,
                        f"needs {task.duration_minutes} min but the largest "
                        f"free gap left is {largest} min",
                    )
                )
                continue

            start = gap.take(task.duration_minutes)
            placed.append(
                ScheduledTask(
                    task,
                    to_time(start),
                    to_time(start + task.duration_minutes),
                    f"{task.priority.value} priority, earliest free "
                    f"{task.duration_minutes} min slot",
                )
            )

        return placed

    def _window(self) -> str:
        """Return the owner's day as a display string, e.g. "08:00-20:00"."""
        return f"{self.owner.day_start:%H:%M}-{self.owner.day_end:%H:%M}"

    def explain(self) -> str:
        """Return human-readable text explaining the plan."""
        available = self.owner.available_minutes()
        lines = [
            f"Plan for {self.owner.name} on {self.day:%A, %B %d, %Y}",
            f"Day runs {self.owner.day_start:%H:%M} to "
            f"{self.owner.day_end:%H:%M} ({available} minutes available).",
            "",
        ]

        if self.scheduled:
            lines.append("Scheduled:")
            for item in self.scheduled:
                lines.append(f"  {item.describe()}  - {item.reason}")
        else:
            lines.append("Nothing scheduled.")

        if self.skipped:
            lines.append("")
            lines.append("Left out:")
            for item in self.skipped:
                lines.append(f"  {item.describe()}")

        lines.append("")
        lines.append(
            f"Using {self.total_minutes()} of {available} minutes "
            f"across {len(self.scheduled)} task(s)."
        )
        return "\n".join(lines)

    def total_minutes(self) -> int:
        """Return how many minutes of the day the plan actually uses."""
        return sum(item.task.duration_minutes for item in self.scheduled)


@dataclass
class Scheduler:
    """The brain: retrieves tasks across all of an owner's pets and plans them.

    Deliberately separate from Schedule. A Schedule is one day's answer --
    a fixed list of placements you can hand to the UI. The Scheduler is the
    thing that goes and gets the tasks and decides what counts, and it can
    produce as many Schedules as you ask it for without holding any of them.

    How it reaches pet data: it never touches pet.tasks directly. It asks
    Owner.all_tasks(), which flattens every pet's list into one. That keeps
    the Owner in charge of its own pets, so adding a pet or changing how
    pets store tasks needs no change here.
    """

    owner: Owner

    def all_tasks(self) -> list[Task]:
        """Return every task across every pet, done or not."""
        return self.owner.all_tasks()

    def pending_tasks(self) -> list[Task]:
        """Return every task that has not been marked complete."""
        return [t for t in self.all_tasks() if not t.completed]

    def completed_tasks(self) -> list[Task]:
        """Return every task already marked complete."""
        return [t for t in self.all_tasks() if t.completed]

    def tasks_due_on(self, day: date) -> list[Task]:
        """Return the tasks that still need doing on the given day."""
        return [t for t in self.pending_tasks() if t.is_due_on(day)]

    def tasks_for_pet(self, pet: Pet) -> list[Task]:
        """Return the tasks belonging to one specific pet."""
        return [t for t in self.all_tasks() if t.pet is pet]

    def plan_for(self, day: date) -> Schedule:
        """Build and return a finished Schedule for the given day."""
        schedule = Schedule(self.owner, day)
        schedule.generate()
        return schedule

    # --- Sorting ------------------------------------------------------------

    def sort_by_time(self, tasks: list[Task] | None = None) -> list[Task]:
        """Return tasks ordered by their fixed time, flexible ones last.

        Sorts a copy rather than in place, so the pets' own task lists keep
        whatever order they were entered in.

        The key is a tuple. Its first element is the boolean
        `fixed_time is None`, and since False sorts before True that puts
        every pinned task ahead of every flexible one. Its second element is
        the time itself, which orders the pinned group. Flexible tasks all
        share time.min for that slot, so the third element, the title, keeps
        them in a predictable order instead of an arbitrary one.
        """
        return sorted(
            self.all_tasks() if tasks is None else tasks,
            key=lambda t: (t.fixed_time is None,
                           t.fixed_time or time.min,
                           t.title),
        )

    def sort_by_priority(self, tasks: list[Task] | None = None) -> list[Task]:
        """Return tasks ordered most urgent first, then shortest first."""
        return sorted(
            self.all_tasks() if tasks is None else tasks,
            key=lambda t: (-t.priority.rank(), t.duration_minutes, t.title),
        )

    # --- Filtering ----------------------------------------------------------

    def filter_by_status(self, completed: bool) -> list[Task]:
        """Return tasks that are done (True) or still outstanding (False)."""
        return [t for t in self.all_tasks() if t.completed is completed]

    def filter_by_pet(self, pet_name: str) -> list[Task]:
        """Return tasks belonging to the pet with this name.

        Matched case-insensitively on the name alone, so "mochi" works as
        well as "Mochi". Returns an empty list for an unknown name rather
        than raising, because this is driven by user input.
        """
        wanted = pet_name.strip().lower()
        return [
            t for t in self.all_tasks()
            if t.pet is not None and t.pet.name.lower() == wanted
        ]

    def filter_by_priority(self, priority: Priority) -> list[Task]:
        """Return tasks at exactly this priority level."""
        return [t for t in self.all_tasks() if t.priority is priority]

    # --- Completing, with automatic repeats ---------------------------------

    def complete_task(self, task: Task, on: date) -> Task | None:
        """Mark a task done and queue up its next occurrence.

        Returns the newly created repeat, or None for a one-off task that
        does not come back. The completed original is kept rather than
        deleted, so the pet's list doubles as a record of what was done.

        An already-completed task is left alone and returns None, so
        clicking twice cannot stack up duplicate repeats.
        """
        if task.completed:
            return None

        task.mark_complete()
        repeat = task.next_occurrence(on)
        if repeat is not None and task.pet is not None:
            task.pet.add_task(repeat)
        return repeat

    # --- Conflict detection -------------------------------------------------

    def find_conflicts(self, day: date) -> list[str]:
        """Return a warning per pair of pinned tasks that overlap on `day`.

        Deliberately lightweight: it reports, it never raises and never
        changes anything. The caller decides whether to show the warnings,
        so a clash is something the owner is told about rather than
        something that stops the app.

        Only pinned tasks can conflict. A flexible task has no fixed time
        yet, so the scheduler will simply place it somewhere free.
        """
        pinned = self.sort_by_time(
            [t for t in self.tasks_due_on(day) if t.is_pinned()]
        )
        return [
            f"{_who(first)} and {_who(second)} overlap: "
            f"{first.title} runs "
            f"{first.fixed_time:%H:%M}-{_end_of(first):%H:%M} "
            f"but {second.title} starts {second.fixed_time:%H:%M}"
            for first, second in combinations(pinned, 2)
            if _overlaps(first, second)
        ]

    def has_conflicts(self, day: date) -> bool:
        """Return True if any two pinned tasks clash on the given day."""
        return bool(self.find_conflicts(day))


def _end_of(task: Task) -> time:
    """Return the clock time a pinned task finishes at."""
    return to_time(to_minutes(task.fixed_time) + task.duration_minutes)


def _who(task: Task) -> str:
    """Return the pet name a task belongs to, for a warning message."""
    return task.pet.name if task.pet is not None else "An unassigned task"


def _overlaps(first: Task, second: Task) -> bool:
    """Return True if two pinned tasks share any minute of the day.

    Touching exactly does not count: a task ending at 10:00 and another
    starting at 10:00 are back to back, not in conflict.
    """
    first_start = to_minutes(first.fixed_time)
    second_start = to_minutes(second.fixed_time)
    return (
        first_start < second_start + second.duration_minutes
        and second_start < first_start + first.duration_minutes
    )
