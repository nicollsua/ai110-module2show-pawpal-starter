"""PawPal+ logic layer.

Backend classes for the pet care planning assistant. The structure here matches
diagrams/uml.mmd one for one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum

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

    Two fields only matter for certain frequencies:
      weekday  -> WEEKLY only, 0 = Monday through 6 = Sunday
      due_date -> ONCE only, the single date this task is for
    """

    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    frequency: Frequency = Frequency.DAILY
    weekday: int | None = None
    due_date: date | None = None
    fixed_time: time | None = None
    completed: bool = False
    pet: Pet | None = None

    def mark_complete(self) -> None:
        """Mark this task done so it drops out of the remaining plan."""
        self.completed = True

    def mark_incomplete(self) -> None:
        """Undo mark_complete, for when something gets ticked off by mistake."""
        self.completed = False

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
        """
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

        Pinned tasks are placed before flexible ones even when a flexible task
        is more important. That is deliberate: medication at 8am is not
        negotiable, and a plan that quietly moves it is worse than useless.
        """
        # Streamlit re-runs the whole script on every button click, so without
        # this the plan would double each time Generate is pressed.
        self.scheduled = []
        self.skipped = []

        day_start = to_minutes(self.owner.day_start)
        day_end = to_minutes(self.owner.day_end)
        window = (
            f"{self.owner.day_start:%H:%M}-{self.owner.day_end:%H:%M}"
        )

        # Ask the Scheduler rather than reaching into pet.tasks directly, so
        # "which tasks count today" is decided in exactly one place.
        due = Scheduler(self.owner).tasks_due_on(self.day)

        pinned = sorted(
            (t for t in due if t.is_pinned()),
            key=lambda t: (to_minutes(t.fixed_time), t.title),
        )
        flexible = [t for t in due if not t.is_pinned()]

        placed: list[ScheduledTask] = []
        occupied: list[tuple[int, int, Task]] = []

        for task in pinned:
            if task.duration_minutes <= 0:
                self.skipped.append(
                    SkippedTask(task, "duration must be at least 1 minute")
                )
                continue

            start = to_minutes(task.fixed_time)
            end = start + task.duration_minutes

            if start < day_start or end > day_end:
                self.skipped.append(
                    SkippedTask(
                        task,
                        f"fixed time {task.fixed_time:%H:%M} does not fit "
                        f"inside your {window} day",
                    )
                )
                continue

            clash = next(
                (o for o in occupied if start < o[1] and o[0] < end), None
            )
            if clash is not None:
                self.skipped.append(
                    SkippedTask(
                        task,
                        f"fixed time {task.fixed_time:%H:%M} overlaps "
                        f"{clash[2].title}",
                    )
                )
                continue

            occupied.append((start, end, task))
            placed.append(
                ScheduledTask(
                    task,
                    to_time(start),
                    to_time(end),
                    f"pinned to {task.fixed_time:%H:%M}",
                )
            )

        # Whatever the pinned tasks left behind, inside the owner's window.
        gaps: list[list[int]] = []
        cursor = day_start
        for start, end, _ in sorted(occupied, key=lambda o: (o[0], o[1])):
            if start > cursor:
                gaps.append([cursor, start])
            cursor = max(cursor, end)
        if cursor < day_end:
            gaps.append([cursor, day_end])

        # Most urgent first; on a tie the shorter task goes first, which fits
        # more tasks into the day overall. Title breaks remaining ties so the
        # output is stable rather than depending on insertion order.
        flexible.sort(
            key=lambda t: (-t.priority.rank(), t.duration_minutes, t.title)
        )

        for task in flexible:
            if task.duration_minutes <= 0:
                self.skipped.append(
                    SkippedTask(task, "duration must be at least 1 minute")
                )
                continue

            gap = next(
                (g for g in gaps if g[1] - g[0] >= task.duration_minutes), None
            )
            if gap is None:
                largest = max((g[1] - g[0] for g in gaps), default=0)
                self.skipped.append(
                    SkippedTask(
                        task,
                        f"needs {task.duration_minutes} min but the largest "
                        f"free gap left is {largest} min",
                    )
                )
                continue

            start = gap[0]
            end = start + task.duration_minutes
            gap[0] = end  # shrink the gap from the front
            placed.append(
                ScheduledTask(
                    task,
                    to_time(start),
                    to_time(end),
                    f"{task.priority.value} priority, earliest free "
                    f"{task.duration_minutes} min slot",
                )
            )

        placed.sort(key=lambda s: (s.start_time, s.task.title))
        self.scheduled = placed

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
