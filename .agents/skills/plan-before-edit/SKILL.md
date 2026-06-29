---
name: plan-before-edit
description: Instructs the agent to always outline an implementation plan and wait for user approval before making any code modifications.
---

# Plan Before Editing Code

Before performing any code modifications or running commands that write to files, you **MUST**:
1. Draft a structured markdown plan outlining the intended changes.
2. Highlight which files will be modified, what code changes will be made, and any risks or impacts.
3. Explain in detail what the code does, where the functions are called, the purpose of each function, why they were introduced, and analyze their internal logic.
4. Verify and test the proposed implementation details at least 2 times (e.g., by executing unit tests, dry-running, or reviewing edge cases) before proposing it to the user.
5. Explicitly ask for the user's review and approval.
6. Stop calling tools and wait for the user to reply and authorize the plan before writing any code.
