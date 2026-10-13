"""PawPal+ logic layer.

Backend classes for the pet care planning assistant. This is a skeleton: the
structure and method signatures come straight from diagrams/uml.mmd, but none
of the methods are implemented yet.

Every stub raises NotImplementedError on purpose. A stub that quietly returned
None would let a broken scheduler look like it "worked" and just produced an
empty plan, which is much harder to debug than a loud crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum


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
        alphabetically would put "high" after "low" — exactly backwards.
        """
        raise NotImplementedError


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

        Should append to self.tasks AND set task.pet = self. Doing both in one
        place is the whole point: the two references can never disagree if
        this is the only code that writes them.
        """
        raise NotImplementedError

    def label(self) -> str:
        """Return a display string for the UI, e.g. "Mochi (cat)"."""
        raise NotImplementedError


@dataclass
class Task:
    """One thing that needs to get done for a pet.

    duration_minutes is how long it takes. fixed_time is when it must happen,
    and is None for a flexible task the scheduler can place wherever it fits.
    These are two different ideas and the scheduler treats them differently.
    """

    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    frequency: Frequency = Frequency.DAILY
    weekday: int | None = None
    fixed_time: time | None = None
    pet: Pet | None = None

    def is_pinned(self) -> bool:
        """Return True if this task must happen at a specific time."""
        raise NotImplementedError

    def is_due_on(self, day: date) -> bool:
        """Return True if this task needs doing on the given day.

        DAILY  -> always True
        WEEKLY -> True only when self.weekday matches day.weekday()
        ONCE   -> True (a one-off is assumed to be for the day being planned)
        """
        raise NotImplementedError


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
        raise NotImplementedError

    def available_minutes(self) -> int:
        """Return the total minutes between day_start and day_end."""
        raise NotImplementedError

    def all_tasks(self) -> list[Task]:
        """Return every task across every pet, flattened into one list."""
        raise NotImplementedError


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
        """Return one display line, e.g. "08:00-08:30  Morning walk (Mochi)"."""
        raise NotImplementedError


@dataclass
class Schedule:
    """The plan for one day, and the logic that builds it.

    Belongs to the Owner rather than a Pet: with two pets you still only get
    one day, so everything has to fit inside the owner's single time window.
    """

    owner: Owner
    day: date
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: list[tuple[Task, str]] = field(default_factory=list)

    def generate(self) -> None:
        """Build the plan, filling in self.scheduled and self.skipped.

        The algorithm:
          1. Collect every task across all of the owner's pets.
          2. Drop the ones not due today (Task.is_due_on).
          3. Split into pinned (fixed_time set) and flexible.
          4. Place pinned tasks first, in fixed_time order. Skip one if it
             falls outside the owner's window or overlaps a pinned task
             already placed, recording why.
          5. Work out the free gaps left between the placed pinned tasks.
          6. Sort flexible tasks by priority descending, then duration
             ascending. Shortest-first on ties fits more tasks overall.
          7. Put each flexible task in the earliest gap big enough, shrinking
             that gap. If none fits, skip it and record why.
          8. Sort the finished list by start time.

        Pinned beats flexible even when the flexible task is more important.
        That is deliberate — medication at 8am is not negotiable.
        """
        raise NotImplementedError

    def explain(self) -> str:
        """Return human-readable text explaining the plan.

        Should cover why each task landed where it did, and why anything in
        self.skipped was left out.
        """
        raise NotImplementedError

    def total_minutes(self) -> int:
        """Return how many minutes of the day the plan actually uses."""
        raise NotImplementedError
