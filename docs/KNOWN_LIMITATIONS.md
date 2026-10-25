# HAQ — Known Limitations

Be open about these when presenting. None of them is hidden in the app: the UI tells users when something was not done.

## Not connected to live services yet

1. **IBM Granite has not been run live.** The watsonx.ai and Ollama integrations are implemented and unit-tested with mocked HTTP responses, but no watsonx.ai credentials were available and Ollama could not be reached from the build environment. Until `AI_PROVIDER` is set and working, letters are written from a deterministic template and the app says "no AI was used".
2. **Watsonx model ID must be checked.** The default `ibm/granite-3-8b-instruct` may not be offered in your region or may have been replaced; pick a Granite model listed in your watsonx.ai project and set `WATSONX_MODEL_ID`.
3. **Email runs in console mode.** Verification codes are shown in the app (development only) and in the server log. SMTP sending is implemented but untested against a real mail server.
4. **Not deployed.** A Dockerfile for IBM Cloud Code Engine exists but has not been built or deployed.

## Features that are partial or missing

5. **No server-side speech-to-text.** Voice typing uses the browser's speech recognition (best in Chrome on Android/desktop; support for some languages such as Odia and Assamese depends on the browser; voice typing needs internet). Uploaded voice notes and videos are stored safely but not transcribed.
6. **OCR needs Tesseract.** Images are read only if Tesseract is installed on the server (the Docker image installs English, Hindi and Kannada). Scanned PDFs (no text layer) are not OCR'd.
7. **No translation for the employer.** The letter is written in the worker's chosen language only.
8. **Translations need review.** English and Hindi cover every screen. The other 11 languages cover the main worker screens and all claim statuses; less common screens (e.g. the employer forms and help page) fall back to English. All translations were written for this project and should be checked by native speakers.
9. **Checks are simple rules**, not forensic analysis. They cannot detect edited screenshots; they only point out things to review.
10. **No email or SMS notifications for claim updates** — only in-app notifications and the first "you have a claim" email to the employer.
11. **Employer business verification** is a status field with no verification process behind it.
12. **No resumable uploads.** A failed upload can be retried, but it restarts from the beginning.
13. **No offline mode / service worker.** Only the description text is saved on the device before it reaches the server.

## Operational

14. Single-process deployment with SQLite and an in-memory rate limiter; not designed for multiple server instances yet.
15. No malware scanning, no encryption at rest, no retention policy (see SECURITY_NOTES.md).
16. Not reviewed by a lawyer; HAQ deliberately gives no legal advice.
