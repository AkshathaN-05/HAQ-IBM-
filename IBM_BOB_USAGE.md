
# How we used IBM Bob in HAQ

> **Before submitting:** do the four Bob tasks in `docs/BOB_GUIDE.md`, then replace every **[bracket]** below with what Bob actually did, and fill in the session log at the bottom. Delete this note when done.

IBM Bob is an AI helper that works inside the code editor. We used it as a partner while building and checking HAQ, our app that helps informal workers get the wages they earned. HAQ has three main parts: a React app that runs in a phone browser, a Python (FastAPI) server, and a SQLite database. It also has an optional IBM Granite step that helps write the complaint letter.

## 1. Understanding the code (Ask mode)

Before changing anything, we used Bob's Ask mode to walk through the whole project. Ask mode only explains and does not change code, so it was safe to use first. We asked Bob how a request travels from the app to the database, where login and user roles are checked, and how a claim moves from "Draft" to "Sent" to "Resolved".

Bob explained **[one thing Bob explained that helped you]**. This mattered because HAQ handles workers' money and private proof, so we needed to understand the safety rules before touching them.

## 2. Checking the code for problems (/review)

We used Bob's code review on the most sensitive parts of HAQ:

- login and accounts: `backend/app/routes_auth.py`, `backend/app/security.py`
- file uploads (photos, PDFs, voice notes): `backend/app/evidence_files.py`
- employer actions: `backend/app/routes_employer.py`

Bob pointed out **[Bob's main findings]**. We fixed **[what you fixed]** and ran all the tests again after every fix. We checked each suggestion ourselves and kept only the ones that made sense for HAQ.

## 3. Writing tests (Code mode)

Tests are small automatic checks that make sure the app keeps working. We used Bob's Code mode to add a test for a real gap: **[test name]**. Bob wrote the test, we ran the full suite with `test.bat`, and it passed.

## 4. Planning what to build next (Plan mode)

We used Plan mode to design upgrades before writing any code. Bob planned how to move evidence files to IBM Cloud Object Storage while keeping every file private, listing the files to change, possible problems and the tests needed. **[Paste or link Bob's plan here.]**

## 5. Keeping private data safe

HAQ stores sensitive information: workers' names, phone numbers, payment screenshots and voice notes. Our `.bobignore` file makes sure Bob never reads the `.env` file (secret keys) or the folder with uploaded proof. We reviewed every change Bob suggested before accepting it, so a person always made the final decision.

## Other IBM technology: IBM Granite

HAQ is designed to use IBM Granite AI for one small job: writing the "What happened" part of the complaint letter in the worker's own language. Granite can run online through IBM watsonx.ai, or for free on a laptop through Ollama. HAQ checks every answer: if Granite mentions any amount or date the worker never gave, the answer is thrown away and a simple template is used instead. All money is calculated by normal code, never by AI. (Code: `backend/app/ai/`.)

## Session log

| # | Date | Bob mode | What we asked | What Bob produced | Kept? | Files changed | `test.bat` after |
|---|---|---|---|---|---|---|---|
| 1 | | Ask | | | | — | — |
| 2 | | /review | | | | | |
| 3 | | Code | | | | | |
| 4 | | Plan | | | | — | — |
