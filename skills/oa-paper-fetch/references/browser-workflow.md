# Interactive publisher browser workflow

Read this only when a user-authenticated browser session is the chosen route
for entitled papers. The CLI backend has its own isolated Playwright profile;
Chrome's existing login does not transfer to it. Do not point Playwright at the
ordinary Chrome default profile or copy/export cookies, storage state, tokens,
or profile data to bridge the two. If browser access is missing, use the
visible-login procedure in `SKILL.md` for the isolated profile, or stop at a
login/challenge boundary.

1. Freeze the requested journal/issue or reference-list subset and make a
   stable identity list. Match against existing PDFs and resume records before
   opening tabs. Restrict publisher pages and resulting PDF requests to IEEE
   Xplore, Wiley Online Library, and Elsevier ScienceDirect, after OA-first
   checks. One agent owns each platform's tabs and downloads; offline agents
   may verify identities and outputs without controlling those tabs.
2. Open one article, confirm its publisher title against the intended DOI/title
   and entitlement, then use the site's visible View PDF/Download PDF flow.
   A View PDF click may open a new PDF tab before a separate browser download.
   Wait for that page or for a download event, then invoke its normal download
   control and save into the requested destination. Do not substitute a media
   or direct HTTP fetch when it yields an HTML viewer, or comb hidden browser
   temporary files for a PDF.
   `not_pdf_browser_download_required` means the direct publisher request
   returned ordinary HTML after challenge detection; it is a handoff to this
   visible flow, not a completed download or a request to reauthenticate. With
   existing authorization, try the normal View PDF path once in the same
   signed-in session and verify the result before continuing.
   Select these rows from `oa_fetch_results.json` by `institutional.error`:
   the CLI records them as `failed`, not in `oa_fetch_pending.csv`. Preserve
   their DOI/URL and unresolved status until a saved PDF passes verification;
   record the browser outcome without overwriting the CLI recovery state.
3. With Playwright-controlled pages, register `page.expect_download()` around
   the action initiating the attachment and persist with `download.save_as()`;
   use `page.expect_popup()` for a new PDF tab, then watch that tab's download
   action. A browser tool may provide its own equivalent download facility;
   use its documented operations. Verify a real PDF and the matched identity
   before recording success. Playwright deletes its temporary downloads when
   the context closes, so save explicitly; `page.pdf()` merely prints the web
   page and is not the publisher's paper.
   This describes the interactive Playwright/browser route; the current CLI
   backend does not implement `expect_download()` and must not be presented as
   if this handoff were automatic.
4. Close only the tabs opened for the task after saving each paper. Continue
   serially at the authorized pace; give unresolved papers a specific reason
   without cycling through the same failed mechanism. Stop on login expiry,
   identity mismatch, payment barrier, or anti-bot challenge. Do not automate
   authentication or bypass a guard.

Use a base delay of at least 4 seconds, jitter within 0--10 seconds, and at
most 30 institutional attempts per run across both routes. The CLI enforces
these limits; count interactive attempts explicitly, including earlier CLI
attempts in the same run. Switching routes does not reset the count. When the
user requests at least 3 seconds between papers, use the more conservative
4-second minimum without another confirmation. Keep browser retrieval within
the requested subset; do not turn a one-run pace into a standing preference.

Playwright source documentation: [downloads and save_as](https://playwright.dev/python/docs/downloads),
[popup pages](https://playwright.dev/python/docs/pages), and
[isolated/persistent browser profiles](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context).
