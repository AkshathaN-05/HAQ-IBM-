# HAQ — Demo Script (about 7 minutes)

## Before you start

1. `start.bat` running; open http://localhost:8000.
2. Use **two browser windows**: a normal window for the worker and a private/incognito window for the employer (sessions are per tab).
3. Optional shortcut: run `demo.bat` beforehand. It creates:
   - Worker `demo.worker@haq.example` / `DemoWorker123`
   - Employer `demo.employer@haq.example` / `DemoEmployer123`
   - A **DEMO** draft claim (all names start with "DEMO", so nobody mistakes it for real data).
4. Have two small files ready, e.g. `e2e/samples/chat.txt` and `e2e/samples/receipt.pdf`.
5. Shrink the window to phone width (or use the browser's device toolbar) — HAQ is designed for phones.

## Story

Lakshmi worked two months as a cook. She was promised ₹9,000 a month, received ₹12,000 in total, and her employer stopped answering. She has a WhatsApp chat and a UPI receipt.

## Steps

| Time | Do | Say |
|---|---|---|
| 0:00 | Landing page; switch language to தமிழ், then اردو, then back | "HAQ means 'what is rightfully yours'. 13 Indian languages are built in, Urdu even reads right-to-left, and a worker can use any other language too — their words are kept exactly." |
| 0:30 | Worker → Create account → the DEV box shows the code → Confirm | "One account system for both roles. The server decides the role — the app can't be tricked into making a worker an employer." |
| 1:00 | **Tell us what happened** → (in Chrome, press **Speak** and say a sentence) → type the rest | "Speak or type in your own words. Notice: 'Saved on this phone only — not sent yet'. We never pretend something reached the server." |
| 1:45 | Add the chat and the receipt | "Any format. Each file is checked, fingerprinted with SHA-256, stored privately, and read in the background. Amounts and dates found are shown — the worker can correct them." |
| 2:30 | Details: tap a suggested amount/date; enter employer email | "Only the important questions. Unknown things can stay empty." |
| 3:00 | Summary & checks | "Automatic checks point out things to look at — like dates outside the period. They never call anyone a fraud." |
| 3:30 | **Prepare my letter**; point at the label | "With IBM Granite switched on, Granite writes only the 'What happened' paragraph. Amounts, the calculation and the evidence list are assembled by plain code. If Granite mentions an amount that isn't in her information, we throw its answer away. Right now it says 'no AI was used' — the app is honest about that." |
| 4:00 | Edit one word in the letter; Next; tick one file; tick the confirmation; **Send** | "She chooses exactly which files the employer sees. Nothing is sent until she confirms." |
| 4:30 | Employer window: sign in with the **worker** email on the employer page | "Wrong portal → a clear message, not a confusing failure." |
| 5:00 | Register the employer with the address Lakshmi entered → inbox → open claim | "The employer only sees claims sent to their *verified* email, and only the one shared file." |
| 5:30 | Employer: **I have seen this claim** → ask a question → worker replies | "Every step lands on the timeline for both sides." |
| 6:00 | Employer offers ₹6,000 → worker accepts → employer records payment | "Look: the claim is *Payment pending*, not resolved. An employer saying 'I paid' isn't proof." |
| 6:30 | Worker taps **I received this** → Resolved → **Print / save record** | "Only the worker's confirmation resolves it. She can print a full record any time." |
| 7:00 | Wage calculator: 800 × 18, paid 8,000 → ₹6,400 | "Money is calculated with exact decimal arithmetic, never by AI, and labelled as an estimate, not a legal finding." |

## If something goes wrong

- *No verification code:* it is in the yellow DEV box under "Confirm your email" (development mode only).
- *Employer sees no claims:* the employer must register with **exactly** the email the worker typed, and verify it.
- *Voice button missing:* use Chrome or Edge.
- *Letter says "no AI was used":* expected unless you configured Granite (see DEPLOYMENT_GUIDE.md §3).
