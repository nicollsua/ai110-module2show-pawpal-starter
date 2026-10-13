"""Quick tests for the two behaviors from Step 3.

Deliberately small and readable. The exhaustive suite lives in
test_pawpal_system.py at the project root; these two are the "can I see at a
glance that the basics work" checks.
"""

from pawpal_system import Pet, Task


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
