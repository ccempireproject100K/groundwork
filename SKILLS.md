# SKILLS.md — Agent Skills Equipped for Work in This Repo

Owner standing rule (2026-10-31): the screened free GitHub agent skills are
equipped to every crew and carried in each repo the crews work in. This
manifest lists which skills apply to work in the Groundwork repo, with
license and provenance. The full skill texts live in the operator's central
library (`~/workspace/custom-skills/`); the screening record behind every
verdict is `~/workspace/empire-bots/SKILLS_SCREENING.md` (2026-10-30/31).

**Discipline:** only ADOPT-verdict skills are ever copied anywhere, and only
as recorded below. ADAPT-verdict skills are method references only — their
text is never copied into this repo or any product. REJECT and UNVERIFIED
skills never enter a repo.

## Adopted general skills (ADOPT verdicts — available to all crews)

| Skill | Source | License | Use in this repo |
|---|---|---|---|
| skill-creator | anthropics/skills (`skills/skill-creator/`) | Apache-2.0 (folder LICENSE.txt verified in screening) | Method for creating and eval-testing new agent skills (baselines, assertions, benchmarks) — the method for maintaining this repo's own project skills in `.grok/skills/`. Full text: `~/workspace/custom-skills/skill-creator/` (PROVENANCE.md there). |
| mcp-builder | anthropics/skills (`skills/mcp-builder/`) | Apache-2.0 (folder LICENSE.txt verified in screening) | Four-phase guide for building MCP servers/connectors — reference if this app's API is ever exposed as MCP tools. Full text: `~/workspace/custom-skills/mcp-builder/` (PROVENANCE.md there). |
| changelog-generator | ComposioHQ/awesome-claude-skills (`changelog-generator/`) | ADOPT verdict in screening; source README claims Apache-2.0, the folder carries no license file of its own (caveat recorded in its PROVENANCE.md) | Turns this repo's commit history into categorized, member-language release notes. Full text: `~/workspace/custom-skills/changelog-generator/`. |

## The empire's own learned skills relevant to this work

Home-grown skills from the operator's library (`~/workspace/custom-skills/`),
written from the empire's own operating history — no external license
involved:

| Skill | Why it applies here |
|---|---|
| coverage_census_before_complete | Census discipline before calling any feature set "complete" — matches this repo's registry-as-source-of-truth rule (49 entries / 48 modules); enumerate the universe independently and recount before reporting. |
| scope_stage_decision_readback | Read back scope/staging decisions before consequential steps — build, ship and deploy are separate authorizations; nothing deploys from this tree without the owner's word. |
| post_merge_deploy_verification | After any merge/deploy, verify the live state rather than trusting the merge/deploy call. |
| secondary_surface_leak_audit | This app holds sensitive member data (anonymous posts, the author-only crisis inbox, the encrypted document vault): audit every surface that could expose author identity, phone numbers or vault content before calling work done. |
| github_target_verification | Confirm the exact GitHub owner/repo before any large build or port, and verify every push landed from commit history before reporting it. |

## Project skills (already in this repo, not part of the screened set)

`.grok/skills/` holds the project's own skills — reentry-checklist,
recovery-moderation, milestone-merch, sober-venue-web, course-generation,
journey-portfolio, ai-matcher, mood-filters and venue-threejs. They are the
build methods for this app's features and stay governed by `AGENTS.md`.

## Explicitly NOT carried here

- ADAPT-verdict skills (e.g. lead-research-assistant, article-extractor,
  content-research-writer, invoice-organizer, file-organizer,
  competitive-ads-extractor, doc-coauthoring): method references only, held
  in the operator's screening record — never copied into this repo.
- REJECT-verdict skills (including Anthropic's proprietary docx/pdf/pptx/xlsx
  skills and all auto-send/credentialed-vendor templates) and everything in
  the screening's UNVERIFIED pile: never used, never copied.

*Manifest added 2026-11-01 with the Groundwork build-out (snapshot of
Brandonk318/groundwork @ 75362a7).*
