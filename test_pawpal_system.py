"""Tests for the PawPal+ logic layer.

Organised by the unit under test, so a gap in coverage is visible as a thin
section rather than hidden in a pile of unrelated tests.

Reason strings are asserted on as substrings, not exact matches, so reworded
messages do not break the suite.
"""

from datetime import date, time

import pytest

from pawpal_system import (
    MINUTES_PER_DAY,
    Frequency,
    Owner,
    Pet,
    Priority,
    Schedule,
    ScheduledTask,
    Scheduler,
    SkippedTask,
    Task,
    to_minutes,
    to_time,
)

# Monday 2026-10-12, so weekday() == 0. Picked deliberately: a weekday of 0 is
# falsy in Python, which is exactly the case a `if self.weekday:` bug misses.
MONDAY = date(2026, 10, 12)
TUESDAY = date(2026, 10, 13)
SUNDAY = date(2026, 10, 18)


def make_owner(start=time(8, 0), end=time(20, 0), tasks=()):
    """Owner with one pet carrying the given tasks."""
    owner = Owner("Jordan", day_start=start, day_end=end)
    pet = Pet("Mochi", "cat")
    owner.add_pet(pet)
    for task in tasks:
        pet.add_task(task)
    return owner


def plan(owner, day=MONDAY):
    """Generate and return a schedule for the owner."""
    schedule = Schedule(owner, day)
    schedule.generate()
    return schedule


def titles(schedule):
    """Scheduled task titles, in plan order."""
    return [item.task.title for item in schedule.scheduled]


def skipped_titles(schedule):
    return [item.task.title for item in schedule.skipped]


def reason_for(schedule, title):
    """The skip reason recorded for a given task title."""
    return next(i.reason for i in schedule.skipped if i.task.title == title)


# --- to_minutes / to_time ---------------------------------------------------


class TestToMinutes:
    def test_midnight_is_zero(self):
        assert to_minutes(time(0, 0)) == 0

    def test_converts_hours_and_minutes(self):
        assert to_minutes(time(8, 30)) == 510

    def test_last_minute_of_day(self):
        assert to_minutes(time(23, 59)) == 1439

    def test_ignores_seconds(self):
        assert to_minutes(time(8, 30, 45)) == 510


class TestToTime:
    def test_zero_is_midnight(self):
        assert to_time(0) == time(0, 0)

    def test_converts_back(self):
        assert to_time(510) == time(8, 30)

    def test_last_minute_of_day(self):
        assert to_time(1439) == time(23, 59)

    def test_rejects_a_full_day(self):
        # 1440 would be midnight tomorrow; silently wrapping to 00:00 would
        # make an end time look earlier than its start time.
        with pytest.raises(ValueError):
            to_time(MINUTES_PER_DAY)

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            to_time(-1)

    @pytest.mark.parametrize("minutes", [0, 1, 59, 60, 510, 719, 720, 1439])
    def test_round_trips(self, minutes):
        assert to_minutes(to_time(minutes)) == minutes


# --- Priority / Frequency ---------------------------------------------------


class TestPriority:
    def test_high_outranks_medium_outranks_low(self):
        assert (
            Priority.HIGH.rank()
            > Priority.MEDIUM.rank()
            > Priority.LOW.rank()
        )

    def test_built_from_the_ui_string(self):
        # app.py's selectbox hands over "high"/"medium"/"low" directly.
        assert Priority("high") is Priority.HIGH
        assert Priority("medium") is Priority.MEDIUM
        assert Priority("low") is Priority.LOW

    def test_unknown_string_is_rejected(self):
        with pytest.raises(ValueError):
            Priority("urgent")

    def test_sorting_by_rank_beats_sorting_alphabetically(self):
        # Alphabetically "high" < "low" < "medium", which is nonsense.
        ordered = sorted(Priority, key=lambda p: -p.rank())
        assert ordered == [Priority.HIGH, Priority.MEDIUM, Priority.LOW]


class TestFrequency:
    def test_values_match_ui_strings(self):
        assert Frequency("daily") is Frequency.DAILY
        assert Frequency("weekly") is Frequency.WEEKLY
        assert Frequency("once") is Frequency.ONCE

    def test_unknown_string_is_rejected(self):
        with pytest.raises(ValueError):
            Frequency("monthly")


# --- Pet --------------------------------------------------------------------


class TestPet:
    def test_starts_with_no_tasks(self):
        assert Pet("Mochi", "cat").tasks == []

    def test_two_pets_do_not_share_a_task_list(self):
        # The classic mutable-default bug: without field(default_factory=list)
        # every Pet would share one list.
        a, b = Pet("Mochi", "cat"), Pet("Biscuit", "dog")
        a.add_task(Task("Walk", 30))
        assert b.tasks == []

    def test_add_task_appends(self):
        pet = Pet("Mochi", "cat")
        pet.add_task(Task("Walk", 30))
        assert [t.title for t in pet.tasks] == ["Walk"]

    def test_add_task_sets_the_back_reference(self):
        pet = Pet("Mochi", "cat")
        task = Task("Walk", 30)
        pet.add_task(task)
        assert task.pet is pet

    def test_label_shows_name_and_species(self):
        assert Pet("Mochi", "cat").label() == "Mochi (cat)"


# --- Task -------------------------------------------------------------------


class TestTaskIsPinned:
    def test_task_with_a_fixed_time_is_pinned(self):
        assert Task("Meds", 10, fixed_time=time(8, 0)).is_pinned()

    def test_task_without_one_is_flexible(self):
        assert not Task("Walk", 30).is_pinned()

    def test_midnight_still_counts_as_pinned(self):
        # time(0, 0) is falsy; `if self.fixed_time:` would get this wrong.
        assert Task("Meds", 10, fixed_time=time(0, 0)).is_pinned()


class TestTaskCompletion:
    def test_tasks_start_incomplete(self):
        assert Task("Walk", 30).completed is False

    def test_mark_complete_flips_the_flag(self):
        task = Task("Walk", 30)
        task.mark_complete()
        assert task.completed is True

    def test_mark_complete_is_idempotent(self):
        task = Task("Walk", 30)
        task.mark_complete()
        task.mark_complete()
        assert task.completed is True

    def test_mark_incomplete_undoes_it(self):
        task = Task("Walk", 30)
        task.mark_complete()
        task.mark_incomplete()
        assert task.completed is False

    def test_completing_one_task_does_not_affect_another(self):
        a, b = Task("Walk", 30), Task("Feed", 10)
        a.mark_complete()
        assert b.completed is False

    def test_completion_does_not_change_anything_else(self):
        task = Task("Walk", 30, Priority.HIGH)
        task.mark_complete()
        assert task.title == "Walk"
        assert task.duration_minutes == 30
        assert task.priority is Priority.HIGH


class TestTaskIsDueOn:
    def test_daily_is_due_every_day(self):
        task = Task("Feed", 10, frequency=Frequency.DAILY)
        assert task.is_due_on(MONDAY)
        assert task.is_due_on(SUNDAY)

    def test_weekly_is_due_on_a_matching_weekday(self):
        task = Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=0)
        assert task.is_due_on(MONDAY)

    def test_weekly_is_not_due_on_another_weekday(self):
        task = Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=0)
        assert not task.is_due_on(TUESDAY)

    def test_weekly_without_a_weekday_is_never_due(self):
        task = Task("Bath", 30, frequency=Frequency.WEEKLY)
        assert not task.is_due_on(MONDAY)

    @pytest.mark.parametrize(
        "weekday,day,expected",
        [(0, MONDAY, True), (1, TUESDAY, True), (6, SUNDAY, True),
         (0, SUNDAY, False), (6, MONDAY, False)],
    )
    def test_weekly_across_the_week(self, weekday, day, expected):
        task = Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=weekday)
        assert task.is_due_on(day) is expected

    def test_once_is_due_on_its_date(self):
        task = Task("Vet", 60, frequency=Frequency.ONCE, due_date=MONDAY)
        assert task.is_due_on(MONDAY)

    def test_once_is_not_due_on_any_other_date(self):
        task = Task("Vet", 60, frequency=Frequency.ONCE, due_date=MONDAY)
        assert not task.is_due_on(TUESDAY)

    def test_once_without_a_date_is_never_due(self):
        # Otherwise ONCE behaves exactly like DAILY, repeating forever.
        task = Task("Vet", 60, frequency=Frequency.ONCE)
        assert not task.is_due_on(MONDAY)

    def test_defaults_to_daily(self):
        assert Task("Feed", 10).frequency is Frequency.DAILY


# --- Owner ------------------------------------------------------------------


class TestOwner:
    def test_starts_with_no_pets(self):
        assert Owner("Jordan").pets == []

    def test_two_owners_do_not_share_a_pet_list(self):
        a, b = Owner("Jordan"), Owner("Sam")
        a.add_pet(Pet("Mochi", "cat"))
        assert b.pets == []

    def test_available_minutes_for_a_normal_day(self):
        owner = Owner("Jordan", day_start=time(8, 0), day_end=time(20, 0))
        assert owner.available_minutes() == 720

    def test_available_minutes_for_a_short_window(self):
        owner = Owner("Jordan", day_start=time(8, 0), day_end=time(8, 45))
        assert owner.available_minutes() == 45

    def test_zero_length_day(self):
        owner = Owner("Jordan", day_start=time(8, 0), day_end=time(8, 0))
        assert owner.available_minutes() == 0

    def test_backwards_day_clamps_to_zero(self):
        # A negative budget would make "does this fit" comparisons nonsense.
        owner = Owner("Jordan", day_start=time(20, 0), day_end=time(8, 0))
        assert owner.available_minutes() == 0

    def test_all_tasks_with_no_pets(self):
        assert Owner("Jordan").all_tasks() == []

    def test_all_tasks_flattens_across_pets(self):
        owner = Owner("Jordan")
        cat, dog = Pet("Mochi", "cat"), Pet("Biscuit", "dog")
        owner.add_pet(cat)
        owner.add_pet(dog)
        cat.add_task(Task("Litter", 10))
        dog.add_task(Task("Walk", 30))
        dog.add_task(Task("Feed", 10))
        assert sorted(t.title for t in owner.all_tasks()) == [
            "Feed", "Litter", "Walk",
        ]

    def test_all_tasks_includes_pets_with_none(self):
        owner = Owner("Jordan")
        owner.add_pet(Pet("Mochi", "cat"))
        assert owner.all_tasks() == []


# --- ScheduledTask / SkippedTask -------------------------------------------


class TestScheduledTaskDescribe:
    def test_includes_times_and_title(self):
        item = ScheduledTask(Task("Walk", 30), time(8, 0), time(8, 30))
        assert "08:00" in item.describe()
        assert "08:30" in item.describe()
        assert "Walk" in item.describe()

    def test_includes_the_pet_name(self):
        pet = Pet("Mochi", "cat")
        task = Task("Walk", 30)
        pet.add_task(task)
        assert "Mochi" in ScheduledTask(task, time(8, 0), time(8, 30)).describe()

    def test_survives_a_task_with_no_pet(self):
        # Tasks built directly in tests never go through Pet.add_task(), so
        # task.pet is None and a naive task.pet.label() would raise.
        item = ScheduledTask(Task("Walk", 30), time(8, 0), time(8, 30))
        assert "Walk" in item.describe()

    def test_times_are_zero_padded(self):
        item = ScheduledTask(Task("Meds", 5), time(9, 5), time(9, 10))
        assert "09:05" in item.describe()


class TestSkippedTaskDescribe:
    def test_includes_title_duration_and_reason(self):
        item = SkippedTask(Task("Grooming", 45), "no gap left")
        text = item.describe()
        assert "Grooming" in text
        assert "45" in text
        assert "no gap left" in text


# --- Schedule.generate ------------------------------------------------------


class TestGenerateOrdering:
    def test_high_priority_is_scheduled_before_low(self):
        owner = make_owner(tasks=[
            Task("Grooming", 30, Priority.LOW),
            Task("Meds", 30, Priority.HIGH),
        ])
        assert titles(plan(owner)) == ["Meds", "Grooming"]

    def test_full_priority_order(self):
        owner = make_owner(tasks=[
            Task("Low", 30, Priority.LOW),
            Task("High", 30, Priority.HIGH),
            Task("Medium", 30, Priority.MEDIUM),
        ])
        assert titles(plan(owner)) == ["High", "Medium", "Low"]

    def test_equal_priority_puts_the_shorter_task_first(self):
        owner = make_owner(tasks=[
            Task("Long", 60, Priority.HIGH),
            Task("Short", 10, Priority.HIGH),
        ])
        assert titles(plan(owner)) == ["Short", "Long"]

    def test_first_task_starts_at_the_owners_day_start(self):
        owner = make_owner(start=time(9, 0), tasks=[Task("Walk", 30)])
        assert plan(owner).scheduled[0].start_time == time(9, 0)

    def test_tasks_run_back_to_back(self):
        owner = make_owner(start=time(8, 0), tasks=[
            Task("A", 30, Priority.HIGH),
            Task("B", 15, Priority.MEDIUM),
        ])
        first, second = plan(owner).scheduled
        assert first.end_time == second.start_time

    def test_plan_is_sorted_by_start_time(self):
        owner = make_owner(tasks=[
            Task("Flexible", 30, Priority.HIGH),
            Task("Late", 15, fixed_time=time(18, 0)),
        ])
        starts = [i.start_time for i in plan(owner).scheduled]
        assert starts == sorted(starts)

    def test_ordering_does_not_depend_on_insertion_order(self):
        a = make_owner(tasks=[
            Task("X", 20, Priority.HIGH), Task("Y", 20, Priority.HIGH),
        ])
        b = make_owner(tasks=[
            Task("Y", 20, Priority.HIGH), Task("X", 20, Priority.HIGH),
        ])
        assert titles(plan(a)) == titles(plan(b))


class TestGeneratePinned:
    def test_pinned_task_lands_on_its_fixed_time(self):
        owner = make_owner(tasks=[Task("Meds", 10, fixed_time=time(9, 0))])
        assert plan(owner).scheduled[0].start_time == time(9, 0)

    def test_pinned_end_time_is_start_plus_duration(self):
        owner = make_owner(tasks=[Task("Meds", 25, fixed_time=time(9, 0))])
        assert plan(owner).scheduled[0].end_time == time(9, 25)

    def test_pinned_reason_says_it_was_pinned(self):
        owner = make_owner(tasks=[Task("Meds", 10, fixed_time=time(9, 0))])
        assert "pinned" in plan(owner).scheduled[0].reason.lower()

    def test_pinned_low_priority_beats_flexible_high_priority(self):
        # The central tradeoff: medication at 8am is not negotiable.
        owner = make_owner(start=time(8, 0), end=time(9, 0), tasks=[
            Task("Pinned low", 60, Priority.LOW, fixed_time=time(8, 0)),
            Task("Flexible high", 30, Priority.HIGH),
        ])
        schedule = plan(owner)
        assert titles(schedule) == ["Pinned low"]
        assert skipped_titles(schedule) == ["Flexible high"]

    def test_overlapping_pinned_task_is_skipped(self):
        owner = make_owner(tasks=[
            Task("First", 60, fixed_time=time(9, 0)),
            Task("Overlap", 30, fixed_time=time(9, 30)),
        ])
        schedule = plan(owner)
        assert titles(schedule) == ["First"]
        assert "overlaps" in reason_for(schedule, "Overlap").lower()

    def test_pinned_tasks_touching_exactly_both_fit(self):
        # 09:00-10:00 and 10:00-10:30 share an instant but do not overlap.
        owner = make_owner(tasks=[
            Task("First", 60, fixed_time=time(9, 0)),
            Task("Second", 30, fixed_time=time(10, 0)),
        ])
        assert titles(plan(owner)) == ["First", "Second"]

    def test_pinned_before_the_day_starts_is_skipped(self):
        owner = make_owner(start=time(9, 0), tasks=[
            Task("Early", 10, fixed_time=time(7, 0)),
        ])
        schedule = plan(owner)
        assert skipped_titles(schedule) == ["Early"]
        assert "fit" in reason_for(schedule, "Early").lower()

    def test_pinned_running_past_the_day_end_is_skipped(self):
        owner = make_owner(end=time(17, 0), tasks=[
            Task("Overrun", 60, fixed_time=time(16, 30)),
        ])
        assert skipped_titles(plan(owner)) == ["Overrun"]

    def test_pinned_ending_exactly_at_day_end_fits(self):
        owner = make_owner(end=time(17, 0), tasks=[
            Task("Exact", 30, fixed_time=time(16, 30)),
        ])
        assert titles(plan(owner)) == ["Exact"]

    def test_pinned_starting_exactly_at_day_start_fits(self):
        owner = make_owner(start=time(8, 0), tasks=[
            Task("Exact", 30, fixed_time=time(8, 0)),
        ])
        assert titles(plan(owner)) == ["Exact"]

    def test_three_pinned_tasks_keep_their_times(self):
        owner = make_owner(tasks=[
            Task("C", 15, fixed_time=time(14, 0)),
            Task("A", 15, fixed_time=time(9, 0)),
            Task("B", 15, fixed_time=time(11, 0)),
        ])
        schedule = plan(owner)
        assert titles(schedule) == ["A", "B", "C"]
        assert [i.start_time for i in schedule.scheduled] == [
            time(9, 0), time(11, 0), time(14, 0),
        ]


class TestGenerateGaps:
    def test_flexible_task_fills_the_gap_between_two_pinned(self):
        owner = make_owner(start=time(8, 0), end=time(12, 0), tasks=[
            Task("Pinned A", 30, fixed_time=time(8, 0)),
            Task("Pinned B", 30, fixed_time=time(10, 0)),
            Task("Filler", 30, Priority.HIGH),
        ])
        schedule = plan(owner)
        filler = next(i for i in schedule.scheduled if i.task.title == "Filler")
        assert filler.start_time == time(8, 30)

    def test_flexible_task_uses_the_earliest_gap_that_fits(self):
        # 08:00-08:30 free (30 min), then pinned, then 10:00 onwards free.
        owner = make_owner(start=time(8, 0), end=time(12, 0), tasks=[
            Task("Pinned", 90, fixed_time=time(8, 30)),
            Task("Big", 60, Priority.HIGH),
        ])
        schedule = plan(owner)
        big = next(i for i in schedule.scheduled if i.task.title == "Big")
        assert big.start_time == time(10, 0)

    def test_gap_before_the_first_pinned_task_is_used(self):
        owner = make_owner(start=time(8, 0), end=time(18, 0), tasks=[
            Task("Pinned", 30, fixed_time=time(12, 0)),
            Task("Early", 30, Priority.HIGH),
        ])
        early = next(
            i for i in plan(owner).scheduled if i.task.title == "Early"
        )
        assert early.start_time == time(8, 0)

    def test_several_flexible_tasks_share_one_gap(self):
        owner = make_owner(start=time(8, 0), end=time(9, 0), tasks=[
            Task("A", 20, Priority.HIGH),
            Task("B", 20, Priority.HIGH),
            Task("C", 20, Priority.HIGH),
        ])
        schedule = plan(owner)
        assert len(schedule.scheduled) == 3
        assert [i.start_time for i in schedule.scheduled] == [
            time(8, 0), time(8, 20), time(8, 40),
        ]

    def test_task_exactly_filling_the_day_fits(self):
        owner = make_owner(start=time(8, 0), end=time(9, 0), tasks=[
            Task("Exact", 60),
        ])
        assert titles(plan(owner)) == ["Exact"]

    def test_task_one_minute_too_long_is_skipped(self):
        owner = make_owner(start=time(8, 0), end=time(9, 0), tasks=[
            Task("Overlong", 61),
        ])
        assert skipped_titles(plan(owner)) == ["Overlong"]


class TestGenerateSkipping:
    def test_task_that_does_not_fit_is_skipped_with_a_reason(self):
        owner = make_owner(start=time(8, 0), end=time(8, 30), tasks=[
            Task("Grooming", 45),
        ])
        schedule = plan(owner)
        assert skipped_titles(schedule) == ["Grooming"]
        assert "45" in reason_for(schedule, "Grooming")

    def test_skip_reason_reports_the_largest_remaining_gap(self):
        owner = make_owner(start=time(8, 0), end=time(8, 30), tasks=[
            Task("Grooming", 45),
        ])
        assert "30" in reason_for(plan(owner), "Grooming")

    def test_lower_priority_is_dropped_first_when_time_runs_out(self):
        owner = make_owner(start=time(8, 0), end=time(9, 0), tasks=[
            Task("Important", 60, Priority.HIGH),
            Task("Optional", 30, Priority.LOW),
        ])
        schedule = plan(owner)
        assert titles(schedule) == ["Important"]
        assert skipped_titles(schedule) == ["Optional"]

    def test_zero_duration_task_is_skipped(self):
        owner = make_owner(tasks=[Task("Nothing", 0)])
        schedule = plan(owner)
        assert skipped_titles(schedule) == ["Nothing"]
        assert "at least 1 minute" in reason_for(schedule, "Nothing")

    def test_negative_duration_task_is_skipped(self):
        owner = make_owner(tasks=[Task("Broken", -30)])
        assert skipped_titles(plan(owner)) == ["Broken"]

    def test_zero_duration_pinned_task_is_skipped(self):
        owner = make_owner(tasks=[Task("Nothing", 0, fixed_time=time(9, 0))])
        assert skipped_titles(plan(owner)) == ["Nothing"]

    def test_everything_is_skipped_on_a_zero_length_day(self):
        owner = make_owner(start=time(8, 0), end=time(8, 0), tasks=[
            Task("Walk", 30), Task("Feed", 10),
        ])
        schedule = plan(owner)
        assert schedule.scheduled == []
        assert len(schedule.skipped) == 2


class TestGenerateRecurring:
    def test_weekly_task_is_included_on_its_weekday(self):
        owner = make_owner(tasks=[
            Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=0),
        ])
        assert titles(plan(owner, MONDAY)) == ["Bath"]

    def test_weekly_task_is_excluded_on_other_weekdays(self):
        owner = make_owner(tasks=[
            Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=0),
        ])
        schedule = plan(owner, TUESDAY)
        assert schedule.scheduled == []
        # Not due is not the same as skipped -- it was never a candidate.
        assert schedule.skipped == []

    def test_once_task_is_included_on_its_date(self):
        owner = make_owner(tasks=[
            Task("Vet", 60, frequency=Frequency.ONCE, due_date=MONDAY),
        ])
        assert titles(plan(owner, MONDAY)) == ["Vet"]

    def test_once_task_is_excluded_on_other_dates(self):
        owner = make_owner(tasks=[
            Task("Vet", 60, frequency=Frequency.ONCE, due_date=MONDAY),
        ])
        assert plan(owner, TUESDAY).scheduled == []

    def test_daily_task_appears_on_every_day(self):
        owner = make_owner(tasks=[Task("Feed", 10)])
        for day in (MONDAY, TUESDAY, SUNDAY):
            assert titles(plan(owner, day)) == ["Feed"]

    def test_mixed_frequencies_filter_independently(self):
        owner = make_owner(tasks=[
            Task("Feed", 10, frequency=Frequency.DAILY),
            Task("Bath", 20, frequency=Frequency.WEEKLY, weekday=0),
            Task("Vet", 30, frequency=Frequency.ONCE, due_date=TUESDAY),
        ])
        assert sorted(titles(plan(owner, MONDAY))) == ["Bath", "Feed"]
        assert sorted(titles(plan(owner, TUESDAY))) == ["Feed", "Vet"]
        assert sorted(titles(plan(owner, SUNDAY))) == ["Feed"]


class TestGenerateEdgeCases:
    def test_no_pets_produces_an_empty_plan(self):
        schedule = plan(Owner("Jordan"))
        assert schedule.scheduled == []
        assert schedule.skipped == []

    def test_no_tasks_produces_an_empty_plan(self):
        assert plan(make_owner()).scheduled == []

    def test_generating_twice_does_not_duplicate(self):
        # Streamlit re-runs the script on every click, so this would show up
        # immediately in the real app.
        owner = make_owner(tasks=[Task("Walk", 30)])
        schedule = Schedule(owner, MONDAY)
        schedule.generate()
        schedule.generate()
        assert len(schedule.scheduled) == 1

    def test_generating_twice_does_not_duplicate_skips(self):
        owner = make_owner(start=time(8, 0), end=time(8, 10), tasks=[
            Task("Grooming", 45),
        ])
        schedule = Schedule(owner, MONDAY)
        schedule.generate()
        schedule.generate()
        assert len(schedule.skipped) == 1

    def test_regenerating_picks_up_a_new_task(self):
        owner = make_owner(tasks=[Task("Walk", 30)])
        schedule = Schedule(owner, MONDAY)
        schedule.generate()
        owner.pets[0].add_task(Task("Feed", 10))
        schedule.generate()
        assert len(schedule.scheduled) == 2

    def test_tasks_from_several_pets_are_all_considered(self):
        owner = Owner("Jordan", day_start=time(8, 0), day_end=time(12, 0))
        cat, dog = Pet("Mochi", "cat"), Pet("Biscuit", "dog")
        owner.add_pet(cat)
        owner.add_pet(dog)
        cat.add_task(Task("Litter", 10))
        dog.add_task(Task("Walk", 30))
        assert sorted(titles(plan(owner))) == ["Litter", "Walk"]

    def test_every_task_is_either_scheduled_or_skipped(self):
        owner = make_owner(start=time(8, 0), end=time(9, 0), tasks=[
            Task("A", 30, Priority.HIGH),
            Task("B", 30, Priority.MEDIUM),
            Task("C", 30, Priority.LOW),
            Task("D", 15, fixed_time=time(8, 0)),
        ])
        schedule = plan(owner)
        assert len(schedule.scheduled) + len(schedule.skipped) == 4

    def test_generate_never_mutates_the_original_tasks(self):
        # The whole reason ScheduledTask exists.
        task = Task("Walk", 30)
        owner = make_owner(tasks=[task])
        plan(owner)
        assert task.fixed_time is None
        assert task.duration_minutes == 30

    def test_nothing_is_scheduled_outside_the_window(self):
        owner = make_owner(start=time(9, 0), end=time(11, 0), tasks=[
            Task("A", 45, Priority.HIGH),
            Task("B", 45, Priority.MEDIUM),
            Task("C", 45, Priority.LOW),
        ])
        for item in plan(owner).scheduled:
            assert item.start_time >= time(9, 0)
            assert item.end_time <= time(11, 0)

    def test_scheduled_tasks_never_overlap(self):
        owner = make_owner(start=time(8, 0), end=time(12, 0), tasks=[
            Task("Pinned", 30, fixed_time=time(9, 0)),
            Task("A", 40, Priority.HIGH),
            Task("B", 50, Priority.MEDIUM),
            Task("C", 20, Priority.LOW),
        ])
        items = plan(owner).scheduled
        for earlier, later in zip(items, items[1:]):
            assert earlier.end_time <= later.start_time

    def test_late_day_window_does_not_wrap_past_midnight(self):
        # Guards the to_time() ValueError: 23:30 + 45 min would be 1455.
        owner = make_owner(start=time(23, 0), end=time(23, 59), tasks=[
            Task("Late", 45),
        ])
        schedule = plan(owner)
        assert titles(schedule) == ["Late"]
        assert schedule.scheduled[0].end_time == time(23, 45)


# --- Scheduler --------------------------------------------------------------


class TestScheduler:
    def test_all_tasks_with_no_pets(self):
        assert Scheduler(Owner("Jordan")).all_tasks() == []

    def test_all_tasks_gathers_across_pets(self):
        owner = Owner("Jordan")
        cat, dog = Pet("Mochi", "cat"), Pet("Biscuit", "dog")
        owner.add_pet(cat)
        owner.add_pet(dog)
        cat.add_task(Task("Litter", 10))
        dog.add_task(Task("Walk", 30))
        assert sorted(
            t.title for t in Scheduler(owner).all_tasks()
        ) == ["Litter", "Walk"]

    def test_all_tasks_includes_completed_ones(self):
        done = Task("Walk", 30)
        done.mark_complete()
        assert len(Scheduler(make_owner(tasks=[done])).all_tasks()) == 1

    def test_pending_excludes_completed(self):
        done, todo = Task("Done", 30), Task("Todo", 30)
        done.mark_complete()
        owner = make_owner(tasks=[done, todo])
        assert [t.title for t in Scheduler(owner).pending_tasks()] == ["Todo"]

    def test_completed_tasks_returns_only_completed(self):
        done, todo = Task("Done", 30), Task("Todo", 30)
        done.mark_complete()
        owner = make_owner(tasks=[done, todo])
        assert [t.title for t in Scheduler(owner).completed_tasks()] == ["Done"]

    def test_pending_and_completed_partition_everything(self):
        done, todo = Task("Done", 30), Task("Todo", 30)
        done.mark_complete()
        scheduler = Scheduler(make_owner(tasks=[done, todo]))
        assert len(scheduler.pending_tasks()) + len(
            scheduler.completed_tasks()
        ) == len(scheduler.all_tasks())

    def test_tasks_due_on_filters_by_frequency(self):
        owner = make_owner(tasks=[
            Task("Daily", 10),
            Task("Bath", 20, frequency=Frequency.WEEKLY, weekday=0),
        ])
        due = Scheduler(owner).tasks_due_on(TUESDAY)
        assert [t.title for t in due] == ["Daily"]

    def test_tasks_due_on_excludes_completed(self):
        done = Task("Done", 30)
        done.mark_complete()
        owner = make_owner(tasks=[done, Task("Todo", 30)])
        due = Scheduler(owner).tasks_due_on(MONDAY)
        assert [t.title for t in due] == ["Todo"]

    def test_tasks_for_pet_separates_pets(self):
        owner = Owner("Jordan")
        cat, dog = Pet("Mochi", "cat"), Pet("Biscuit", "dog")
        owner.add_pet(cat)
        owner.add_pet(dog)
        cat.add_task(Task("Litter", 10))
        dog.add_task(Task("Walk", 30))
        scheduler = Scheduler(owner)
        assert [t.title for t in scheduler.tasks_for_pet(cat)] == ["Litter"]
        assert [t.title for t in scheduler.tasks_for_pet(dog)] == ["Walk"]

    def test_tasks_for_pet_with_no_tasks(self):
        owner = Owner("Jordan")
        pet = Pet("Mochi", "cat")
        owner.add_pet(pet)
        assert Scheduler(owner).tasks_for_pet(pet) == []

    def test_plan_for_returns_a_generated_schedule(self):
        owner = make_owner(tasks=[Task("Walk", 30)])
        schedule = Scheduler(owner).plan_for(MONDAY)
        assert isinstance(schedule, Schedule)
        assert titles(schedule) == ["Walk"]

    def test_plan_for_matches_building_a_schedule_by_hand(self):
        owner = make_owner(tasks=[Task("Walk", 30), Task("Feed", 10)])
        assert titles(Scheduler(owner).plan_for(MONDAY)) == titles(plan(owner))

    def test_plan_for_different_days_gives_different_plans(self):
        owner = make_owner(tasks=[
            Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=0),
        ])
        scheduler = Scheduler(owner)
        assert titles(scheduler.plan_for(MONDAY)) == ["Bath"]
        assert titles(scheduler.plan_for(TUESDAY)) == []

    def test_scheduler_holds_no_state_between_plans(self):
        owner = make_owner(tasks=[Task("Walk", 30)])
        scheduler = Scheduler(owner)
        first = scheduler.plan_for(MONDAY)
        second = scheduler.plan_for(MONDAY)
        assert first is not second
        assert titles(first) == titles(second)


class TestCompletedTasksAreNotScheduled:
    def test_completed_task_is_left_out_of_the_plan(self):
        done = Task("Walk", 30)
        done.mark_complete()
        assert plan(make_owner(tasks=[done])).scheduled == []

    def test_completed_task_is_not_reported_as_skipped(self):
        # Already done is not the same as could not fit.
        done = Task("Walk", 30)
        done.mark_complete()
        assert plan(make_owner(tasks=[done])).skipped == []

    def test_completing_a_task_frees_time_for_another(self):
        done = Task("Long", 60, Priority.HIGH)
        other = Task("Short", 45, Priority.LOW)
        owner = make_owner(start=time(8, 0), end=time(9, 0),
                           tasks=[done, other])
        assert titles(plan(owner)) == ["Long"]
        done.mark_complete()
        assert titles(plan(owner)) == ["Short"]

    def test_completed_pinned_task_frees_its_slot(self):
        done = Task("Meds", 60, fixed_time=time(8, 0))
        flexible = Task("Walk", 60, Priority.HIGH)
        owner = make_owner(start=time(8, 0), end=time(9, 0),
                           tasks=[done, flexible])
        assert titles(plan(owner)) == ["Meds"]
        done.mark_complete()
        assert titles(plan(owner)) == ["Walk"]


# --- Schedule.total_minutes -------------------------------------------------


class TestTotalMinutes:
    def test_empty_plan_uses_no_time(self):
        assert plan(make_owner()).total_minutes() == 0

    def test_sums_scheduled_durations(self):
        owner = make_owner(tasks=[Task("A", 30), Task("B", 15)])
        assert plan(owner).total_minutes() == 45

    def test_excludes_skipped_tasks(self):
        owner = make_owner(start=time(8, 0), end=time(8, 30), tasks=[
            Task("Fits", 30, Priority.HIGH),
            Task("Does not", 45, Priority.LOW),
        ])
        assert plan(owner).total_minutes() == 30

    def test_never_exceeds_the_owners_available_minutes(self):
        owner = make_owner(start=time(8, 0), end=time(10, 0), tasks=[
            Task(f"T{n}", 25, Priority.HIGH) for n in range(10)
        ])
        schedule = plan(owner)
        assert schedule.total_minutes() <= owner.available_minutes()


# --- Schedule.explain -------------------------------------------------------


class TestExplain:
    def test_names_the_owner(self):
        assert "Jordan" in plan(make_owner()).explain()

    def test_reports_the_time_window(self):
        owner = make_owner(start=time(9, 0), end=time(17, 0))
        text = plan(owner).explain()
        assert "09:00" in text and "17:00" in text

    def test_lists_each_scheduled_task(self):
        owner = make_owner(tasks=[Task("Walk", 30), Task("Feed", 10)])
        text = plan(owner).explain()
        assert "Walk" in text and "Feed" in text

    def test_gives_a_reason_for_each_scheduled_task(self):
        owner = make_owner(tasks=[Task("Meds", 10, fixed_time=time(9, 0))])
        assert "pinned" in plan(owner).explain().lower()

    def test_lists_skipped_tasks_and_why(self):
        owner = make_owner(start=time(8, 0), end=time(8, 30), tasks=[
            Task("Grooming", 45),
        ])
        text = plan(owner).explain()
        assert "Grooming" in text
        assert "Left out" in text

    def test_says_so_when_nothing_is_scheduled(self):
        assert "Nothing scheduled" in plan(make_owner()).explain()

    def test_reports_minutes_used(self):
        owner = make_owner(tasks=[Task("Walk", 30)])
        assert "30" in plan(owner).explain()

    def test_is_plain_text_with_no_blank_first_line(self):
        text = plan(make_owner(tasks=[Task("Walk", 30)])).explain()
        assert isinstance(text, str)
        assert text.splitlines()[0].strip() != ""
