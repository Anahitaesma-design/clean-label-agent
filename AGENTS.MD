# Clean Label Agent - Coding Rules

To ensure a successful and conflict-free collaboration on the Clean Label Agent project, all AI coding agents must strictly adhere to the following rules:

1. **Think Before Coding**: Analyze the task, understand the context and implications, and review existing files before making any modifications.
2. **Surgical Edits Only**: Make minimal, precise, and surgical edits to only the specific files required for the task. Avoid unnecessary code changes or refactoring of unrelated code.
3. **Strict Directory Boundaries**:
   - You must never modify files outside the directory/files assigned for the current task.
   - Respect file-ownership:
     - Lead files (edited only by the Lead agent): `src/agent.py`, `src/tools/mcp_client.py`, `src/observability/tracer.py`, `specs/clean-label.yaml`, `Dockerfile`, `AGENTS.MD`, `README.md`.
     - Specialist files (edited only by Ali's agent): `src/agents/toxicology.py`, `src/ui/report_card.py`, `src/checkpoints/vibe_diff.py`, `src/commerce/safer_alt.py`, `skills/**/*.md`, `tests/**/*.py`.
4. **Test-Driven Development (TDD)**: Treat tests and BDD specifications as primary requirements. Write/review tests before writing the implementation, and verify all changes using the test suite.
5. **Source of Truth**: The hybrid Gherkin specification at `specs/clean-label.yaml` is the single source of truth for the agent's behavior. Any implementation details must align exactly with the scenarios defined in this spec.
6. **Documentation and Comments**: Code must contain clear comments pertinent to implementation, design, and behavior (this is a graded criterion). Maintain all existing docstrings and comments. Document new functions with clear, descriptive docstrings.

