# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

- So I have planned to do four classes: owner, pet, task, and schedule. For the owner there would be attribute of name. For the pets the would be name, species, type, and age (it would also belong to owner and owner can have multiple pets). For task it would have time and priority (it would also belong to each specific pet). Lastly, for schedule the would be logic (it would belong to the owner since the schedule has to align).

The responsibilities I had in mind were: Owner is the person using the app and the thing that pets hang off of. Pet is just the info about the animal plus the list of tasks that animal needs. Task is one thing that has to get done. Schedule is the one that actually thinks — it looks at everything and decides what the day looks like.

I put Schedule on the Owner instead of on the Pet on purpose. If you have two pets, you don't get two separate days. There's one day and everything has to fit inside it, so the plan has to be built from the owner's side.

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yeah, three things changed once I started thinking about how the scheduler would actually run.

**1. "Time" on a task was actually two different things.** I originally wrote that Task would have `time`, but I was using that word for two things without noticing. How *long* something takes (a walk is 30 minutes) and *when* it has to happen (meds at 8am) are not the same attribute, and the scheduler treats them completely differently — duration gets subtracted from the day, a fixed time has to be respected. So Task now has `duration_minutes` and a separate `fixed_time`. If `fixed_time` is empty, the task is flexible and the scheduler picks the slot for it. That one change is what makes pinned tasks possible at all.

**2. Owner needed more than a name.** This was the bigger miss. I had Owner holding just a name, but then there was nothing for the scheduler to schedule *against* — no reason to ever leave a task out. The whole point is that the owner is busy and doesn't have unlimited time. So Owner got `day_start` and `day_end`, which is the time window everything has to fit in. This actually made me more confident that putting Schedule on Owner was right, since now the constraint lives there too.

**3. I added a fifth class, ScheduledTask.** At first I was going to just store the start time on the Task itself, but that breaks as soon as you generate a plan twice — the second run overwrites the first one's times, and now your task list is holding leftover data from a plan you threw away. A Task is a fact that's always true ("walk the dog, 30 min, high priority"). Where it landed today is a different fact. So ScheduledTask wraps a Task and adds `start_time`, `end_time`, and the reason it got placed there. Keeping them separate is also what lets the plan explain itself, since the reason has somewhere to live.

Two smaller things: I made Priority and Frequency into enums instead of plain strings, because `"high"` vs `"HIGH"` is the kind of typo that would quietly break the sorting and not throw an error. And I renamed Pet's `type` to `breed`, since having `species` and `type` sitting next to each other didn't actually tell you which was which.

### Changes after reviewing the skeleton

Once I had `pawpal_system.py` written out I had AI review it for missing relationships and bottlenecks. Five things came back and I took all of them.

**4. Python's `time` can't do math, which affects almost every method.** This was the one I had no idea about. `datetime.time` is a clock reading, not an amount of time, so `time(8,0) + timedelta(minutes=30)` just raises a TypeError. I checked it myself before changing anything because it sounded wrong. But `available_minutes()`, `generate()`, and `total_minutes()` are all basically time math, so this would have been a mess spread across the whole file. I added two helpers, `to_minutes()` and `to_time()`, and now everything converts to minutes past midnight, does normal integer math, and only converts back when it's time to display something.

**5. `Frequency.ONCE` wasn't actually doing anything.** My plan was DAILY returns True always and ONCE returns True always, which are the same thing — so a "one time" task would have repeated every single day. The problem was that ONCE had no date on it to check against. I added `due_date` to Task, so now ONCE means "only on this specific date." This one bugged me because the gap was in my UML, not just the code, so the diagram was wrong too.

**6. `generate()` would have duplicated the plan every time you ran it.** It adds to `self.scheduled` but never empties it first. This matters way more in Streamlit than I expected, because Streamlit re-runs the entire script every time you click anything. So pressing Generate twice would have given me every task listed twice and I probably would have blamed the scheduler. Step 0 of the method is now clearing both lists.

**7. `describe()` would crash when a task has no pet.** `Task.pet` starts as None and only gets filled in by `Pet.add_task()`. But my tests are going to build Task objects directly without any pet, and `describe()` wants `task.pet.label()` for the display line, which would be an AttributeError on None. Now it just leaves the pet name off instead of crashing.

**8. I added a `SkippedTask` class.** I had skipped tasks stored as `(task, reason)` tuples, which meant getting a reason looked like `schedule.skipped[0][1]`. That's unreadable. It's funny because I'd already solved this exact problem with `ScheduledTask` and didn't notice I was doing the opposite thing right next to it. Now it's `skipped[0].reason`.

### Changes during implementation

Two more things changed once I was actually writing the code.

**9. I split `Scheduler` out from `Schedule`.** I'd had one class doing both jobs. But "go get all the tasks from all the pets and work out which ones count today" and "here is Monday's finished plan" are different responsibilities, and jamming them together meant I had no clean place to put things like "show me everything still pending." So `Scheduler` is the brain — it holds the owner, pulls tasks, filters them, and hands back a `Schedule`. `Schedule` is just one day's answer.

The part I had to think about was how `Scheduler` should reach the task data. The easy version is looping over `owner.pets` and then `pet.tasks` inside `Scheduler`, but that means `Scheduler` has to know how `Owner` stores pets and how `Pet` stores tasks. If either ever changes, `Scheduler` breaks. So it calls `Owner.all_tasks()` instead and lets `Owner` handle its own pets. `Scheduler` never touches `pet.tasks` directly.

**10. Tasks needed a completion status.** Adding `completed` and `mark_complete()` turned out to matter more than I expected, because the scheduler now filters completed tasks out before planning. That means ticking something off actually frees up its time and a task that got skipped earlier can fit. You can see this in the sample output in the README — marking the vet checkup done lets the nail trim in.

One thing I was careful about: a completed task is filtered out *before* planning, so it never shows up in the skipped list. "Already done" and "couldn't fit" are different things and lumping them together would have been confusing to read.

So the final count is seven classes plus two enums, not the four classes I started with. Most of the growth came from the same realization over and over: a thing, and a fact *about* that thing in one specific situation, want to be two separate objects.


---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

My scheduler works with five constraints, and the order I check them in *is* the ranking:

1. **The owner's time window.** `day_start` to `day_end`. Nothing gets planned outside it, full stop. This is first because it's the actual problem — a busy owner doesn't have unlimited hours, and a planner that ignores that is just a to-do list.
2. **Fixed times.** If a task is pinned to 8am, it happens at 8am or it doesn't happen. No negotiating.
3. **Whether it's even due today.** Daily, weekly, or a one-off on a specific date. A weekly bath shouldn't clutter up the other six days.
4. **Whether it's already done.** Ticked-off tasks come out before planning starts.
5. **Priority, then duration.** High before medium before low, and on a tie the shorter task first so more fits.

I decided the order by asking what would be *worst* to get wrong. Scheduling the cat's insulin at the wrong time is a real problem. Doing the nail trim before the walk isn't. So hard constraints that can't bend go first, and priority — which is really just a preference — comes last.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

**The big one: my scheduler is greedy, not optimal.** It walks the task list once in priority order, drops each task in the first gap big enough, and never goes back to reconsider.

That means it can leave time on the table. In the sample output in the README, "Nail trim" (25 min) gets skipped because the largest remaining gap is 15 minutes — but there was 15 minutes free *earlier* too, and a smarter algorithm could have shuffled things to make one 25-minute block. Mine doesn't look for that. Finding the genuinely best packing is a bin-packing problem, which is NP-hard, so "optimal" means either an exponential search or a real constraint solver.

I think greedy is the right call here. A pet owner has maybe ten tasks in a morning, so the difference between my answer and a perfect one is usually one small task. What you lose in packing efficiency, you gain in being able to explain yourself — every task carries a sentence saying why it landed where it did, and skipped ones say exactly what they needed and what was actually free. A perfect schedule nobody can argue with is worth less than a good one you can look at and go "oh, that's why."

**A second tradeoff: pinned always beats flexible, even when the flexible task is more important.** A low-priority task pinned to 8am will push out a high-priority flexible one if time is short. That looks wrong written down, but it's deliberate — medication at 8am isn't a preference, it's a requirement, and priority is a softer signal than a fixed time.

**A third one, about conflict detection.** `find_conflicts()` compares every pair of pinned tasks, which is O(n²). A sweep-line algorithm would be O(n log n). I kept the pairwise version because with under fifty tasks the difference is unmeasurable, and the pairwise loop is something I can read and be sure is correct. I did take one refactor here — swapping a hand-written nested loop for `itertools.combinations(pinned, 2)`, which says "every pair" in actual words instead of making you decode an index slice. That one was both shorter *and* clearer, so it was an easy yes. I turned down the sweep-line version because it was only faster in a way I'd never notice, and harder to read in a way I definitely would.

One limitation I should be honest about: conflict detection only looks at *pinned* tasks. Two flexible tasks can never conflict, because the scheduler just puts them in different gaps. But that also means the warning list doesn't tell you "your day is overbooked" — only "these two fixed appointments clash." Overbooking shows up in the skipped list instead, which works, but it's a second place to look.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

I used Claude Code in VS Code for basically the whole build. The parts that actually earned their keep:

**Agent mode with terminal access.** This was the big one. The assistant could run `pytest` and `python main.py` itself and read the real output, instead of guessing whether something worked. When I asked it to verify my Streamlit app, it found Streamlit's own `AppTest` harness and drove the actual UI — clicking buttons, filling forms — rather than just eyeballing the code. That's how we caught a bug I'd never have found by reading.

**Design conversation before any code.** Before writing a line of `pawpal_system.py` I had it ask me four questions: pinned times or not, one pet or many, recurring tasks in scope, and what the owner's constraint actually is. Those four answers determined every attribute in my UML. Doing that first meant the class design came out of decisions instead of guesses.

**Reviewing my own skeleton.** Attaching `pawpal_system.py` and asking "what's missing here" found five real problems before I'd implemented anything — including that `datetime.time` can't do arithmetic at all, which would have made a mess of basically every method.

The prompts that worked best were the ones that asked for problems rather than code. "What's wrong with this" got me much further than "write this for me." The worst prompts were vague ones like "make it better" — those produced changes I then had to evaluate from scratch.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

The clearest one is sorting. Phase 3 told me to sort my task times as `"HH:MM"` strings using a lambda key. I asked about it, and the answer was that doing it that way would be a real bug, not just an awkward style choice: string comparison goes character by character, so `"9:00"` sorts *after* `"10:00"` because `"9" > "1"`. It only appears to work if everything is zero-padded. My tasks store `datetime.time` objects, which compare properly, so I kept those and used the lambda for a different job — pushing flexible tasks to the end of the list. I wrote a test (`test_single_digit_hours_sort_before_double_digit`) specifically to pin that down.

I also turned down a suggestion that was genuinely more Pythonic. I'd asked how to simplify `find_conflicts()`, and got two options. The first replaced a hand-written nested loop with `itertools.combinations(pinned, 2)` — shorter *and* clearer, since it says "every pair" in actual words, so I took it. The second was a sweep-line algorithm to get conflict detection from O(n²) to O(n log n). I said no. With under fifty tasks the speedup is something I would never notice, and the pairwise version is one I can read and be confident is correct. Faster in a way nobody can perceive, harder to read in a way I definitely would.

How I verified things, in rough order of how much I trust them:

1. **Run it.** The time-arithmetic claim sounded wrong to me, so I had it actually execute `time(8,0) + timedelta(minutes=30)` and show me the `TypeError`. Then I believed it.
2. **Break it on purpose.** After my tests all passed first time, I was suspicious that they weren't testing anything. So I deliberately introduced four bugs into `pawpal_system.py` — weekly repeats landing the same day, touching tasks counting as overlaps, flexible tasks losing their sort position, repeats being due immediately — and ran the suite each time. All four were caught. A suite that passes proves nothing by itself.
3. **Read the output and ask if it's sensible.** The terminal output in the README is the real check. No assertion tells me whether that's a morning a person would actually follow.

The one I'd flag to anyone doing this next: the assistant wrote both my implementation and my tests, so they agree with each other by construction. If I'd misunderstood the *problem*, that misunderstanding would be sitting in both and the tests would cheerfully confirm it.

**c. Separate chat sessions**

The instructions said to open a new chat session for each phase. **I didn't do that — I ran the whole project in one continuous session.** Being honest about it because the tradeoff is real and went both ways.

What I gained: the assistant remembered every decision. When I added recurring tasks in Phase 3, it already knew why `Task` had `duration_minutes` and `fixed_time` as separate fields, and it caught that the naive "today + 1 day" approach would collide with my existing daily-task model — because it remembered that model. A fresh session would have had to re-derive that, or gotten it wrong.

What it cost: no clean separation between planning and implementing. A couple of times I was mid-implementation and wanted to think about design instead, and the conversation was already deep in test output. A separate session would have forced that reset.

If I did it again I'd split differently than the instructions suggest — not one session per phase, but one for "decide what to build" and one for "build it," since those are the two modes that actually conflict.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

I ended up with 399 tests across four files. The three behaviors I focused on hardest were sorting, recurrence, and conflict detection, because those are the three places where being wrong is *quiet* — the app still runs, it just tells you the wrong thing.

**Sorting.** The tests I care about most here aren't the obvious ones. Midnight was the big one: `time(0, 0)` is falsy in Python, so writing `if task.fixed_time:` would treat a midnight task as having no time at all and shove it to the bottom of the list. Same trap with `weekday=0` for Monday. Both of those would look fine in testing unless you specifically picked those values, so I did.

**Recurrence.** The one that would have bitten me is a weekly task completed on its own weekday. The natural way to write it is `(target - today) % 7`, which gives 0 when they match — so finishing Monday's bath would make it due again immediately, that same Monday. I test that it waits a full seven days. I also test month ends, year ends, and leap days, since that's exactly the kind of thing you assume works until it doesn't.

**Conflicts.** The distinction I wanted pinned down is touching versus overlapping. A task ending at 09:00 and another starting at 09:00 are back to back, not a clash, and getting that boundary wrong by one minute in either direction would make the app either cry wolf constantly or miss real conflicts.

**Empty states.** An owner with no pets, a pet with no tasks, a task with no pet. These are boring and they're the ones that crash real apps.

The tests also paid for themselves directly. When I refactored `find_conflicts()` to use `itertools.combinations`, all 335 tests at the time passed straight away, which is the only reason I was willing to touch working code at all.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

**About 4 out of 5.** Confident, not certain.

What makes me confident is that I checked the tests themselves rather than just trusting a green bar. I deliberately broke four things in `pawpal_system.py` — made weekly repeats land the same day, made touching tasks count as overlapping, dropped the flexible-last rule from the sort key, and let repeats be due immediately — and ran the suite each time. All four got caught. A test suite that passes tells you nothing on its own; one that fails when you break the code is actually doing something.

What stops it being a 5 is that I wrote the code and the tests, so they agree with each other by construction. If I misunderstood the *problem* rather than the code, that misunderstanding is sitting in both and the tests would cheerfully confirm it. The thing that actually catches that is reading the terminal output in the README and asking "is that a sensible morning?" — and that's me looking at it, not an assertion.

If I had more time, in order:

1. **A real week.** Run it against an actual schedule for seven days and see if the plans are ones a person would follow.
2. **Daylight saving.** I store times as wall-clock `time` objects with no timezone, so the day the clocks change, an hour either vanishes or happens twice. Completely untested.
3. **Volume.** Everything is tested with under ten tasks. The conflict check compares every pair, so a hundred tasks is ten thousand comparisons — fine, but I don't actually know where it stops feeling instant.
4. **Deliberately nasty input.** A 480-minute task in a 30-minute day, a task pinned to 23:59, every task at the same time.
5. **Whether the greedy packing is good enough in practice.** I know it isn't optimal. I don't know how often that costs a real person a real task.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

The explanations. Every scheduled task carries a sentence saying why it landed where it did, and every skipped one says exactly what it needed and what was actually free. That turned out to matter more than I expected, because the scheduler does things that look wrong at first glance. In my sample output a *medium* priority task is scheduled before a *high* priority one, and without the reason column I'd have assumed the sorting was broken. With it, you can see the walk needed 30 minutes and only 25 were free, so the shorter task backfilled the gap. The app can defend itself.

I'm also pleased with how splitting `Task` from `ScheduledTask` worked out. It felt like extra ceremony when I added it. It stopped being ceremony the moment plans needed regenerating, because the task list never gets corrupted by yesterday's answer.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**Completion should be per-day, not a boolean.** This is the thing I'd redo first. Right now `completed` is `True`/`False`, which means finishing a daily task required creating a whole new copy of it stamped with a start date. It works, and it's tested, but a pet's task list fills up with completed duplicates — seven days of feeding is seven objects. If `Task` stored `completed_on` as a set of dates instead, one daily task would just be one object that knows which days it's been done. Smaller, and it makes "show me last week" possible, which right now it isn't really.

**The greedy packing.** It isn't optimal and I know exactly where it loses: it never reconsiders a placement. In my demo "Nail trim" gets skipped for want of 25 minutes when there were two separate 15-minute gaps that a smarter arrangement could have merged. I'd want to at least measure how often that costs a real task before deciding whether it's worth fixing.

**Timezones.** I store wall-clock times with no date attached, so the day the clocks change, an hour either disappears or happens twice. Completely untested and I'd guess completely broken.

**Editing tasks.** You can add and complete, but not edit. Getting a duration wrong means deleting and re-adding, and there isn't even a delete.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

That the useful thing I bring isn't writing code — it's deciding what's true about the problem.

The clearest case was recurring tasks. The instructions said to calculate the next due date as "today + 1 day." That's correct arithmetic and completely wrong for my system, because in my model a daily task is *already* due every day — so creating a copy for tomorrow would have put two identical tasks in the same day's plan. The code would have run. The tests I'd have written for it would have passed. It would just have told the owner to feed the cat twice.

Nothing about that is a coding problem. It's a question about what "daily" means in my model, and the only person who could answer it was me, because I'm the one who decided what `is_due_on()` returns. The assistant could write the fix in seconds once the question was settled — the `starts_on` field — but it couldn't settle it.

That's what "lead architect" turned out to mean in practice. The AI is faster than me at everything except knowing which question is the real one. It will happily and competently build whatever I describe, including the wrong thing, and it'll be well-structured and tested and wrong. So the job is holding onto the model in my head and checking each suggestion against it — not reviewing the syntax, but asking "does this match what I decided this system is?"

The habit I'll keep is making it prove things instead of asserting them. When it told me `datetime.time` can't do arithmetic, I had it run the code and show me the `TypeError` before I believed it. When my tests all passed first try, I had it deliberately break the source to check the tests could fail at all. Both times the claim held up. But I only know that because I checked, and checking cost about thirty seconds each time.
