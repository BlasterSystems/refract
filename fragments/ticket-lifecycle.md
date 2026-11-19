## 9. Ticket lifecycle

Work is tracked in the project's issue tracker: task identifiers use the `{{TICKET_PREFIX}}-<number>` convention. **Status transitions are part of the definition of done: a ticket is never left in a state that contradicts the code.**

1. **Fetch** the ticket (description + acceptance criteria) before implementing anything.
2. **Before coding**: transition the ticket to "In Progress" and assign yourself; record the assignment in the ticket.
3. **Plan** in `tasks/<TICKET>.md` from `tasks/task-template.md`; keep it updated with decisions, evidence, and residual risks as the work progresses.
4. **Deliver — always via pull request**: push a branch and open a PR whose title references the ticket and whose body links the ticket and the task file. Direct pushes to the default branch are a process violation — including fixes, hotfixes, docs, and process changes themselves.
5. **On merge — mandatory status update**: transition the ticket to "Done" and post an evidence comment (commands run + observed results). This step is blocking: merging without the status update is a process violation, not optional cleanup.
6. **Multi-ticket changes**: a PR that covers several tickets (e.g. an epic landing its child stories) reconciles every covered ticket's status in the same pass — including epics and parents whose state the change completes. A ticket whose feature is only partially delivered stays "In Progress" with a comment naming the remainder.
7. **Reconciliation**: when work lands at a coarser grain than the tickets describe (an epic PR implementing many stories), verify each covered ticket against the actual code before transitioning it; tickets whose feature is genuinely absent stay open and become the next work items, not silent "Done"s.
