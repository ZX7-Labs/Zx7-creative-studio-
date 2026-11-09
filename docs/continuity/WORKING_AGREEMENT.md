# How to work on ZX7 Creative Studio

ZX7 is one local-first creative workspace for the work of a multidisciplinary studio. A replaceable AI chooses original creative direction and uses native tools to author, inspect, revise, preserve, and deliver editable projects. Motion design, graphics, ads, video, CGI, VFX, and sound are examples of its range. The [capability and acceptance contract](../../CAPABILITIES.md) defines the full scope. The [engineering standard](../../ENGINEERING_STANDARD.md) sets the quality bar. The [status page](STATUS.md) records the current evidence and priorities.

## Make and verify decisions

1. Recover the actual state. Confirm the repository and branch, protect local edits, then check the relevant source, open PRs, commits, run conclusions, and artifacts. Use repository evidence to resume when earlier chats are unavailable. Read more background when it can change a decision.
2. Pick the next dependency that unlocks a real creative workflow. Define what the user must be able to do, what evidence would count, and what would falsify the approach. Complete one field to its acceptance bar before broadening development. Keep the full studio goal in view.
3. For consequential choices, compare a simple baseline and credible alternatives using primary research, upstream code, licenses, and equivalent workloads. Measure quality, correctness, fidelity, performance, cost, and recovery where they matter. Explain the decisive tradeoff and any unresolved assumption.
4. Work through the normal entry point. Reuse capable pinned engines and preserve native editable state, source custody, existing integrations, and recovery. Reproduce failures and fix the responsible layer. Use isolated branches, scoped permissions, bounded retries, and clear checkpoints. Never automatically replay a write with an uncertain outcome.
5. Verify the resulting behavior. Use focused tests, real installed tools, decoded media, saved project inspection, and restart or failure checks when relevant. Separate implementation, scripted integration evidence, actual model autonomy, and independent artistic evaluation. Record the exact source, model, inputs, outcomes, and limitations. Keep negative results.
6. Use parallel agents when tasks can genuinely run independently. Give each a question, scope, allowed writes, and evidence to return. Keep one integration owner. Assign a skeptical reviewer or evaluator when the failure risk warrants it and independently inspect its findings before integrating changes.

The owner delegates routine research, architecture, implementation, testing, and authorized repository delivery. Make reversible choices directly. Ask only when a missing decision or authority materially blocks progress. Respect the latest pause or scope change. Keep owner media, rights, credentials, and paid services within their explicit boundaries. Preserve the free, open-source, self-hostable runtime.

## Start and end a session

Use the [resume prompt](RESUME_PROMPT.md) in a fresh chat. A useful engineering prompt states the goal, constraints, where to recover state, what success must demonstrate, and what decisions the agent owns. Plain headings and paths are sufficient. Keep durable requirements in the repository and put changing facts in the status page. Replace that snapshot at a meaningful checkpoint rather than adding a diary. Leave a verified baseline, exact links to work in progress, unresolved failures, and the next useful check.

The Anthropic reference means applying published engineering methods, including resumable checkpoints and independent evaluation against a concrete contract. Scope the planning and reviewer roles to the risk. [Long-running agent harnesses](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents) · [Harness design for long-running applications](https://www.anthropic.com/research/harness-design-long-running-apps)

For GPT-6, concise instructions in `AGENTS.md`, task-specific references, clear authority, and observable completion criteria give a fresh session the information it needs to take initiative. [OpenAI GPT-6 guidance](https://developers.openai.com/api/docs/guides/latest-model) · [OpenAI guidance on repository prompts](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
