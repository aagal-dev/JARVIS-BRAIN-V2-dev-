Agent Instructions

This file is the source of truth for any coding agent (Claude Code, Cursor, Codex, OpenCode, etc.) working in this repository.

Core Principle

Understand → Adapt → Implement → Verify

The repository is the primary specification for its architecture, structure, conventions, naming, patterns, and coding style.

Adapt to the project. Do not impose your own.

Before changing code, inspect the relevant repository context and derive:

- Architecture, subsystems, and data flow.
- Folder/file responsibilities and placement patterns.
- Naming conventions.
- Module boundaries and import/dependency patterns.
- Configuration and integration patterns.
- Error-handling and validation practices.
- Testing, typing, formatting, and documentation conventions.
- Existing implementations analogous to the requested change.

Study repeated patterns, especially in the affected subsystem. Nearby and analogous code is stronger evidence than generic "best practices."

Do not guess how unfamiliar code works when the repository can answer it.

Project Adaptation

Make new code look and behave like native project code.

Follow existing conventions for:

- File/folder structure and placement.
- Names and terminology.
- Abstraction level.
- Module organization.
- Configuration.
- Dependencies.
- Error handling.
- Tests and verification.
- Documentation and style.

Reuse an existing project pattern when applicable. Do not create a second pattern for something the project already knows how to do.

Do not rename, reorganize, or "clean up" existing code just because another style seems better.

Repository evidence beats agent assumptions.

Scope and Non-Invention

Implement the requested change and nothing unrelated.

Do not invent requirements, APIs, interfaces, abstractions, compatibility layers, configuration systems, feature flags, subsystems, file structures, or behavior that was not requested or observed.

Before modifying behavior, identify the existing contract and affected dependencies.

Preserve existing behavior unless the task explicitly requires changing it.

If the existing architecture can support the task, do not redesign it.

Minimal Change

Make the smallest coherent change that fully solves the problem.

Prefer:

- Existing files over unnecessary new ones.
- Existing utilities over duplicates.
- Existing abstractions over new ones.
- Existing dependencies over new ones.
- Existing patterns over new ones.
- Direct solutions over unnecessary indirection.

Do not bundle unrelated refactors, optimizations, migrations, style changes, renames, reorganizations, or upgrades.

When fixing bugs, address the root cause rather than masking the symptom.

Anti-Overengineering

Prefer simple, explicit, readable code.

- Small, obvious functions.
- Straightforward control flow.
- Clear names.
- Focused modules.
- Explicit behavior.
- No premature abstraction.
- No speculative extensibility.
- No unnecessary inheritance or framework layers.
- No hidden magic.
- No abstraction whose main purpose is to look "architected."

Three similar lines can be better than a bad abstraction. Extract only when a concrete repeated need or existing project pattern justifies it.

A simple function is preferable to a multi-class design when both solve the same problem.

Dependencies

Default to the standard library/platform and existing project dependencies.

Every dependency adds maintenance, upgrade, transitive-dependency, and supply-chain cost.

Add a dependency only when it is already part of the stack, required by an external system, or provides substantial/error-prone functionality that is unreasonable to implement locally.

Do not add libraries merely for convenience or nicer APIs.

Configuration

Follow the repository's existing configuration architecture.

Keep configuration centralized and explicit. Do not scatter environment-variable access or configuration loading through application modules.

If a central settings/configuration layer exists, use it.

Do not introduce a second configuration mechanism.

Required configuration should fail clearly rather than silently falling back to incorrect behavior.

Boundaries and Errors

Treat external systems and genuinely untrusted boundaries carefully:

- User/external input.
- APIs/network responses.
- Databases.
- Files.
- Parsed or untrusted content.
- Third-party services.

Validate and handle failures at those boundaries.

Do not add defensive handling for impossible internal states when existing contracts make them safe.

Do not catch, suppress, or transform errors without a concrete reason.

Do not hide failures merely to make execution appear successful.

File Placement and Naming

Do not create or move files based on personal preference.

Determine placement and naming from analogous files and the responsibilities of existing folders/modules.

Match the project's terminology, singular/plural rules, prefixes/suffixes, class/function names, and filename conventions.

Avoid introducing synonyms for concepts that already have established project names.

Do not create new directories unless the existing structure clearly calls for one or the task genuinely requires it.

Comments and Documentation

Explain why, not what obvious code already does.

Comment only when behavior is non-obvious, constrained, or intentionally unusual.

Follow the repository's documentation style. Remove stale TODOs when encountered as part of the relevant change.

Do not rewrite unrelated documentation.

Testing and Verification

Verify the change using the repository's existing mechanisms.

Run the most relevant tests and checks, and exercise the affected path when practical.

Use targeted verification first, then broader checks where appropriate.

Do not claim success without verification.

If verification cannot be performed, state exactly what was and was not verified.

Do not change tests merely to make an incorrect implementation pass.

Decision Rules

When uncertain:

1. Inspect the repository.
2. Find analogous code.
3. Determine the local pattern.
4. Follow that pattern.
5. Choose the smallest consistent solution.
6. Verify it.

Do not resolve uncertainty by inventing architecture or rewriting surrounding code.

Final Check

Before completing a task, ensure:

- The code matches local style and conventions.
- Names and file placement match existing patterns.
- Existing utilities/patterns are reused where appropriate.
- No unnecessary dependencies or abstractions were added.
- No unrelated behavior or code was changed.
- The requested problem is fully solved.
- Relevant verification was performed.

General Principle

The agent adapts to the project; the project does not adapt to the agent.

Optimize for:

Correct → Consistent → Simple → Explicit → Maintainable

Avoid unnecessary complexity, abstraction, dependency, refactoring, and speculative engineering.