"""Terminal demo for PawPal+.

Builds a small but realistic day -- one owner, two pets, a mix of pinned,
flexible, daily, weekly and one-off tasks -- and prints the plan the scheduler
produces. Run it with:

    python main.py

This is a testing ground, not part of the app. The real UI is app.py.
"""

from datetime import date, time

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


def build_owner() -> Owner:
    """Set up one owner with two pets and seven tasks between them."""
    owner = Owner("Jordan", day_start=time(7, 30), day_end=time(10, 0))

    cat = Pet("Mochi", "cat", breed="tabby", age=3)
    dog = Pet("Biscuit", "dog", breed="golden retriever", age=5)
    owner.add_pet(cat)
    owner.add_pet(dog)

    # Pinned: these have to happen at a specific time.
    cat.add_task(Task("Insulin shot", 5, Priority.HIGH, fixed_time=time(7, 30)))
    dog.add_task(Task("Breakfast", 10, Priority.HIGH, fixed_time=time(8, 0)))

    # Flexible: the scheduler decides when.
    dog.add_task(Task("Morning walk", 30, Priority.HIGH))
    cat.add_task(Task("Litter box", 10, Priority.MEDIUM))
    dog.add_task(Task("Nail trim", 25, Priority.LOW))

    # Recurring: only due on certain days.
    dog.add_task(
        Task("Brush coat", 20, Priority.LOW,
             frequency=Frequency.WEEKLY, weekday=0)
    )
    cat.add_task(
        Task("Vet checkup", 60, Priority.HIGH,
             frequency=Frequency.ONCE, due_date=TODAY)
    )

    return owner


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
    """Build the demo day, plan it, and print the result."""
    owner = build_owner()
    scheduler = Scheduler(owner)
    schedule = scheduler.plan_for(TODAY)

    print_header(owner)
    print_plan(schedule)
    print_leftovers(schedule)
    print_footer(schedule, owner)

    # Completing a task frees its time up for whatever got left out.
    print()
    print("  >> Marking 'Vet checkup' complete and re-planning...")
    print()
    for task in scheduler.all_tasks():
        if task.title == "Vet checkup":
            task.mark_complete()

    schedule = scheduler.plan_for(TODAY)
    print_plan(schedule)
    print_leftovers(schedule)
    print_footer(schedule, owner)


if __name__ == "__main__":
    main()
