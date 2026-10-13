"""Automated test suite for the PawPal+ scheduler.

Covers the behaviors a pet owner actually depends on: that tasks come back in
the right order, that a daily task comes back tomorrow once it is done, and
that two appointments at the same time get flagged instead of silently
colliding.

Organised happy path first, then the edge cases, so a reader can see what is
meant to work before seeing what it does when pushed.

This file overlaps on purpose with test_pawpal_system.py at the project root.
That one is exhaustive and grouped by method; this one is grouped by
behaviour and is meant to be readable top to bottom as a description of what
the system guarantees.
"""

from datetime import date, time, timedelta

import pytest

from pawpal_system import (
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
)

# Real weekdays, so weekday() is not a guess.
MONDAY = date(2026, 10, 12)
TUESDAY = date(2026, 10, 13)
SUNDAY = date(2026, 10, 18)
NEXT_MONDAY = MONDAY + timedelta(days=7)


@pytest.fixture
def owner():
    """An owner with a full working day and one cat."""
    o = Owner("Jordan", day_start=time(8, 0), day_end=time(20, 0))
    o.add_pet(Pet("Mochi", "cat"))
    return o


@pytest.fixture
def pet(owner):
    """The cat from the owner fixture."""
    return owner.pets[0]


@pytest.fixture
def two_pets():
    """An owner with a cat and a dog, for cross-pet cases."""
    o = Owner("Jordan", day_start=time(8, 0), day_end=time(20, 0))
    o.add_pet(Pet("Mochi", "cat"))
    o.add_pet(Pet("Biscuit", "dog"))
    return o


def titles(tasks):
    """Task titles, in the order given."""
    return [t.title for t in tasks]


# ===========================================================================
# 1. Task completion and task addition
# ===========================================================================


def test_mark_complete_changes_the_status():
    """Task Completion: mark_complete() actually flips completed to True."""
    task = Task("Morning walk", 30)
    assert task.completed is False

    task.mark_complete()

    assert task.completed is True


def test_adding_a_task_increases_the_pets_task_count():
    """Task Addition: adding a task to a Pet grows that pet's task list."""
    pet = Pet("Mochi", "cat")
    assert len(pet.tasks) == 0

    pet.add_task(Task("Litter box", 10))

    assert len(pet.tasks) == 1

    pet.add_task(Task("Feed", 5))

    assert len(pet.tasks) == 2


# ===========================================================================
# 2. Sorting correctness
# ===========================================================================


class TestSortingHappyPath:
    def test_tasks_come_back_in_chronological_order(self, owner, pet):
        for title, when in [
            ("Dinner", time(18, 0)),
            ("Breakfast", time(8, 0)),
            ("Lunch", time(12, 30)),
        ]:
            pet.add_task(Task(title, 15, fixed_time=when))

        assert titles(Scheduler(owner).sort_by_time()) == [
            "Breakfast", "Lunch", "Dinner",
        ]

    def test_minutes_are_compared_not_just_hours(self, owner, pet):
        pet.add_task(Task("Later", 5, fixed_time=time(8, 45)))
        pet.add_task(Task("Earlier", 5, fixed_time=time(8, 5)))

        assert titles(Scheduler(owner).sort_by_time()) == ["Earlier", "Later"]

    def test_single_digit_hours_sort_before_double_digit(self, owner, pet):
        # The trap in sorting "HH:MM" as plain text: "9:00" > "10:00"
        # character by character, because "9" > "1". Comparing time objects
        # avoids it entirely.
        pet.add_task(Task("Ten", 5, fixed_time=time(10, 0)))
        pet.add_task(Task("Nine", 5, fixed_time=time(9, 0)))

        assert titles(Scheduler(owner).sort_by_time()) == ["Nine", "Ten"]

    def test_flexible_tasks_come_after_every_pinned_one(self, owner, pet):
        pet.add_task(Task("Flexible", 30))
        pet.add_task(Task("Late but pinned", 10, fixed_time=time(23, 0)))

        assert titles(Scheduler(owner).sort_by_time()) == [
            "Late but pinned", "Flexible",
        ]


class TestSortingEdgeCases:
    def test_an_owner_with_no_pets_sorts_to_an_empty_list(self):
        assert Scheduler(Owner("Jordan")).sort_by_time() == []

    def test_a_pet_with_no_tasks_sorts_to_an_empty_list(self, owner):
        assert Scheduler(owner).sort_by_time() == []

    def test_a_single_task_sorts_to_itself(self, owner, pet):
        pet.add_task(Task("Only one", 30, fixed_time=time(9, 0)))
        assert titles(Scheduler(owner).sort_by_time()) == ["Only one"]

    def test_all_flexible_tasks_are_ordered_predictably(self, owner, pet):
        # With no times to compare, the order must still be stable rather
        # than whatever order they happened to be entered in.
        for title in ["Zebra", "Apple", "Mango"]:
            pet.add_task(Task(title, 10))

        assert titles(Scheduler(owner).sort_by_time()) == [
            "Apple", "Mango", "Zebra",
        ]

    def test_tasks_at_identical_times_both_survive_the_sort(self, owner, pet):
        pet.add_task(Task("B", 15, fixed_time=time(9, 0)))
        pet.add_task(Task("A", 15, fixed_time=time(9, 0)))

        assert titles(Scheduler(owner).sort_by_time()) == ["A", "B"]

    def test_midnight_sorts_first_rather_than_counting_as_unset(
        self, owner, pet
    ):
        # time(0, 0) is falsy. A check like `if task.fixed_time:` would treat
        # a midnight task as having no time at all and bury it at the end.
        pet.add_task(Task("Dawn", 5, fixed_time=time(6, 0)))
        pet.add_task(Task("Midnight", 5, fixed_time=time(0, 0)))

        assert titles(Scheduler(owner).sort_by_time())[0] == "Midnight"

    def test_the_last_minute_of_the_day_sorts_last(self, owner, pet):
        pet.add_task(Task("Almost midnight", 1, fixed_time=time(23, 59)))
        pet.add_task(Task("Noon", 30, fixed_time=time(12, 0)))

        assert titles(Scheduler(owner).sort_by_time())[-1] == (
            "Almost midnight"
        )

    def test_sorting_does_not_reorder_the_pets_own_list(self, owner, pet):
        pet.add_task(Task("Dinner", 15, fixed_time=time(18, 0)))
        pet.add_task(Task("Breakfast", 15, fixed_time=time(8, 0)))

        Scheduler(owner).sort_by_time()

        assert titles(pet.tasks) == ["Dinner", "Breakfast"]

    def test_sorting_gathers_tasks_from_every_pet(self, two_pets):
        cat, dog = two_pets.pets
        cat.add_task(Task("Litter", 10, fixed_time=time(9, 0)))
        dog.add_task(Task("Walk", 30, fixed_time=time(8, 0)))

        assert titles(Scheduler(two_pets).sort_by_time()) == ["Walk", "Litter"]


# ===========================================================================
# 3. Recurrence logic
# ===========================================================================


class TestRecurrenceHappyPath:
    def test_completing_a_daily_task_creates_one_for_tomorrow(
        self, owner, pet
    ):
        pet.add_task(Task("Evening feed", 10, frequency=Frequency.DAILY))
        scheduler = Scheduler(owner)

        repeat = scheduler.complete_task(pet.tasks[0], MONDAY)

        assert repeat is not None
        assert repeat.title == "Evening feed"
        assert repeat.starts_on == TUESDAY

    def test_the_repeat_is_attached_to_the_same_pet(self, owner, pet):
        pet.add_task(Task("Evening feed", 10))

        repeat = Scheduler(owner).complete_task(pet.tasks[0], MONDAY)

        assert repeat.pet is pet
        assert repeat in pet.tasks

    def test_the_repeat_starts_out_incomplete(self, owner, pet):
        pet.add_task(Task("Evening feed", 10))

        repeat = Scheduler(owner).complete_task(pet.tasks[0], MONDAY)

        assert repeat.completed is False

    def test_the_repeat_is_not_due_today_but_is_due_tomorrow(
        self, owner, pet
    ):
        # Without this the completed task would be replaced by an identical
        # one in the very same day's plan, and the owner would be told to
        # feed the cat twice.
        pet.add_task(Task("Evening feed", 10))
        scheduler = Scheduler(owner)

        scheduler.complete_task(pet.tasks[0], MONDAY)

        assert titles(scheduler.tasks_due_on(MONDAY)) == []
        assert titles(scheduler.tasks_due_on(TUESDAY)) == ["Evening feed"]

    def test_the_repeat_keeps_the_original_details(self, owner, pet):
        pet.add_task(
            Task("Insulin", 5, Priority.HIGH, fixed_time=time(7, 30))
        )

        repeat = Scheduler(owner).complete_task(pet.tasks[0], MONDAY)

        assert repeat.duration_minutes == 5
        assert repeat.priority is Priority.HIGH
        assert repeat.fixed_time == time(7, 30)

    def test_a_weekly_task_comes_back_next_week(self, owner, pet):
        pet.add_task(
            Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=0)
        )

        repeat = Scheduler(owner).complete_task(pet.tasks[0], MONDAY)

        assert repeat.starts_on == NEXT_MONDAY


class TestRecurrenceEdgeCases:
    def test_a_daily_task_rolls_over_the_end_of_a_month(self, owner, pet):
        pet.add_task(Task("Feed", 10))

        repeat = Scheduler(owner).complete_task(
            pet.tasks[0], date(2026, 10, 31)
        )

        assert repeat.starts_on == date(2026, 11, 1)

    def test_a_daily_task_rolls_over_the_end_of_a_year(self, owner, pet):
        pet.add_task(Task("Feed", 10))

        repeat = Scheduler(owner).complete_task(
            pet.tasks[0], date(2026, 12, 31)
        )

        assert repeat.starts_on == date(2027, 1, 1)

    def test_a_daily_task_handles_a_leap_day(self, owner, pet):
        # 2028 is a leap year, so the 28th is followed by the 29th, not
        # March 1st. timedelta knows this; naive date arithmetic might not.
        pet.add_task(Task("Feed", 10))

        repeat = Scheduler(owner).complete_task(
            pet.tasks[0], date(2028, 2, 28)
        )

        assert repeat.starts_on == date(2028, 2, 29)

    def test_a_leap_day_task_rolls_into_march(self, owner, pet):
        pet.add_task(Task("Feed", 10))

        repeat = Scheduler(owner).complete_task(
            pet.tasks[0], date(2028, 2, 29)
        )

        assert repeat.starts_on == date(2028, 3, 1)

    def test_a_weekly_task_finished_on_its_own_day_waits_a_full_week(
        self, owner, pet
    ):
        # The obvious bug here is (target - today) % 7 giving 0, which would
        # make Monday's bath due again on Monday, immediately.
        pet.add_task(Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=0))
        scheduler = Scheduler(owner)

        repeat = scheduler.complete_task(pet.tasks[0], MONDAY)

        assert repeat.starts_on == NEXT_MONDAY
        assert titles(scheduler.tasks_due_on(MONDAY)) == []

    def test_a_weekly_task_finished_early_waits_only_until_its_day(
        self, owner, pet
    ):
        pet.add_task(Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=6))

        repeat = Scheduler(owner).complete_task(pet.tasks[0], MONDAY)

        assert repeat.starts_on == SUNDAY

    @pytest.mark.parametrize("weekday", range(7))
    def test_a_weekly_repeat_always_lands_in_the_future_on_the_right_day(
        self, owner, pet, weekday
    ):
        pet.add_task(
            Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=weekday)
        )

        repeat = Scheduler(owner).complete_task(pet.tasks[0], MONDAY)

        assert repeat.starts_on > MONDAY
        assert repeat.starts_on.weekday() == weekday

    def test_a_one_off_task_does_not_come_back(self, owner, pet):
        pet.add_task(
            Task("Vet visit", 60, frequency=Frequency.ONCE, due_date=MONDAY)
        )

        repeat = Scheduler(owner).complete_task(pet.tasks[0], MONDAY)

        assert repeat is None
        assert len(pet.tasks) == 1

    def test_completing_twice_does_not_stack_up_duplicates(self, owner, pet):
        # A double click in the UI must not quietly create two copies.
        pet.add_task(Task("Feed", 10))
        scheduler = Scheduler(owner)
        task = pet.tasks[0]

        scheduler.complete_task(task, MONDAY)
        second = scheduler.complete_task(task, MONDAY)

        assert second is None
        assert len(pet.tasks) == 2

    def test_the_completed_original_is_kept_as_a_record(self, owner, pet):
        pet.add_task(Task("Feed", 10))
        scheduler = Scheduler(owner)

        scheduler.complete_task(pet.tasks[0], MONDAY)

        assert titles(scheduler.filter_by_status(True)) == ["Feed"]

    def test_a_week_of_completions_leaves_exactly_one_task_due_each_day(
        self, owner, pet
    ):
        # The real test of the whole mechanism: run it forward seven days and
        # check it neither duplicates nor loses the task.
        pet.add_task(Task("Feed", 10))
        scheduler = Scheduler(owner)

        day = MONDAY
        for _ in range(7):
            due = scheduler.tasks_due_on(day)
            assert len(due) == 1, f"expected one task due on {day}, got {due}"
            scheduler.complete_task(due[0], day)
            day += timedelta(days=1)

        assert len(scheduler.filter_by_status(True)) == 7

    def test_a_weekly_task_with_no_weekday_set_never_repeats(
        self, owner, pet
    ):
        pet.add_task(Task("Bath", 30, frequency=Frequency.WEEKLY))

        assert Scheduler(owner).complete_task(pet.tasks[0], MONDAY) is None


# ===========================================================================
# 4. Conflict detection
# ===========================================================================


class TestConflictHappyPath:
    def test_two_tasks_at_the_exact_same_time_are_flagged(self, owner, pet):
        pet.add_task(Task("Insulin", 15, fixed_time=time(8, 0)))
        pet.add_task(Task("Eye drops", 15, fixed_time=time(8, 0)))

        assert len(Scheduler(owner).find_conflicts(MONDAY)) == 1

    def test_overlapping_tasks_are_flagged(self, owner, pet):
        pet.add_task(Task("Long walk", 60, fixed_time=time(8, 0)))
        pet.add_task(Task("Grooming", 30, fixed_time=time(8, 30)))

        assert Scheduler(owner).has_conflicts(MONDAY) is True

    def test_a_clear_schedule_reports_no_conflicts(self, owner, pet):
        pet.add_task(Task("Breakfast", 30, fixed_time=time(8, 0)))
        pet.add_task(Task("Lunch", 30, fixed_time=time(12, 0)))

        assert Scheduler(owner).find_conflicts(MONDAY) == []

    def test_the_warning_names_both_tasks_and_the_pet(self, owner, pet):
        pet.add_task(Task("Insulin", 15, fixed_time=time(8, 0)))
        pet.add_task(Task("Eye drops", 15, fixed_time=time(8, 0)))

        warning = Scheduler(owner).find_conflicts(MONDAY)[0]

        assert "Insulin" in warning
        assert "Eye drops" in warning
        assert "Mochi" in warning

    def test_detection_returns_a_warning_rather_than_raising(
        self, owner, pet
    ):
        pet.add_task(Task("A", 60, fixed_time=time(8, 0)))
        pet.add_task(Task("B", 60, fixed_time=time(8, 0)))

        result = Scheduler(owner).find_conflicts(MONDAY)

        assert isinstance(result, list)
        assert all(isinstance(w, str) for w in result)


class TestConflictEdgeCases:
    def test_tasks_that_touch_exactly_are_not_a_conflict(self, owner, pet):
        # 08:00-09:00 followed by 09:00-09:30 is back to back, not a clash.
        pet.add_task(Task("First", 60, fixed_time=time(8, 0)))
        pet.add_task(Task("Second", 30, fixed_time=time(9, 0)))

        assert Scheduler(owner).find_conflicts(MONDAY) == []

    def test_one_minute_of_overlap_is_a_conflict(self, owner, pet):
        pet.add_task(Task("First", 60, fixed_time=time(8, 0)))
        pet.add_task(Task("Second", 30, fixed_time=time(8, 59)))

        assert len(Scheduler(owner).find_conflicts(MONDAY)) == 1

    def test_conflicts_between_different_pets_are_still_reported(
        self, two_pets
    ):
        # Two pets, but still only one owner with one pair of hands.
        cat, dog = two_pets.pets
        cat.add_task(Task("Insulin", 30, fixed_time=time(8, 0)))
        dog.add_task(Task("Walk", 30, fixed_time=time(8, 15)))

        warning = Scheduler(two_pets).find_conflicts(MONDAY)[0]

        assert "Mochi" in warning
        assert "Biscuit" in warning

    def test_flexible_tasks_never_conflict(self, owner, pet):
        # They have no fixed time yet, so the scheduler simply places them
        # in different gaps.
        pet.add_task(Task("A", 120))
        pet.add_task(Task("B", 120))

        assert Scheduler(owner).find_conflicts(MONDAY) == []

    def test_a_flexible_task_does_not_conflict_with_a_pinned_one(
        self, owner, pet
    ):
        pet.add_task(Task("Pinned", 60, fixed_time=time(8, 0)))
        pet.add_task(Task("Flexible", 60))

        assert Scheduler(owner).find_conflicts(MONDAY) == []

    def test_each_clashing_pair_is_reported_exactly_once(self, owner, pet):
        pet.add_task(Task("A", 60, fixed_time=time(8, 0)))
        pet.add_task(Task("B", 60, fixed_time=time(8, 30)))

        assert len(Scheduler(owner).find_conflicts(MONDAY)) == 1

    def test_three_overlapping_tasks_give_three_pairs(self, owner, pet):
        for index in range(3):
            pet.add_task(
                Task(f"T{index}", 60, fixed_time=time(8, index * 10))
            )

        assert len(Scheduler(owner).find_conflicts(MONDAY)) == 3

    def test_completed_tasks_do_not_conflict(self, owner, pet):
        done = Task("Done", 60, fixed_time=time(8, 0))
        pet.add_task(done)
        pet.add_task(Task("Todo", 30, fixed_time=time(8, 30)))
        done.mark_complete()

        assert Scheduler(owner).find_conflicts(MONDAY) == []

    def test_tasks_not_due_today_do_not_conflict(self, owner, pet):
        pet.add_task(Task("Daily", 60, fixed_time=time(8, 0)))
        pet.add_task(
            Task("Sunday only", 60, frequency=Frequency.WEEKLY, weekday=6,
                 fixed_time=time(8, 30))
        )

        assert Scheduler(owner).find_conflicts(MONDAY) == []
        assert len(Scheduler(owner).find_conflicts(SUNDAY)) == 1

    def test_an_owner_with_no_pets_has_no_conflicts(self):
        assert Scheduler(Owner("Jordan")).find_conflicts(MONDAY) == []

    def test_a_pet_with_no_tasks_has_no_conflicts(self, owner):
        assert Scheduler(owner).find_conflicts(MONDAY) == []

    def test_a_single_task_cannot_conflict_with_itself(self, owner, pet):
        pet.add_task(Task("Alone", 60, fixed_time=time(8, 0)))

        assert Scheduler(owner).find_conflicts(MONDAY) == []

    def test_detection_does_not_change_anything(self, owner, pet):
        pet.add_task(Task("A", 60, fixed_time=time(8, 0)))
        pet.add_task(Task("B", 30, fixed_time=time(8, 30)))

        Scheduler(owner).find_conflicts(MONDAY)

        assert len(pet.tasks) == 2
        assert all(not t.completed for t in pet.tasks)


# ===========================================================================
# 5. Empty states and whole-system behaviour
# ===========================================================================


class TestEmptyStates:
    def test_an_owner_with_no_pets_plans_an_empty_day(self):
        schedule = Scheduler(Owner("Jordan")).plan_for(MONDAY)

        assert schedule.scheduled == []
        assert schedule.skipped == []

    def test_a_pet_with_no_tasks_plans_an_empty_day(self, owner):
        schedule = Scheduler(owner).plan_for(MONDAY)

        assert schedule.scheduled == []
        assert schedule.total_minutes() == 0

    def test_an_empty_plan_still_explains_itself(self, owner):
        assert "Nothing scheduled" in Scheduler(owner).plan_for(
            MONDAY
        ).explain()

    def test_filtering_an_unknown_pet_name_returns_empty(self, owner, pet):
        pet.add_task(Task("Feed", 10))

        assert Scheduler(owner).filter_by_pet("Nobody") == []


class TestSchedulingTogether:
    def test_a_full_day_schedules_and_explains_itself(self, two_pets):
        cat, dog = two_pets.pets
        two_pets.day_start = time(7, 30)
        two_pets.day_end = time(10, 0)

        cat.add_task(Task("Insulin", 5, Priority.HIGH, fixed_time=time(7, 30)))
        dog.add_task(Task("Breakfast", 10, Priority.HIGH,
                          fixed_time=time(8, 0)))
        dog.add_task(Task("Morning walk", 30, Priority.HIGH))
        cat.add_task(Task("Litter box", 10, Priority.MEDIUM))

        schedule = Scheduler(two_pets).plan_for(MONDAY)

        assert len(schedule.scheduled) == 4
        assert schedule.scheduled[0].start_time == time(7, 30)
        assert schedule.total_minutes() <= two_pets.available_minutes()
        assert all(item.reason for item in schedule.scheduled)

    def test_nothing_is_ever_scheduled_outside_the_owners_day(
        self, owner, pet
    ):
        owner.day_start = time(9, 0)
        owner.day_end = time(11, 0)
        for index in range(6):
            pet.add_task(Task(f"T{index}", 45, Priority.HIGH))

        for item in Scheduler(owner).plan_for(MONDAY).scheduled:
            assert item.start_time >= time(9, 0)
            assert item.end_time <= time(11, 0)

    def test_scheduled_tasks_never_overlap_each_other(self, owner, pet):
        pet.add_task(Task("Pinned", 30, fixed_time=time(9, 0)))
        for index, minutes in enumerate([40, 50, 20, 35]):
            pet.add_task(Task(f"T{index}", minutes))

        items = Scheduler(owner).plan_for(MONDAY).scheduled

        for earlier, later in zip(items, items[1:]):
            assert earlier.end_time <= later.start_time

    def test_every_due_task_is_either_scheduled_or_explained(
        self, owner, pet
    ):
        # Nothing may silently disappear.
        owner.day_end = time(9, 0)
        for index in range(5):
            pet.add_task(Task(f"T{index}", 30, Priority.HIGH))

        scheduler = Scheduler(owner)
        schedule = scheduler.plan_for(MONDAY)

        assert len(schedule.scheduled) + len(schedule.skipped) == len(
            scheduler.tasks_due_on(MONDAY)
        )

    def test_completing_a_task_frees_time_for_one_that_did_not_fit(
        self, owner, pet
    ):
        owner.day_start = time(8, 0)
        owner.day_end = time(9, 0)
        big = Task("Long groom", 60, Priority.HIGH)
        pet.add_task(big)
        pet.add_task(Task("Nail trim", 45, Priority.LOW))

        scheduler = Scheduler(owner)
        assert titles(
            t.task for t in scheduler.plan_for(MONDAY).scheduled
        ) == ["Long groom"]

        big.mark_complete()

        assert titles(
            t.task for t in scheduler.plan_for(MONDAY).scheduled
        ) == ["Nail trim"]
