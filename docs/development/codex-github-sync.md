# Forest Keeper — Codex ↔ GitHub synchronization

## Source of truth
GitHub repository `SergeyRassohin/Forest-Keeper` is the single engineering source of truth for Forest Keeper.

Codex must work against this repository rather than maintain an independent copy of project knowledge.

## Required workflow
Before starting work in Codex:
1. open the local Forest Keeper repository;
2. fetch/pull the current default branch;
3. read `AGENTS.md` and the referenced project documentation;
4. resolve any local-vs-remote divergence before making new changes.

After completing a coherent unit of work:
1. save changes in the local repository;
2. review the diff;
3. run the relevant tests/checks;
4. commit with a meaningful message;
5. push to GitHub.

This creates the synchronization loop:

`GitHub → pull → Codex/local repo → edit/test → commit → push → GitHub`

## What must live in Git
Version-control all durable project knowledge and implementation artifacts, including:
- application/source code;
- site source;
- database migrations;
- rules and configuration;
- data-model definitions;
- connectors/adapters;
- tests;
- architecture;
- requirements;
- interface specifications;
- security and testing documentation;
- decision logs;
- deployment instructions;
- Project Portal/index material.

Do not rely on chat history as the only copy of an accepted requirement or decision.

## ChatGPT role
ChatGPT may help recover context from earlier discussions, write/update documentation, review changes and commit text artifacts to the repository. When a discussion changes a project decision, that decision should be written to the repository, preferably in `docs/decisions/decision-log.md` and the relevant canonical document.

## Codex role
Codex implements and edits the checked-out repository. Codex should treat `AGENTS.md` as the entry point and Git history as the engineering history.

## Conflict rule
If local Codex files and GitHub differ, do not silently overwrite either side. Compare changes first and preserve intentional work. The newest explicit accepted decision in `docs/decisions/decision-log.md` has precedence over older prose when documents conflict.

## Practical rule for this project
A change is not considered safely transferred from chat into the project until it exists in GitHub.

A Codex change is not considered synchronized until it has been pushed to GitHub.
