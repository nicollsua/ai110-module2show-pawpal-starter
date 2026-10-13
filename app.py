"""PawPal+ Streamlit UI.

The thin layer over pawpal_system.py. Everything here is either reading input
from the user or displaying what the Scheduler produced -- no scheduling logic
lives in this file.

Run it with:

    streamlit run app.py

The helper functions at the top take a plain mapping rather than touching
st.session_state directly, which is what lets test_app.py exercise them with
an ordinary dict and no Streamlit runtime.
"""

from __future__ import annotations

from datetime import date, time
from typing import MutableMapping

import streamlit as st

# Step 1: bring the logic-layer classes into the UI.
from pawpal_system import (
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
)

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

SPECIES_OPTIONS = ["dog", "cat", "bird", "rabbit", "other"]


# --- Step 2: session state --------------------------------------------------
# Streamlit re-runs this whole script on every interaction, so anything built
# at module level is thrown away and rebuilt each time. st.session_state is a
# dict that survives those re-runs, so the Owner lives there and is created
# once, on the first run only.


def ensure_owner(
    state: MutableMapping,
    *,
    name: str = "Jordan",
    day_start: time = time(8, 0),
    day_end: time = time(20, 0),
) -> Owner:
    """Return the Owner from session state, creating it on the first run.

    The "not in" check is the whole point: without it a fresh, empty Owner
    would replace the real one on every single button click.
    """
    if "owner" not in state:
        state["owner"] = Owner(name, day_start=day_start, day_end=day_end)
    return state["owner"]


def update_owner_settings(
    owner: Owner, name: str, day_start: time, day_end: time
) -> Owner:
    """Apply edited owner details without replacing the object.

    Mutating in place keeps the existing pets and tasks attached. Building a
    new Owner here would silently wipe them.
    """
    cleaned = name.strip()
    if cleaned:
        owner.name = cleaned
    owner.day_start = day_start
    owner.day_end = day_end
    return owner


# --- Step 3: UI actions -> logic-layer methods ------------------------------


def add_pet(
    owner: Owner, name: str, species: str, breed: str = "", age: int = 0
) -> Pet | None:
    """Build a Pet from form input and hand it to Owner.add_pet().

    Returns None for a blank name so the caller can show an error instead of
    creating a nameless pet.
    """
    cleaned = name.strip()
    if not cleaned:
        return None
    pet = Pet(cleaned, species, breed=breed.strip(), age=int(age))
    owner.add_pet(pet)
    return pet


def add_task(
    pet: Pet | None,
    title: str,
    duration_minutes: int,
    priority: Priority,
    frequency: Frequency = Frequency.DAILY,
    weekday: int | None = None,
    due_date: date | None = None,
    fixed_time: time | None = None,
) -> Task | None:
    """Build a Task from form input and hand it to Pet.add_task().

    Fields that do not apply to the chosen frequency are cleared, so a task
    switched from weekly to daily does not keep a stale weekday hanging off
    it.

    Returns None for a missing pet, a blank title, or a non-positive
    duration, so the caller can show an error rather than crash.
    """
    if pet is None:
        return None

    cleaned = title.strip()
    if not cleaned or int(duration_minutes) <= 0:
        return None

    task = Task(
        cleaned,
        int(duration_minutes),
        priority,
        frequency,
        weekday=weekday if frequency is Frequency.WEEKLY else None,
        due_date=due_date if frequency is Frequency.ONCE else None,
        fixed_time=fixed_time,
    )
    pet.add_task(task)
    return task


def pet_labels(owner: Owner) -> list[str]:
    """Return each pet's display label, for a selectbox."""
    return [pet.label() for pet in owner.pets]


def find_pet(owner: Owner, label: str) -> Pet | None:
    """Return the pet matching a label from pet_labels(), or None."""
    return next((p for p in owner.pets if p.label() == label), None)


# --- Display helpers --------------------------------------------------------


def plan_rows(schedule) -> list[dict]:
    """Turn a Schedule's placed tasks into rows for a table."""
    return [
        {
            "Time": f"{item.start_time:%H:%M} - {item.end_time:%H:%M}",
            "Task": item.task.title,
            "Pet": item.task.pet.name if item.task.pet else "-",
            "Minutes": item.task.duration_minutes,
            "Priority": item.task.priority.value,
            "Why": item.reason,
        }
        for item in schedule.scheduled
    ]


def skipped_rows(schedule) -> list[dict]:
    """Turn a Schedule's skipped tasks into rows for a table."""
    return [
        {
            "Task": item.task.title,
            "Pet": item.task.pet.name if item.task.pet else "-",
            "Minutes": item.task.duration_minutes,
            "Priority": item.task.priority.value,
            "Why not": item.reason,
        }
        for item in schedule.skipped
    ]


def task_rows(owner: Owner) -> list[dict]:
    """Turn every task the owner has into rows for a table."""
    return [
        {
            "Pet": task.pet.name if task.pet else "-",
            "Task": task.title,
            "Minutes": task.duration_minutes,
            "Priority": task.priority.value,
            "Repeats": describe_frequency(task),
            "When": describe_time(task),
            "Done": "yes" if task.completed else "no",
        }
        for task in Scheduler(owner).all_tasks()
    ]


ALL_PETS = "All pets"
SORT_CHOICES = ["Time", "Priority", "Pet"]
STATUS_CHOICES = ["Outstanding", "Completed", "All"]


def visible_tasks(
    owner: Owner,
    pet_choice: str = ALL_PETS,
    status_choice: str = "Outstanding",
    sort_choice: str = "Time",
) -> list[Task]:
    """Apply the task list's filter and sort controls.

    Pure function over the Scheduler's own filtering and sorting methods, so
    the UI never reimplements any of that logic. Takes the control values as
    plain strings because that is what Streamlit's selectboxes hand back.
    """
    scheduler = Scheduler(owner)

    if status_choice == "Outstanding":
        tasks = scheduler.filter_by_status(False)
    elif status_choice == "Completed":
        tasks = scheduler.filter_by_status(True)
    else:
        tasks = scheduler.all_tasks()

    if pet_choice != ALL_PETS:
        wanted = find_pet(owner, pet_choice)
        tasks = [t for t in tasks if wanted is not None and t.pet is wanted]

    if sort_choice == "Priority":
        return scheduler.sort_by_priority(tasks)
    if sort_choice == "Pet":
        return sorted(
            tasks, key=lambda t: (t.pet.name if t.pet else "", t.title)
        )
    return scheduler.sort_by_time(tasks)


def describe_time(task: Task) -> str:
    """Return a task's pinned time, or "flexible" if it has none."""
    return f"{task.fixed_time:%H:%M}" if task.is_pinned() else "flexible"


def describe_task(task: Task) -> str:
    """Return one Markdown line summarising a task for the list view."""
    parts = [
        task.pet.name if task.pet else "?",
        f"{task.duration_minutes} min",
        task.priority.value,
        describe_frequency(task),
        describe_time(task),
    ]
    return f"**{task.title}** &nbsp; " + " &nbsp;·&nbsp; ".join(parts)


def describe_frequency(task: Task) -> str:
    """Describe a task's recurrence in words, e.g. "weekly (Monday)"."""
    if task.frequency is Frequency.WEEKLY:
        if task.weekday is None:
            return "weekly (no day set)"
        return f"weekly ({WEEKDAY_NAMES[task.weekday]})"
    if task.frequency is Frequency.ONCE:
        if task.due_date is None:
            return "once (no date set)"
        return f"once ({task.due_date:%b %d})"
    return "daily"


# --- UI ---------------------------------------------------------------------


def render_sidebar(owner: Owner) -> date:
    """Draw the owner settings and day picker. Returns the day to plan."""
    with st.sidebar:
        st.header("Owner")
        name = st.text_input("Your name", value=owner.name, key="owner_name")
        start = st.time_input(
            "Day starts", value=owner.day_start, key="owner_start"
        )
        end = st.time_input("Day ends", value=owner.day_end, key="owner_end")
        update_owner_settings(owner, name, start, end)

        if owner.available_minutes() == 0:
            st.error("Your day ends before it starts, so nothing can fit.")
        else:
            st.caption(f"{owner.available_minutes()} minutes available.")

        st.divider()
        st.header("Planning for")
        day = st.date_input("Day", value=date.today(), key="plan_day")
        st.caption(f"That is a {WEEKDAY_NAMES[day.weekday()]}.")

    return day


def render_add_pet(owner: Owner) -> None:
    """Draw the add-a-pet form and wire it to Owner.add_pet()."""
    st.subheader("Pets")

    with st.form("add_pet", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Pet name", placeholder="Mochi",
                                 key="pet_name")
            species = st.selectbox("Species", SPECIES_OPTIONS,
                                   key="pet_species")
        with col2:
            breed = st.text_input("Breed (optional)", placeholder="tabby",
                                  key="pet_breed")
            age = st.number_input("Age", min_value=0, max_value=40, value=1,
                                  key="pet_age")

        if st.form_submit_button("Add pet", width="stretch"):
            pet = add_pet(owner, name, species, breed, age)
            if pet is None:
                st.error("Give your pet a name first.")
            else:
                # Rerun so the new pet shows up everywhere at once: the list
                # below, and the pet picker in the task form.
                st.rerun()

    if owner.pets:
        st.write(" ".join(f"`{p.label()}`" for p in owner.pets))
    else:
        st.info("No pets yet. Add one above to get started.")


def draw_task_fields(owner: Owner) -> dict:
    """Draw the task form's inputs and return what the user entered.

    Separated from render_add_task() so that function is about what happens
    on submit, rather than two dozen lines of widget setup.
    """
    col1, col2 = st.columns(2)
    with col1:
        pet_label = st.selectbox("For which pet", pet_labels(owner),
                                 key="task_pet")
        title = st.text_input("Task", placeholder="Morning walk",
                              key="task_title")
        duration = st.number_input(
            "Duration (minutes)", min_value=1, max_value=480, value=20,
            key="task_duration",
        )
    with col2:
        priority = st.selectbox(
            "Priority", [p.value for p in Priority], index=1,
            key="task_priority",
        )
        frequency = st.selectbox(
            "Repeats", [f.value for f in Frequency], index=0,
            key="task_frequency",
        )
        weekday_name = st.selectbox("On which day (weekly only)",
                                    WEEKDAY_NAMES, key="task_weekday")
        once_date = st.date_input("On which date (once only)",
                                  value=date.today(), key="task_date")

    # Both stay enabled. Widgets inside a form do not trigger a rerun until
    # the form is submitted, so disabling the time picker based on the
    # checkbox would read last run's value -- the box would stay grey right
    # after ticking it, and the time could never be set. The time is simply
    # ignored unless the box is ticked.
    pinned = st.checkbox("This has to happen at a specific time",
                         key="task_pinned")
    fixed_time = st.time_input("At (used only if ticked)",
                               value=time(8, 0), key="task_time")

    return {
        "pet": find_pet(owner, pet_label),
        "title": title,
        "duration_minutes": duration,
        "priority": Priority(priority),
        "frequency": Frequency(frequency),
        "weekday": WEEKDAY_NAMES.index(weekday_name),
        "due_date": once_date,
        "fixed_time": fixed_time if pinned else None,
    }


def render_add_task(owner: Owner) -> None:
    """Draw the add-a-task form and wire it to Pet.add_task()."""
    st.subheader("Tasks")

    if not owner.pets:
        st.caption("Add a pet first, then you can give them tasks.")
        return

    with st.form("add_task", clear_on_submit=True):
        entered = draw_task_fields(owner)

        if st.form_submit_button("Add task", width="stretch"):
            if add_task(**entered) is None:
                st.error("Give the task a title and a duration of at least 1.")
            else:
                st.rerun()


def render_task_list(owner: Owner, day: date) -> None:
    """Draw the filterable, sortable task list with a Done button each.

    Completion goes through Scheduler.complete_task() rather than
    Task.mark_complete(), which is what makes a daily or weekly task come
    back for its next occurrence. A button rather than a tick box, because
    completing now has a consequence -- it queues the repeat -- and a tick
    box implies you can simply untick it.
    """
    scheduler = Scheduler(owner)
    if not scheduler.all_tasks():
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        pet_choice = st.selectbox(
            "Show", [ALL_PETS] + pet_labels(owner), key="filter_pet"
        )
    with col2:
        status_choice = st.selectbox(
            "Status", STATUS_CHOICES, key="filter_status"
        )
    with col3:
        sort_choice = st.selectbox("Sort by", SORT_CHOICES, key="sort_by")

    tasks = visible_tasks(owner, pet_choice, status_choice, sort_choice)

    if not tasks:
        st.caption("Nothing matches those filters.")
        return

    for index, task in enumerate(tasks):
        row, action = st.columns([5, 1])
        with row:
            st.markdown(describe_task(task))
        with action:
            if task.completed:
                st.caption("done")
            elif st.button("Done", key=f"done_{index}", width="stretch"):
                repeat = scheduler.complete_task(task, day)
                if repeat is None:
                    st.toast(f"{task.title} done.")
                else:
                    st.toast(
                        f"{task.title} done - next one "
                        f"{repeat.starts_on:%a %d %b}."
                    )
                st.rerun()

    with st.expander("All tasks as a table"):
        st.dataframe(task_rows(owner), width="stretch", hide_index=True)


def render_conflicts(owner: Owner, day: date) -> None:
    """Warn about clashing fixed times before showing the plan.

    Shown above the plan rather than inside it, because a clash is something
    the owner has to resolve themselves -- the scheduler can only drop one of
    the two. Each warning names both tasks and both pets so it is actionable
    without having to go hunting.
    """
    scheduler = Scheduler(owner)
    if not scheduler.tasks_due_on(day):
        return

    conflicts = scheduler.find_conflicts(day)
    if not conflicts:
        st.success("No clashing appointments today.")
        return

    st.warning(
        f"{len(conflicts)} clash(es). Only the earlier task of each pair "
        f"gets scheduled, so move one of them if both matter."
    )
    for warning in conflicts:
        st.markdown(f"- {warning}")


def render_schedule(owner: Owner, day: date) -> None:
    """Build a plan with the Scheduler and show it."""
    st.subheader("Today's plan")

    if not Scheduler(owner).all_tasks():
        st.info("Add some tasks and a plan will appear here.")
        return

    schedule = Scheduler(owner).plan_for(day)

    if schedule.scheduled:
        st.dataframe(plan_rows(schedule), width="stretch",
                     hide_index=True)
        used = schedule.total_minutes()
        available = owner.available_minutes()
        summary = (
            f"{len(schedule.scheduled)} task(s), using {used} of "
            f"{available} minutes ({available - used} spare)."
        )
        if schedule.skipped:
            st.warning(f"{summary} {len(schedule.skipped)} did not fit.")
        else:
            st.success(f"Everything fits. {summary}")
    else:
        st.warning("Nothing could be scheduled for this day.")

    if schedule.skipped:
        st.markdown("**Left out**")
        st.dataframe(skipped_rows(schedule), width="stretch",
                     hide_index=True)

    with st.expander("Why this plan?"):
        st.code(schedule.explain(), language=None)


def main() -> None:
    """Draw the whole app."""
    st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
    st.title("🐾 PawPal+")
    st.caption(
        "Plan your pets' care around the time you actually have."
    )

    owner = ensure_owner(st.session_state)
    day = render_sidebar(owner)

    render_add_pet(owner)
    st.divider()
    render_add_task(owner)
    render_task_list(owner, day)
    st.divider()
    render_conflicts(owner, day)
    render_schedule(owner, day)


# Streamlit runs this script with __name__ set to "__main__", so the UI draws
# normally under `streamlit run app.py`. The guard means test_app.py can
# import this module to test the helpers without any of it rendering.
if __name__ == "__main__":
    main()
