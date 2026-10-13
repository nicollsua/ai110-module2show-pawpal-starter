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


---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
