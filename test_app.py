"""Tests for the Streamlit glue layer in app.py.

app.py keeps its UI inside main(), behind an `if __name__ == "__main__"`
guard, so importing it here runs no Streamlit code. The helpers take a plain
mapping instead of reaching for st.session_state directly, which means a
normal dict stands in for the session and these tests need no Streamlit
runtime at all.
"""

from datetime import date, time

import pytest

from app import (
    ALL_PETS,
    SPECIES_OPTIONS,
    WEEKDAY_NAMES,
    add_pet,
    add_task,
    describe_frequency,
    ensure_owner,
    find_pet,
    pet_labels,
    plan_rows,
    skipped_rows,
    task_rows,
    update_owner_settings,
    visible_tasks,
)
from pawpal_system import Frequency, Owner, Pet, Priority, Scheduler, Task

MONDAY = date(2026, 10, 12)
TUESDAY = date(2026, 10, 13)


@pytest.fixture
def owner():
    """An owner with one pet, built the way the UI would build it."""
    o = Owner("Jordan", day_start=time(8, 0), day_end=time(20, 0))
    add_pet(o, "Mochi", "cat")
    return o


# --- ensure_owner (session state) -------------------------------------------


class TestEnsureOwner:
    def test_creates_an_owner_on_the_first_run(self):
        state = {}
        result = ensure_owner(state)
        assert isinstance(result, Owner)
        assert state["owner"] is result

    def test_returns_the_same_owner_on_later_runs(self):
        # The point of the whole exercise: Streamlit re-runs the script on
        # every click, and the Owner has to survive that.
        state = {}
        first = ensure_owner(state)
        second = ensure_owner(state)
        assert first is second

    def test_pets_survive_a_rerun(self):
        state = {}
        ensure_owner(state)
        add_pet(state["owner"], "Mochi", "cat")
        assert len(ensure_owner(state).pets) == 1

    def test_tasks_survive_many_reruns(self):
        state = {}
        owner = ensure_owner(state)
        add_task(add_pet(owner, "Mochi", "cat"), "Walk", 30, Priority.HIGH)
        for _ in range(10):
            ensure_owner(state)
        assert len(Scheduler(state["owner"]).all_tasks()) == 1

    def test_accepts_starting_values(self):
        state = {}
        owner = ensure_owner(
            state, name="Sam", day_start=time(6, 0), day_end=time(12, 0)
        )
        assert owner.name == "Sam"
        assert owner.available_minutes() == 360

    def test_starting_values_are_ignored_once_it_exists(self):
        # Otherwise editing the name in the sidebar would be undone on the
        # next rerun.
        state = {}
        ensure_owner(state, name="Jordan")
        assert ensure_owner(state, name="Sam").name == "Jordan"

    def test_does_not_disturb_other_session_keys(self):
        state = {"something_else": 42}
        ensure_owner(state)
        assert state["something_else"] == 42


class TestUpdateOwnerSettings:
    def test_changes_the_name(self):
        o = Owner("Jordan")
        update_owner_settings(o, "Sam", time(8, 0), time(20, 0))
        assert o.name == "Sam"

    def test_changes_the_time_window(self):
        o = Owner("Jordan")
        update_owner_settings(o, "Jordan", time(6, 30), time(11, 30))
        assert o.available_minutes() == 300

    def test_keeps_the_same_object(self):
        # Replacing the Owner here would throw away every pet and task.
        o = Owner("Jordan")
        assert update_owner_settings(o, "Sam", time(8, 0), time(9, 0)) is o

    def test_keeps_existing_pets(self):
        o = Owner("Jordan")
        add_pet(o, "Mochi", "cat")
        update_owner_settings(o, "Sam", time(8, 0), time(9, 0))
        assert len(o.pets) == 1

    def test_blank_name_is_ignored(self):
        o = Owner("Jordan")
        update_owner_settings(o, "   ", time(8, 0), time(9, 0))
        assert o.name == "Jordan"


# --- add_pet ----------------------------------------------------------------


class TestAddPet:
    def test_adds_the_pet_to_the_owner(self):
        o = Owner("Jordan")
        add_pet(o, "Mochi", "cat")
        assert [p.name for p in o.pets] == ["Mochi"]

    def test_returns_the_new_pet(self):
        pet = add_pet(Owner("Jordan"), "Mochi", "cat")
        assert isinstance(pet, Pet)
        assert pet.name == "Mochi"

    def test_stores_the_optional_fields(self):
        pet = add_pet(Owner("Jordan"), "Biscuit", "dog", "golden", 5)
        assert pet.breed == "golden"
        assert pet.age == 5

    def test_trims_whitespace(self):
        pet = add_pet(Owner("Jordan"), "  Mochi  ", "cat", "  tabby  ")
        assert pet.name == "Mochi"
        assert pet.breed == "tabby"

    def test_blank_name_is_rejected(self):
        o = Owner("Jordan")
        assert add_pet(o, "", "cat") is None
        assert o.pets == []

    def test_whitespace_only_name_is_rejected(self):
        o = Owner("Jordan")
        assert add_pet(o, "   ", "cat") is None
        assert o.pets == []

    def test_several_pets_accumulate(self):
        o = Owner("Jordan")
        add_pet(o, "Mochi", "cat")
        add_pet(o, "Biscuit", "dog")
        assert len(o.pets) == 2

    @pytest.mark.parametrize("species", SPECIES_OPTIONS)
    def test_every_species_option_works(self, species):
        assert add_pet(Owner("Jordan"), "Pet", species) is not None


# --- add_task ---------------------------------------------------------------


class TestAddTask:
    def test_adds_the_task_to_the_pet(self, owner):
        add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        assert [t.title for t in owner.pets[0].tasks] == ["Walk"]

    def test_sets_the_back_reference(self, owner):
        task = add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        assert task.pet is owner.pets[0]

    def test_stores_priority_and_duration(self, owner):
        task = add_task(owner.pets[0], "Walk", 45, Priority.LOW)
        assert task.duration_minutes == 45
        assert task.priority is Priority.LOW

    def test_trims_the_title(self, owner):
        task = add_task(owner.pets[0], "  Walk  ", 30, Priority.HIGH)
        assert task.title == "Walk"

    def test_blank_title_is_rejected(self, owner):
        assert add_task(owner.pets[0], "", 30, Priority.HIGH) is None
        assert owner.pets[0].tasks == []

    def test_zero_duration_is_rejected(self, owner):
        assert add_task(owner.pets[0], "Walk", 0, Priority.HIGH) is None

    def test_negative_duration_is_rejected(self, owner):
        assert add_task(owner.pets[0], "Walk", -5, Priority.HIGH) is None

    def test_pinned_task_keeps_its_time(self, owner):
        task = add_task(
            owner.pets[0], "Meds", 10, Priority.HIGH, fixed_time=time(9, 0)
        )
        assert task.is_pinned()
        assert task.fixed_time == time(9, 0)

    def test_unpinned_task_has_no_time(self, owner):
        task = add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        assert not task.is_pinned()

    def test_weekly_task_keeps_its_weekday(self, owner):
        task = add_task(
            owner.pets[0], "Bath", 30, Priority.LOW,
            Frequency.WEEKLY, weekday=2,
        )
        assert task.weekday == 2

    def test_daily_task_discards_a_stray_weekday(self, owner):
        # The form always sends a weekday, because the selectbox always has
        # something picked. A daily task must not keep it.
        task = add_task(
            owner.pets[0], "Feed", 10, Priority.HIGH,
            Frequency.DAILY, weekday=3,
        )
        assert task.weekday is None

    def test_once_task_keeps_its_date(self, owner):
        task = add_task(
            owner.pets[0], "Vet", 60, Priority.HIGH,
            Frequency.ONCE, due_date=MONDAY,
        )
        assert task.due_date == MONDAY

    def test_daily_task_discards_a_stray_date(self, owner):
        task = add_task(
            owner.pets[0], "Feed", 10, Priority.HIGH,
            Frequency.DAILY, due_date=MONDAY,
        )
        assert task.due_date is None

    def test_weekly_task_discards_a_stray_date(self, owner):
        task = add_task(
            owner.pets[0], "Bath", 30, Priority.LOW, Frequency.WEEKLY,
            weekday=0, due_date=MONDAY,
        )
        assert task.due_date is None

    def test_once_task_discards_a_stray_weekday(self, owner):
        task = add_task(
            owner.pets[0], "Vet", 60, Priority.HIGH, Frequency.ONCE,
            weekday=0, due_date=MONDAY,
        )
        assert task.weekday is None

    def test_added_task_reaches_the_scheduler(self, owner):
        add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        assert len(Scheduler(owner).tasks_due_on(MONDAY)) == 1


# --- pet_labels / find_pet --------------------------------------------------


class TestPetLookup:
    def test_labels_with_no_pets(self):
        assert pet_labels(Owner("Jordan")) == []

    def test_labels_match_pet_label(self, owner):
        assert pet_labels(owner) == ["Mochi (cat)"]

    def test_find_pet_round_trips_through_its_label(self, owner):
        label = pet_labels(owner)[0]
        assert find_pet(owner, label) is owner.pets[0]

    def test_find_pet_returns_none_for_an_unknown_label(self, owner):
        assert find_pet(owner, "Nobody (dog)") is None

    def test_find_pet_picks_the_right_one_of_several(self):
        o = Owner("Jordan")
        add_pet(o, "Mochi", "cat")
        dog = add_pet(o, "Biscuit", "dog")
        assert find_pet(o, "Biscuit (dog)") is dog

    def test_every_label_finds_its_pet(self):
        o = Owner("Jordan")
        add_pet(o, "Mochi", "cat")
        add_pet(o, "Biscuit", "dog")
        for label in pet_labels(o):
            assert find_pet(o, label) is not None


# --- describe_frequency -----------------------------------------------------


class TestDescribeFrequency:
    def test_daily(self):
        assert describe_frequency(Task("Feed", 10)) == "daily"

    def test_weekly_names_the_day(self):
        task = Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=0)
        assert describe_frequency(task) == "weekly (Monday)"

    def test_weekly_handles_the_last_day_of_the_week(self):
        task = Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=6)
        assert describe_frequency(task) == "weekly (Sunday)"

    @pytest.mark.parametrize("index,name", list(enumerate(WEEKDAY_NAMES)))
    def test_every_weekday_index_maps_to_the_right_name(self, index, name):
        task = Task("Bath", 30, frequency=Frequency.WEEKLY, weekday=index)
        assert name in describe_frequency(task)

    def test_weekly_with_no_day_says_so(self):
        task = Task("Bath", 30, frequency=Frequency.WEEKLY)
        assert "no day set" in describe_frequency(task)

    def test_once_shows_the_date(self):
        task = Task("Vet", 60, frequency=Frequency.ONCE, due_date=MONDAY)
        assert "Oct" in describe_frequency(task)

    def test_once_with_no_date_says_so(self):
        task = Task("Vet", 60, frequency=Frequency.ONCE)
        assert "no date set" in describe_frequency(task)


# --- table rows -------------------------------------------------------------


class TestPlanRows:
    def test_empty_plan_gives_no_rows(self, owner):
        assert plan_rows(Scheduler(owner).plan_for(MONDAY)) == []

    def test_one_row_per_scheduled_task(self, owner):
        add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        add_task(owner.pets[0], "Feed", 10, Priority.HIGH)
        assert len(plan_rows(Scheduler(owner).plan_for(MONDAY))) == 2

    def test_row_carries_the_display_fields(self, owner):
        add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        row = plan_rows(Scheduler(owner).plan_for(MONDAY))[0]
        assert row["Task"] == "Walk"
        assert row["Pet"] == "Mochi"
        assert row["Minutes"] == 30
        assert row["Priority"] == "high"
        assert "08:00" in row["Time"]
        assert row["Why"]

    def test_every_row_has_the_same_columns(self, owner):
        add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        add_task(owner.pets[0], "Meds", 10, Priority.LOW,
                 fixed_time=time(9, 0))
        rows = plan_rows(Scheduler(owner).plan_for(MONDAY))
        assert len({tuple(r) for r in rows}) == 1

    def test_handles_a_task_with_no_pet(self):
        # Nothing in the UI creates one, but the helper should not crash.
        o = Owner("Jordan")
        pet = Pet("Ghost", "cat")
        o.add_pet(pet)
        pet.tasks.append(Task("Orphan", 30))  # deliberately skips add_task
        assert plan_rows(Scheduler(o).plan_for(MONDAY))[0]["Pet"] == "-"


class TestSkippedRows:
    def test_nothing_skipped_gives_no_rows(self, owner):
        add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        assert skipped_rows(Scheduler(owner).plan_for(MONDAY)) == []

    def test_one_row_per_skipped_task(self):
        o = Owner("Jordan", day_start=time(8, 0), day_end=time(8, 30))
        pet = add_pet(o, "Mochi", "cat")
        add_task(pet, "Grooming", 45, Priority.LOW)
        rows = skipped_rows(Scheduler(o).plan_for(MONDAY))
        assert len(rows) == 1
        assert rows[0]["Task"] == "Grooming"

    def test_row_explains_why(self):
        o = Owner("Jordan", day_start=time(8, 0), day_end=time(8, 30))
        pet = add_pet(o, "Mochi", "cat")
        add_task(pet, "Grooming", 45, Priority.LOW)
        assert "45" in skipped_rows(Scheduler(o).plan_for(MONDAY))[0]["Why not"]


class TestTaskRows:
    def test_no_tasks_gives_no_rows(self, owner):
        assert task_rows(owner) == []

    def test_one_row_per_task_across_pets(self):
        o = Owner("Jordan")
        cat = add_pet(o, "Mochi", "cat")
        dog = add_pet(o, "Biscuit", "dog")
        add_task(cat, "Litter", 10, Priority.MEDIUM)
        add_task(dog, "Walk", 30, Priority.HIGH)
        assert len(task_rows(o)) == 2

    def test_shows_a_pinned_time(self, owner):
        add_task(owner.pets[0], "Meds", 10, Priority.HIGH,
                 fixed_time=time(9, 0))
        assert task_rows(owner)[0]["When"] == "09:00"

    def test_shows_flexible_for_an_unpinned_task(self, owner):
        add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        assert task_rows(owner)[0]["When"] == "flexible"

    def test_shows_completion(self, owner):
        task = add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        assert task_rows(owner)[0]["Done"] == "no"
        task.mark_complete()
        assert task_rows(owner)[0]["Done"] == "yes"

    def test_includes_completed_tasks(self, owner):
        # The plan hides them, but the task list should still show them.
        task = add_task(owner.pets[0], "Walk", 30, Priority.HIGH)
        task.mark_complete()
        assert len(task_rows(owner)) == 1


# --- visible_tasks (the filter and sort controls) ---------------------------


class TestVisibleTasks:
    @pytest.fixture
    def stocked(self):
        """An owner with two pets, four tasks, one of them completed."""
        o = Owner("Jordan", day_start=time(8, 0), day_end=time(20, 0))
        cat = add_pet(o, "Mochi", "cat")
        dog = add_pet(o, "Biscuit", "dog")
        add_task(cat, "Litter box", 10, Priority.MEDIUM)
        add_task(cat, "Insulin", 5, Priority.HIGH, fixed_time=time(7, 30))
        add_task(dog, "Walk", 30, Priority.HIGH)
        done = add_task(dog, "Breakfast", 10, Priority.LOW,
                        fixed_time=time(8, 0))
        done.mark_complete()
        return o

    def test_defaults_to_outstanding_only(self, stocked):
        titles = [t.title for t in visible_tasks(stocked)]
        assert "Breakfast" not in titles
        assert len(titles) == 3

    def test_completed_filter_shows_only_completed(self, stocked):
        titles = [t.title for t in visible_tasks(stocked,
                                                 status_choice="Completed")]
        assert titles == ["Breakfast"]

    def test_all_status_shows_everything(self, stocked):
        assert len(visible_tasks(stocked, status_choice="All")) == 4

    def test_status_filters_partition_the_whole_list(self, stocked):
        outstanding = visible_tasks(stocked, status_choice="Outstanding")
        completed = visible_tasks(stocked, status_choice="Completed")
        every = visible_tasks(stocked, status_choice="All")
        assert len(outstanding) + len(completed) == len(every)

    def test_filtering_by_pet_narrows_the_list(self, stocked):
        titles = [t.title for t in visible_tasks(stocked, "Mochi (cat)",
                                                 status_choice="All")]
        assert sorted(titles) == ["Insulin", "Litter box"]

    def test_all_pets_is_the_default(self, stocked):
        assert len(visible_tasks(stocked, ALL_PETS, "All")) == 4

    def test_an_unknown_pet_label_shows_nothing(self, stocked):
        assert visible_tasks(stocked, "Nobody (dog)", "All") == []

    def test_pet_and_status_filters_combine(self, stocked):
        titles = [t.title for t in visible_tasks(stocked, "Biscuit (dog)",
                                                 "Outstanding")]
        assert titles == ["Walk"]

    def test_sort_by_time_puts_pinned_first(self, stocked):
        titles = [t.title for t in visible_tasks(stocked, ALL_PETS, "All",
                                                 "Time")]
        assert titles[:2] == ["Insulin", "Breakfast"]

    def test_sort_by_priority_puts_urgent_first(self, stocked):
        tasks = visible_tasks(stocked, ALL_PETS, "All", "Priority")
        assert tasks[0].priority is Priority.HIGH
        assert tasks[-1].priority is Priority.LOW

    def test_sort_by_pet_groups_by_pet_name(self, stocked):
        names = [t.pet.name for t in visible_tasks(stocked, ALL_PETS, "All",
                                                   "Pet")]
        assert names == sorted(names)

    def test_an_unknown_sort_choice_falls_back_to_time(self, stocked):
        assert [t.title for t in visible_tasks(stocked, ALL_PETS, "All",
                                               "Nonsense")] == [
            t.title for t in visible_tasks(stocked, ALL_PETS, "All", "Time")
        ]

    def test_no_tasks_gives_an_empty_list(self):
        assert visible_tasks(Owner("Jordan")) == []

    def test_filtering_does_not_mutate_the_pets_lists(self, stocked):
        before = [[t.title for t in p.tasks] for p in stocked.pets]
        visible_tasks(stocked, "Mochi (cat)", "All", "Priority")
        assert [[t.title for t in p.tasks] for p in stocked.pets] == before


# --- end to end through the UI helpers --------------------------------------


class TestUserJourney:
    def test_a_full_session_produces_a_plan(self):
        """Everything a user would click, in order, with a dict as session."""
        state = {}
        owner = ensure_owner(state)
        update_owner_settings(owner, "Jordan", time(7, 30), time(10, 0))

        cat = add_pet(owner, "Mochi", "cat", "tabby", 3)
        dog = add_pet(owner, "Biscuit", "dog", "golden retriever", 5)

        add_task(cat, "Insulin", 5, Priority.HIGH, fixed_time=time(7, 30))
        add_task(dog, "Breakfast", 10, Priority.HIGH, fixed_time=time(8, 0))
        add_task(dog, "Morning walk", 30, Priority.HIGH)
        add_task(cat, "Litter box", 10, Priority.MEDIUM)
        add_task(dog, "Nail trim", 25, Priority.LOW)

        schedule = Scheduler(ensure_owner(state)).plan_for(MONDAY)

        assert len(plan_rows(schedule)) == 5
        assert schedule.total_minutes() <= owner.available_minutes()
        assert plan_rows(schedule)[0]["Time"].startswith("07:30")

    def test_ticking_a_task_off_frees_time_for_another(self):
        state = {}
        owner = ensure_owner(state)
        update_owner_settings(owner, "Jordan", time(8, 0), time(9, 0))
        pet = add_pet(owner, "Mochi", "cat")
        big = add_task(pet, "Long groom", 60, Priority.HIGH)
        add_task(pet, "Nail trim", 45, Priority.LOW)

        before = Scheduler(owner).plan_for(MONDAY)
        assert [r["Task"] for r in plan_rows(before)] == ["Long groom"]
        assert len(skipped_rows(before)) == 1

        big.mark_complete()

        after = Scheduler(owner).plan_for(MONDAY)
        assert [r["Task"] for r in plan_rows(after)] == ["Nail trim"]
        assert skipped_rows(after) == []

    def test_changing_the_day_changes_the_plan(self):
        state = {}
        owner = ensure_owner(state)
        pet = add_pet(owner, "Biscuit", "dog")
        add_task(pet, "Bath", 30, Priority.LOW, Frequency.WEEKLY, weekday=0)

        assert len(plan_rows(Scheduler(owner).plan_for(MONDAY))) == 1
        assert plan_rows(Scheduler(owner).plan_for(TUESDAY)) == []

    def test_shrinking_the_day_pushes_tasks_out(self):
        state = {}
        owner = ensure_owner(state)
        pet = add_pet(owner, "Biscuit", "dog")
        add_task(pet, "Walk", 60, Priority.HIGH)

        assert len(plan_rows(Scheduler(owner).plan_for(MONDAY))) == 1

        update_owner_settings(owner, "Jordan", time(8, 0), time(8, 30))
        assert plan_rows(Scheduler(owner).plan_for(MONDAY)) == []
        assert len(skipped_rows(Scheduler(owner).plan_for(MONDAY))) == 1
