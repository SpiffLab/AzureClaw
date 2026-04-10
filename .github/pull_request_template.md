<!--
Thanks for contributing to AzureClaw!

Every meaningful change should be backed by an OpenSpec change folder under
`openspec/changes/<name>/`. If your PR is implementing a proposed change,
link the change folder below so reviewers can compare the implementation
against the spec.
-->

## OpenSpec change

Implements: `openspec/changes/<change-name>/`

<!-- If this PR is a chore, infra tweak, or doc fix that does not warrant a full
     OpenSpec change, delete the line above and explain why here. -->

## Summary

<!-- 1-3 bullets describing what changed and why. -->

-
-

## Test plan

- [ ] `uv run ruff check src tests`
- [ ] `uv run ruff format --check src tests`
- [ ] `uv run pyright`
- [ ] `uv run pytest -m local`
- [ ] (if `infra/` changed) `bicep build infra/main.bicep` is clean and the `bicep-what-if` PR comment looks correct
- [ ] (if a new spec scenario was added) the corresponding test exists and is run by `pytest -m local`

## Reviewer checklist

- [ ] PR matches the linked OpenSpec change's scope (no scope creep)
- [ ] No secrets or credentials in source
- [ ] No unauthorized destructive infra changes in `bicep-what-if`
- [ ] `openspec/project.md` updated if architectural decisions changed

## Notes / follow-ups

<!-- Anything reviewers should know that does not fit above. -->
