"""Tests that drive the real Streamlit app.

test_app.py tests the helper functions in isolation. These go through
Streamlit's own AppTest harness instead, which runs app.py exactly the way
`streamlit run` does -- real session state, real reruns, real widgets.

That makes these the tests that would actually catch a broken wire-up: a
button handler that calls the wrong method, a form that loses its input, or
an Owner that gets rebuilt empty on every rerun.

They are slower than the rest of the suite (each one boots a script runner),
so the exhaustive cases stay in test_app.py and only the journeys live here.
"""

from datetime import date, time

import pytest
from streamlit.testing.v1 import AppTest

from pawpal_system import Scheduler

APP = "app.py"
MONDAY = date(2026, 10, 12)


def launch():
    """Start the app and return it after its first run."""
    return AppTest.from_file(APP, default_timeout=30).run()


def add_pet_through_ui(at, name="Mochi", species="cat"):
    """Fill in the add-pet form and click Add pet."""
    at.text_input("pet_name").set_value(name)
    at.selectbox("pet_species").set_value(species)
    at.button[0].click().run()
    return at


def add_task_through_ui(at, title="Morning walk", minutes=30,
                        priority="high"):
    """Fill in the add-task form and click Add task."""
    at.text_input("task_title").set_value(title)
    at.number_input("task_duration").set_value(minutes)
    at.selectbox("task_priority").set_value(priority)
    at.button[1].click().run()
    return at


def owner_of(at):
    return at.session_state["owner"]


def plan_table(at):
    """The first dataframe rendered, as a list of row dicts."""
    frames = [e for e in at.main if type(e).__name__ == "Dataframe"]
    return frames


# --- the app loads ----------------------------------------------------------


class TestAppLoads:
    def test_runs_without_an_exception(self):
        assert not launch().exception

    def test_shows_its_title(self):
        assert "PawPal+" in launch().title[0].value

    def test_creates_an_owner_in_session_state(self):
        assert "owner" in launch().session_state

    def test_prompts_for_a_pet_when_empty(self):
        messages = " ".join(i.value for i in launch().info)
        assert "No pets yet" in messages

    def test_shows_the_three_main_sections(self):
        headings = [s.value for s in launch().subheader]
        assert headings == ["Pets", "Tasks", "Today's plan"]


# --- Step 2: state survives reruns ------------------------------------------


class TestSessionStatePersistence:
    def test_the_owner_is_the_same_object_after_a_rerun(self):
        at = launch()
        first = owner_of(at)
        at.run()
        assert owner_of(at) is first

    def test_a_pet_survives_a_rerun(self):
        at = add_pet_through_ui(launch())
        at.run()
        assert [p.name for p in owner_of(at).pets] == ["Mochi"]

    def test_a_pet_survives_many_reruns(self):
        at = add_pet_through_ui(launch())
        for _ in range(5):
            at.run()
        assert len(owner_of(at).pets) == 1

    def test_a_task_survives_a_rerun(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        at.run()
        assert len(Scheduler(owner_of(at)).all_tasks()) == 1

    def test_editing_the_owner_name_keeps_the_pets(self):
        at = add_pet_through_ui(launch())
        at.text_input("owner_name").set_value("Sam").run()
        assert owner_of(at).name == "Sam"
        assert len(owner_of(at).pets) == 1


# --- Step 3: UI actions reach the logic layer -------------------------------


class TestAddPetWiring:
    def test_clicking_add_pet_calls_owner_add_pet(self):
        at = add_pet_through_ui(launch())
        assert [p.label() for p in owner_of(at).pets] == ["Mochi (cat)"]

    def test_the_species_choice_is_carried_through(self):
        at = add_pet_through_ui(launch(), "Biscuit", "dog")
        assert owner_of(at).pets[0].species == "dog"

    def test_a_blank_name_shows_an_error_and_adds_nothing(self):
        at = launch()
        at.button[0].click().run()
        assert owner_of(at).pets == []
        assert any("name" in e.value.lower() for e in at.error)

    def test_two_pets_can_be_added(self):
        at = add_pet_through_ui(launch(), "Mochi", "cat")
        at = add_pet_through_ui(at, "Biscuit", "dog")
        assert len(owner_of(at).pets) == 2

    def test_the_task_form_appears_once_a_pet_exists(self):
        at = launch()
        assert "task_title" not in [i.key for i in at.text_input]
        at = add_pet_through_ui(at)
        assert "task_title" in [i.key for i in at.text_input]


class TestAddTaskWiring:
    def test_clicking_add_task_calls_pet_add_task(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        pet = owner_of(at).pets[0]
        assert [t.title for t in pet.tasks] == ["Morning walk"]

    def test_the_form_values_reach_the_task(self):
        at = add_task_through_ui(
            add_pet_through_ui(launch()), "Nail trim", 25, "low"
        )
        task = Scheduler(owner_of(at)).all_tasks()[0]
        assert task.duration_minutes == 25
        assert task.priority.value == "low"

    def test_a_blank_title_shows_an_error_and_adds_nothing(self):
        at = add_pet_through_ui(launch())
        at.button[1].click().run()
        assert Scheduler(owner_of(at)).all_tasks() == []
        assert any("title" in e.value.lower() for e in at.error)

    def test_a_pinned_task_keeps_its_time(self):
        at = add_pet_through_ui(launch())
        at.text_input("task_title").set_value("Meds")
        at.checkbox("task_pinned").set_value(True)
        at.time_input("task_time").set_value(time(9, 0))
        at.button[1].click().run()
        assert Scheduler(owner_of(at)).all_tasks()[0].fixed_time == time(9, 0)

    def test_an_unpinned_task_has_no_time(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        assert not Scheduler(owner_of(at)).all_tasks()[0].is_pinned()

    def test_a_task_goes_to_the_pet_that_was_picked(self):
        at = add_pet_through_ui(launch(), "Mochi", "cat")
        at = add_pet_through_ui(at, "Biscuit", "dog")
        at.selectbox("task_pet").set_value("Biscuit (dog)")
        at.text_input("task_title").set_value("Walk")
        at.button[1].click().run()
        cat, dog = owner_of(at).pets
        assert [t.title for t in dog.tasks] == ["Walk"]
        assert cat.tasks == []


class TestCompletionWiring:
    def test_a_tick_box_appears_for_each_task(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        labels = [c.label for c in at.checkbox]
        assert any("Morning walk" in label for label in labels)

    def test_ticking_a_task_marks_it_complete(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        at.checkbox("done_0").set_value(True).run()
        assert Scheduler(owner_of(at)).all_tasks()[0].completed is True

    def test_unticking_marks_it_incomplete_again(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        at.checkbox("done_0").set_value(True).run()
        at.checkbox("done_0").set_value(False).run()
        assert Scheduler(owner_of(at)).all_tasks()[0].completed is False

    def test_a_completed_task_leaves_the_plan(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        before = len(plan_table(at))
        at.checkbox("done_0").set_value(True).run()
        assert len(plan_table(at)) < before


# --- the plan renders -------------------------------------------------------


class TestPlanRendering:
    def test_a_table_appears_once_there_is_a_task(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        assert plan_table(at)

    def test_the_summary_caption_reports_the_minutes_used(self):
        at = add_task_through_ui(
            add_pet_through_ui(launch()), "Morning walk", 30
        )
        captions = " ".join(c.value for c in at.caption)
        assert "30" in captions

    def test_the_explanation_is_rendered(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        code_blocks = [e for e in at.main if type(e).__name__ == "Code"]
        assert code_blocks
        assert "Morning walk" in code_blocks[0].value

    def test_an_impossible_day_is_reported(self):
        at = add_task_through_ui(add_pet_through_ui(launch()))
        at.time_input("owner_start").set_value(time(20, 0))
        at.time_input("owner_end").set_value(time(8, 0)).run()
        assert any("ends before it starts" in e.value for e in at.error)

    def test_a_task_too_long_for_the_day_is_shown_as_left_out(self):
        at = add_pet_through_ui(launch())
        at.time_input("owner_end").set_value(time(8, 20)).run()
        at = add_task_through_ui(at, "Long groom", 60)
        markdown = " ".join(m.value for m in at.markdown)
        assert "Left out" in markdown
