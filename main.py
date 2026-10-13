"""Terminal demo for PawPal+.

Builds a small but realistic day -- one owner, two pets, a mix of pinned,
flexible, daily, weekly and one-off tasks -- and exercises every piece of
scheduling logic in turn: sorting, filtering, conflict detection, planning,
and recurring tasks regenerating when they are completed. Run it with:

    python main.py

This is a testing ground, not part of the app. The real UI is app.py.
"""

from datetime import date, time, timedelta

from pawpal_system import (
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
)

# A Monday, so the weekly task below is due.
TODAY = date(2026, 10, 12)
WIDTH = 62


def build_owner() -> Owner:
    """Set up one owner with two pets and eight tasks between them.

    Tasks are added deliberately out of chronological order so that
    sort_by_time() has something real to do. Two of them are pinned to
    overlapping times so conflict detection has something to find.
    """
    owner = Owner("Jordan", day_start=time(7, 30), day_end=time(10, 0))

    cat = Pet("Mochi", "cat", breed="tabby", age=3)
    dog = Pet("Biscuit", "dog", breed="golden retriever", age=5)
    owner.add_pet(cat)
    owner.add_pet(dog)

    # Added last-thing-first on purpose, to prove the sort works.
    dog.add_task(Task("Nail trim", 25, Priority.LOW))
    dog.add_task(Task("Breakfast", 10, Priority.HIGH, fixed_time=time(8, 0)))
    cat.add_task(
        Task("Vet checkup", 60, Priority.HIGH,
             frequency=Frequency.ONCE, due_date=TODAY)
    )
    cat.add_task(
        Task("Insulin shot", 5, Priority.HIGH, fixed_time=time(7, 30))
    )
    dog.add_task(Task("Morning walk", 30, Priority.HIGH))
    dog.add_task(
        Task("Brush coat", 20, Priority.LOW,
             frequency=Frequency.WEEKLY, weekday=0)
    )
    cat.add_task(Task("Litter box", 10, Priority.MEDIUM))

    # Deliberate clash with Breakfast at 08:00, for conflict detection.
    cat.add_task(Task("Eye drops", 15, Priority.HIGH, fixed_time=time(8, 5)))

    return owner


def banner(text: str) -> None:
    """Print a section heading."""
    print()
    print("=" * WIDTH)
    print(f"  {text}")
    print("=" * WIDTH)


def print_sorted(scheduler: Scheduler) -> None:
    """Show sort_by_time() putting an out-of-order list straight."""
    banner("SORTING - Scheduler.sort_by_time()")
    print("  As entered:")
    for task in scheduler.all_tasks():
        print(f"    {_when(task):>9}  {task.title}")

    print()
    print("  Sorted by time (pinned first, flexible last):")
    for task in scheduler.sort_by_time():
        print(f"    {_when(task):>9}  {task.title}")


def print_filtered(scheduler: Scheduler) -> None:
    """Show filtering by pet and by completion status."""
    banner("FILTERING - by pet, and by status")
    for pet in scheduler.owner.pets:
        tasks = scheduler.filter_by_pet(pet.name)
        print(f"  {pet.label():<22} {len(tasks)} task(s)")
        for task in scheduler.sort_by_time(tasks):
            print(f"      {_when(task):>9}  {task.title}")

    print()
    outstanding = scheduler.filter_by_status(False)
    done = scheduler.filter_by_status(True)
    print(f"  Outstanding : {len(outstanding)}")
    print(f"  Completed   : {len(done)}")


def print_conflicts(scheduler: Scheduler) -> None:
    """Show conflict detection warning rather than crashing."""
    banner("CONFLICTS - Scheduler.find_conflicts()")
    warnings = scheduler.find_conflicts(TODAY)
    if not warnings:
        print("  No clashes found.")
        return
    print(f"  {len(warnings)} clash(es) found. The app keeps running:")
    for warning in warnings:
        print(f"    ! {warning}")


def print_recurring(scheduler: Scheduler) -> None:
    """Show a daily task regenerating itself when completed."""
    banner("RECURRING - completing a task queues the next one")

    tomorrow = TODAY + timedelta(days=1)

    feeding = Task("Evening feed", 10, Priority.HIGH)
    scheduler.owner.pets[1].add_task(feeding)
    print(f"  Added '{feeding.title}' (daily).")
    print(f"  Outstanding copies today: {_count(scheduler, TODAY, feeding)}")

    repeat = scheduler.complete_task(feeding, TODAY)
    print()
    print(f"  Marked complete on {TODAY:%a %d %b}.")
    print(f"  A repeat was created, starting {repeat.starts_on:%a %d %b}.")
    print()
    print("  The completed original drops out and the repeat has not")
    print("  started yet, so today is clear -- but tomorrow is covered:")
    print(f"    outstanding today    : {_count(scheduler, TODAY, feeding)}")
    print(f"    outstanding tomorrow : {_count(scheduler, tomorrow, feeding)}")


def _count(scheduler: Scheduler, day: date, like: Task) -> int:
    """Count outstanding tasks with the same title as `like`, due on `day`."""
    return sum(
        1 for t in scheduler.tasks_due_on(day) if t.title == like.title
    )


def _when(task: Task) -> str:
    """Return a task's pinned time, or 'flexible'."""
    return f"{task.fixed_time:%H:%M}" if task.is_pinned() else "flexible"


def print_header(owner: Owner) -> None:
    """Print the owner, their pets and the day's time budget."""
    print("=" * 62)
    print("  PawPal+ - Today's Schedule")
    print("=" * 62)
    print(f"  Owner : {owner.name}")
    print(f"  Pets  : {', '.join(p.label() for p in owner.pets)}")
    print(
        f"  Day   : {TODAY:%A, %B %d, %Y}  "
        f"({owner.day_start:%H:%M}-{owner.day_end:%H:%M}, "
        f"{owner.available_minutes()} min)"
    )
    print()


def print_plan(schedule) -> None:
    """Print the scheduled tasks as an aligned table with reasons."""
    print("-" * 62)
    print(f"  {'TIME':<13} {'TASK':<16} {'PET':<9} WHY")
    print("-" * 62)
    for item in schedule.scheduled:
        when = f"{item.start_time:%H:%M}-{item.end_time:%H:%M}"
        pet = item.task.pet.name if item.task.pet else "-"
        print(f"  {when:<13} {item.task.title:<16} {pet:<9} {item.reason}")
    print("-" * 62)


def print_leftovers(schedule) -> None:
    """Print anything that did not make it into the plan, and why."""
    if not schedule.skipped:
        return
    print()
    print("  NOT SCHEDULED")
    for item in schedule.skipped:
        print(f"    - {item.describe()}")


def print_footer(schedule, owner: Owner) -> None:
    """Print how much of the day the plan uses."""
    used = schedule.total_minutes()
    available = owner.available_minutes()
    print()
    print(
        f"  {len(schedule.scheduled)} task(s) scheduled, "
        f"{len(schedule.skipped)} left out."
    )
    print(f"  Using {used} of {available} minutes "
          f"({available - used} min spare).")
    print("=" * 62)


def main() -> None:
    """Build the demo day and walk through every scheduling feature."""
    owner = build_owner()
    scheduler = Scheduler(owner)

    print_header(owner)
    print_sorted(scheduler)
    print_filtered(scheduler)
    print_conflicts(scheduler)

    banner("THE PLAN - Scheduler.plan_for()")
    schedule = scheduler.plan_for(TODAY)
    print_plan(schedule)
    print_leftovers(schedule)
    print_footer(schedule, owner)

    print_recurring(scheduler)


if __name__ == "__main__":
    main()
