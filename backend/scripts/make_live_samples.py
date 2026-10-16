"""Create realistic sample inputs (fictitious organisations) for live Smart Verification tests.

    .venv/Scripts/python scripts/make_live_samples.py <output-dir>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests import fixtures  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "live-samples")
out.mkdir(parents=True, exist_ok=True)

(out / "email.txt").write_text(
    "Subject: Final notice - your parcel is on hold\n\n"
    "Dear Customer,\n"
    "We attempted to deliver your parcel (ref. AC-20931) on 14 October 2026 but customs duties of $4.99 are unpaid.\n"
    "Pay within 24 hours at http://acme-parcel-release.xyz/pay or the parcel will be destroyed.\n"
    "Acme Logistics refunds all customer payments within 30 days, no questions asked.\n"
    "Acme Logistics has delivered over 2 billion parcels since 1985.\n\n"
    "Acme Logistics Support Team\nsupport@acme-logistics-help.com | +1 415 555 0134\n", encoding="utf-8")

(out / "offer-letter.pdf").write_bytes(fixtures.text_pdf([
    "NORTHWIND CONSULTING LLP - OFFER OF ENGAGEMENT",
    "Date: 2 October 2026",
    "Dear Ms. Patel,",
    "We are pleased to offer you the role of Remote Data Analyst at a salary of USD 9,500 per month.",
    "Northwind Consulting is a Fortune 500 company with offices in 42 countries.",
    "To activate your company laptop, please transfer a refundable deposit of USD 450",
    "to our equipment partner within 48 hours: account 0091-447-2210, Swift NWCLUS33.",
    "Your start date is 15 October 2026. No interview is required.",
    "HR Department, careers@northwind-consulting-jobs.net",
]))

(out / "message-screenshot.png").write_bytes(fixtures.png([
    "WhatsApp  +44 7700 900123",
    "Hi! This is Emma from Globex Bank security team.",
    "We detected an unusual login on your account.",
    "Reply with the 6-digit code we just sent you",
    "to keep your account active. Expires in 10 min.",
]))

(out / "refund-policy.pdf").write_bytes(fixtures.text_pdf([
    "Acme Logistics - Customer Refund Policy (v4, effective 1 January 2026)",
    "1. Refund requests must be submitted within 14 days of payment.",
    "2. Approved refunds are issued within 10 business days.",
    "3. Customs duties paid to government authorities are non-refundable.",
    "4. Acme Logistics never requests payment through third-party websites.",
    "Official website: www.acmelogistics.com",
]))

(out / "scanned-invoice.pdf").write_bytes(fixtures.scanned_pdf([
    "INVOICE  #INV-1042        Date: 30 September 2026",
    "Bill to: Contoso Retail Ltd",
    "Cloud hosting - Q3 2026 ............ $1,250.00",
    "Payment due: 14 October 2026",
    "Bank: First Example Bank  IBAN: GB00 EXAM 0000 1234 5678",
]))

(out / "corrupt.pdf").write_bytes(b"%PDF-1.7\nthis is not really a pdf\n")
(out / "locked.pdf").write_bytes(fixtures.encrypted_pdf())
(out / "notes.txt").write_text("plain text file", encoding="utf-8")
print("samples written to", out.resolve())
