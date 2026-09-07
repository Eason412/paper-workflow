# Paper Workflow maintenance

This repository contains two independently installable Skills under `skills/`.

- Paper acquisition changes: read `skills/oa-paper-fetch/AGENTS.md`; its contracts apply only within that Skill. Keep its English and Chinese READMEs equivalent.
- Report rendering changes: read `skills/md-course-report-to-pdf/SKILL.md` and the relevant format QA reference. Use temporary reports for verification.
- Root documentation and CI describe installation, navigation and repository maintenance; runtime behavior belongs to each Skill.

Preserve independent script entrypoints and full install payloads. Do not make either Skill import its sibling or depend on the repository root at runtime. Run test suites in separate processes from the corresponding Skill directory.

Do not inspect institutional profiles, export cookies, automate credentials, or start downloads/login flows merely to test repository changes. Keep generated PDFs, user reports, browser sessions and credentials outside Git. Use offline fixtures for downloader tests; report actual PDF compilation separately from static checks.

For parallel work, assign disjoint Skill directories and reserve root integration files for the coordinating agent. Preserve unrelated edits. Only publish, rename or delete remote repositories within the user's explicit scope; destructive actions require an impact summary and confirmation.

Use a GitHub noreply email for new commits. Preserve original license notices and third-party attributions.
