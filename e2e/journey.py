"""End-to-end browser test of the main HAQ journey (worker + employer) with screenshots.

Requires: pip install playwright && python -m playwright install chromium
Run with the app already running at BASE_URL (default http://127.0.0.1:8000) in development mode:
    python e2e/journey.py
Screenshots are written to docs/screenshots/.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
SAMPLES = Path(__file__).resolve().parent / "samples"
SHOTS.mkdir(parents=True, exist_ok=True)
PHONE = {"width": 390, "height": 844}
RUN = uuid.uuid4().hex[:6]
WORKER = {"name": "Lakshmi", "email": f"lakshmi.{RUN}@example.com", "password": "Lakshmi2026"}
EMPLOYER = {"name": "Suresh", "email": f"suresh.{RUN}@example.com", "password": "Suresh2026"}
results: list[tuple[str, bool, str]] = []


def step(name):
    def deco(fn):
        def run(*a, **kw):
            try:
                fn(*a, **kw)
                results.append((name, True, ""))
                print(f"  ✓ {name}")
            except Exception as e:  # report and stop
                results.append((name, False, str(e).splitlines()[0][:200]))
                print(f"  ✗ {name}: {e}")
                raise
        return run
    return deco


def shot(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)


def register_and_verify(page, portal, who):
    page.goto(f"{BASE}/{portal}/register")
    page.get_by_label("Your name").fill(who["name"])
    page.get_by_label("Email").fill(who["email"])
    page.get_by_label("Password").fill(who["password"])
    page.get_by_role("button", name="Create account").click()
    expect(page.get_by_text("Confirm your email")).to_be_visible()
    expect(page.locator(".dev-box pre")).to_contain_text("code is", timeout=10000)
    code_text = page.locator(".dev-box pre").inner_text()
    code = "".join(ch for ch in code_text.split("code is")[1] if ch.isdigit())[:6]
    page.get_by_label("6-digit code").fill(code)
    page.get_by_role("button", name="Confirm", exact=True).click()
    expect(page.get_by_text("Confirm your email")).to_have_count(0)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        wctx = browser.new_context(viewport=PHONE, device_scale_factor=2)
        ectx = browser.new_context(viewport=PHONE, device_scale_factor=2)
        w, e = wctx.new_page(), ectx.new_page()
        js_errors, http_errors = [], []
        for pg in (w, e):
            pg.on("pageerror", lambda err: js_errors.append(str(err)))
            pg.on("response", lambda r: http_errors.append(f"{r.status} {r.url}") if r.status >= 400 else None)

        @step("Landing page loads")
        def landing():
            w.goto(BASE)
            expect(w.get_by_role("heading", name="Your wages. Your right.")).to_be_visible()
            shot(w, "01-landing")
        landing()

        @step("Worker registers and verifies email")
        def worker_register():
            register_and_verify(w, "worker", WORKER)
            expect(w.get_by_text("Unpaid wages", exact=True)).to_be_visible()
            expect(w.get_by_text("Another problem at work", exact=True)).to_be_visible()
            shot(w, "02-worker-home")
        worker_register()

        @step("Worker picks the problem type and describes it (step 1 of 4)")
        def describe():
            w.get_by_text("Unpaid wages", exact=True).click()
            expect(w.locator(".issue-chosen")).to_contain_text("Unpaid or less wages")
            expect(w.locator(".issue-picker")).to_have_count(0)
            w.get_by_label("What happened at work?").fill(
                "I worked as a cook for the Mehta family from 1 August to 30 September 2026. We agreed Rs 9000 per month. "
                "They paid Rs 12000 in total and stopped answering my calls.")
            expect(w.get_by_text("Saved on this phone only")).to_be_visible()
            shot(w, "03-describe")
            w.get_by_role("button", name="Next").click()
            expect(w.get_by_text("Add any proof you have")).to_be_visible()
        describe()

        @step("Worker uploads mixed evidence and text is extracted (step 2 of 4)")
        def evidence():
            w.locator("input[type=file]").set_input_files([str(SAMPLES / "chat.txt"), str(SAMPLES / "receipt.pdf"), str(SAMPLES / "voice-note.mp3")])
            # chat.txt and receipt.pdf are always read; the voice note too when offline speech-to-text is set up
            expect(w.locator(".file-item")).to_have_count(3, timeout=20000)
            expect(w.locator(".file-item .ex-pending")).to_have_count(0, timeout=90000)
            expect(w.locator(".file-item .ex-done").nth(1)).to_be_visible()
            shot(w, "04-evidence")
            w.get_by_role("button", name="Next").click()
        evidence()

        @step("Worker fills only the needed details (step 3 of 4)")
        def details():
            w.get_by_label("Employer or customer name").fill("Mehta family")
            w.get_by_label("Employer email (needed to send the claim)").fill(EMPLOYER["email"])
            w.get_by_label("What work did you do?").fill("Cook")
            w.get_by_label("Amount you believe is unpaid (₹)").fill("6000")
            w.get_by_label("Work started").fill("2026-08-01")
            w.get_by_label("Work ended").fill("2026-09-30")
            w.get_by_label("What do you want the employer to do?").fill("Please pay the remaining ₹6,000.")
            shot(w, "05-details")
            w.get_by_role("button", name="Next").click()
            expect(w.get_by_text("Check and send", exact=True)).to_be_visible()
        details()

        @step("Letter is prepared automatically, checks shown, and editable (step 4 of 4)")
        def draft():
            letter = w.locator("#complaint")
            expect(letter).to_be_visible(timeout=20000)
            expect(letter).to_contain_text("₹6,000")
            letter.fill(letter.input_value().replace("Cook", "Cook (full-time)"))
            shot(w, "06-summary-checks")
            shot(w, "07-letter")
        draft()

        @step("Send is blocked until the worker confirms; then the claim is sent")
        def send():
            send_btn = w.get_by_role("button", name="Send to employer")
            expect(send_btn).to_be_disabled()
            w.locator(".share-list label").nth(1).click()  # share only the first file
            w.locator(".share-list label").nth(2).click()
            w.locator(".check-row.confirm input").check()
            shot(w, "08-send")
            send_btn.click()
            expect(w.get_by_text("Your claim was sent.")).to_be_visible(timeout=15000)
            expect(w.locator(".badge-submitted")).to_be_visible()
            shot(w, "09-claim-sent")
        send()

        @step("Wrong portal sign-in is refused with a clear message")
        def wrong_portal():
            e.goto(f"{BASE}/employer/sign-in")
            e.get_by_label("Email").fill(WORKER["email"])
            e.get_by_label("Password").fill(WORKER["password"])
            e.get_by_role("button", name="Sign in").click()
            expect(e.get_by_role("alert")).to_contain_text("worker account")
            shot(e, "10-wrong-portal")
        wrong_portal()

        @step("Employer registers, verifies and sees only the shared file")
        def employer_inbox():
            register_and_verify(e, "employer", EMPLOYER)
            e.get_by_role("tab", name="All").click()
            e.get_by_text(f"From {WORKER['name']}").click()
            expect(e.get_by_text("Proof shared by the worker")).to_be_visible()
            expect(e.locator(".file-list li")).to_have_count(1)
            shot(e, "11-employer-claim")
        employer_inbox()

        @step("Employer acknowledges and asks a question; worker replies")
        def question():
            e.get_by_role("button", name="I have seen this claim").click()
            expect(e.locator(".badge-acknowledged")).to_be_visible()
            e.get_by_label("Type of reply").select_option("question")
            e.get_by_placeholder("Write a reply…").fill("Were there any days you did not come to work?")
            e.get_by_role("button", name="Send", exact=True).click()
            expect(e.locator(".badge-info_requested")).to_be_visible()
            w.reload()
            expect(w.locator(".badge-info_requested")).to_be_visible()
            w.get_by_placeholder("Write a reply…").fill("No, I came every day including Sundays.")
            w.get_by_role("button", name="Send", exact=True).click()
            expect(w.locator(".badge-under_review")).to_be_visible()
        question()

        @step("Employer offers a settlement; worker accepts")
        def settle():
            e.reload()
            e.get_by_label("Amount (₹)").fill("6000")
            e.get_by_label("Explanation").fill("Sorry for the delay. Paying the full balance.")
            e.get_by_role("button", name="Send offer").click()
            expect(e.locator(".badge-settlement_offered")).to_be_visible()
            w.reload()
            shot(w, "12-offer-received")
            w.get_by_role("button", name="Accept offer").click()
            expect(w.locator(".badge-settlement_accepted")).to_be_visible()
        settle()

        @step("Employer records payment; claim waits for worker; worker confirms → resolved")
        def payment():
            e.reload()
            e.get_by_label("Amount paid (₹)").fill("6000")
            e.get_by_label("Reference (UPI / bank / cash note)").fill("UPI 4471 2290")
            e.get_by_role("button", name="Record payment").click()
            expect(e.locator(".badge-payment_pending")).to_be_visible()
            shot(e, "13-employer-payment-recorded")
            w.reload()
            expect(w.locator(".badge-payment_pending")).to_be_visible()
            w.get_by_role("button", name="I received this").click()
            expect(w.locator(".badge-resolved")).to_be_visible()
            shot(w, "14-resolved")
        payment()

        @step("Next-steps guide, and Hindi, Tamil and Urdu (right-to-left) interfaces")
        def calc_hindi():
            w.goto(f"{BASE}/guide")
            expect(w.get_by_role("heading", name="If your problem is not solved")).to_be_visible()
            expect(w.get_by_text("15100", exact=False)).to_be_visible()
            shot(w, "15-guide")
            w.goto(f"{BASE}/worker")
            w.get_by_label("Language").first.select_option("hi")
            expect(w.get_by_text("मज़दूरी नहीं मिली", exact=True)).to_be_visible()
            shot(w, "16-hindi-home")
            w.get_by_label("भाषा").first.select_option("ta")
            expect(w.get_by_text("சம்பளம் கிடைக்கவில்லை", exact=True)).to_be_visible()
            shot(w, "18-tamil-home")
            w.get_by_label("மொழி").first.select_option("ur")
            expect(w.locator("html")).to_have_attribute("dir", "rtl")
            expect(w.get_by_text("اجرت نہیں ملی", exact=True)).to_be_visible()
            shot(w, "19-urdu-home")
            w.get_by_label("زبان").first.select_option("en")
        calc_hindi()

        @step("No JavaScript errors, and the only HTTP error is the deliberate wrong-portal sign-in")
        def console_clean():
            assert not js_errors, js_errors
            unexpected = [x for x in http_errors if not (x.startswith("403 ") and x.endswith("/api/auth/login"))]
            assert not unexpected, unexpected
        console_clean()

        # Desktop screenshot of the employer view for documentation
        e.set_viewport_size({"width": 1280, "height": 900})
        e.reload()
        time.sleep(0.5)
        shot(e, "17-employer-desktop")
        browser.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        passed = sum(1 for r in results if r[1])
        print(f"\nE2E: {passed}/{len(results)} steps passed")
        if any(not r[1] for r in results):
            sys.exit(1)
