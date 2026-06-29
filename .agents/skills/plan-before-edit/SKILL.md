---
name: plan-before-edit
description: Instructs the agent to always outline an implementation plan and wait for user approval before making any code modifications.
---

# Plan Before Editing Code

Before performing any code modifications or running commands that write to files, you **MUST**:
1. Draft a structured markdown plan outlining the intended changes.
2. Highlight which files will be modified, what code changes will be made, and any risks or impacts.
3. Explicitly ask for the user's review and approval.
4. Stop calling tools and wait for the user to reply and authorize the plan before writing any code.
