# mWP — Minimum Wowable Product

> "Ship minimum wowable product, not MVP. Target 5-7 on the 11-star scale."

## The Problem with MVP

MVP (Minimum Viable Product) is a lie we tell ourselves. "Viable" means "barely works." You ship something functional but forgettable, tell yourself you'll iterate, and wonder why nobody cares.

The marketplace doesn't reward viability. It rewards **wow**.

## The 11-Star Scale

Borrowed from Brian Chesky (Airbnb) and adapted for engineering products:

| Stars | What it feels like | Example |
|-------|-------------------|---------|
| 1-2 | Broken. Embarrassing. | CLI crashes on first command. |
| 3-4 | Works. Nobody cares. | Another auto-poster. Another code review tool. |
| **5-6** | **"Oh, that's clever."** | Plugin system that auto-discovers. |
| **7-8** | **"I need this."** | Autonomous storyteller that notices your work without asking. |
| 9-10 | "This changes how I work." | Your engineering output becomes your content. Zero clicks. |
| 11 | "I can't stop telling people about this." | The system ships, tells the story, and builds your audience while you sleep. |

**mWP ships at 5-7.** Not 3-4 (forgettable MVP). Not 9-10 (takes too long). The sweet spot where someone sees it and thinks "I need this" — because it does something they didn't know was possible.

## mWP vs MVP

| | MVP | mWP |
|---|-----|-----|
| Goal | Validate the idea | Make people want the idea |
| Bar | Functional | Memorable |
| Question answered | "Does this work?" | "Would I tell a friend about this?" |
| User reaction | "OK." | "Wait, it does WHAT?" |
| Timeline | As fast as possible | As fast as possible WITH the wow |
| Risk | Nobody cares | Some people don't care, the right people love it |

## How We Apply mWP at Maggy

Every feature must clear the 5-star bar before shipping:

**Build-in-Public Plugin — 7/11 stars**
- MVP version: "It auto-posts when you merge a PR." (3 stars. Forgettable. A dozen tools do this.)
- mWP version: "It notices meaningful work, extracts the narrative arc, redacts sensitive names, formats per channel voice, schedules intelligently, and generates a full editorial calendar — without a single click." (7 stars. Nobody else does this.)
- What made it mWP: The ContentStrategy engine deciding thread vs single vs series. The multi-channel voice differentiation. The zero-click autonomy. Not "an auto-poster." An autonomous storyteller.

**Mnemos Memory — 8/11 stars**
- MVP version: "It saves context before compaction." (4 stars. Nice, but Claude Code does this.)
- mWP version: "Typed memory nodes with per-type eviction policies. 4-dimension fatigue model that triggers consolidation BEFORE death spirals. Re-read ratio as leading indicator. Fully auditable on disk." (8 stars. Fundamentally different architecture.)
- What made it mWP: The fatigue surface. The typed eviction. The pre-compaction checkpoint. Not "context saving." Memory lifecycle.

**9-Tier Model Routing — 6/11 stars**
- MVP version: "Pick the cheapest model that can do the job." (3 stars. Cost optimization is table stakes.)
- mWP version: "QWEN classifies every prompt. Cascading fallback through kimi → deepseek if the classifier fails. Per-channel delegation scripts in ~/bin/. The system knows when it needs Claude (architecture) vs DeepSeek (features) vs Gemini (research)." (6 stars. Clever architecture, not just cost-cutting.)
- What made it mWP: The delegation pattern. The cascade. The project-aware routing. Not "cheapest model." Right model.

## The mWP Design Checklist

Before shipping, ask:

1. **Would I tell a friend about this?** If not, it's not at 5.
2. **Is there ONE thing that makes someone say "wait, it does WHAT?"** Find it. Ship that.
3. **If I stripped it down to just the wow, does it still work?** Yes → ship. No → you're shipping complexity, not wow.
4. **Does it do something nobody else thought to do?** That's the moat. Functionality is replicable. Insight isn't.
5. **Can someone explain it in one sentence and make the other person curious?** If it takes a paragraph, you haven't found the wow yet.

## Anti-Patterns

- **"We'll add the wow later."** No you won't. The wow is the product. Ship without it and you ship nothing.
- **"It needs to be perfect first."** 5-7, not 11. Done and wow > perfect and late.
- **"MVP first, then polish."** MVP ships at 3. Nobody comes back to see your polish.
- **"The wow is in the V2."** Nobody uses V1 long enough to see V2.

## Origins

This philosophy emerged from building Maggy and Claude Bootstrap. We shipped 96 files across 14 commits in one day — but every commit added something that made you stop and think "that's different." Not "that works." Different.

The 11-star scale comes from Airbnb's design philosophy. The mWP framing is ours — a recognition that in AI tools, viability is table stakes and wow is the only thing that matters.
