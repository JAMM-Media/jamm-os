# scripts/seed_letter_templates.py
"""
Seed engagement letter templates for the Riverside demo firm.
Run from the project root:
    python scripts/seed_letter_templates.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.engagement_letter_template import EngagementLetterTemplate
from app.models.firm import Firm

TEMPLATES = [
    {
        "name": "Individual Tax Return Engagement Letter (1040)",
        "engagement_type": "tax_return_1040",
        "variable_fields": ["client_name", "client_email", "firm_name", "firm_owner_name", "engagement_name", "engagement_date", "due_date", "fee_amount"],
        "body_html": """<p style="margin-bottom: 24pt;">{{engagement_date}}</p>

<p style="margin-bottom: 24pt;">
  {{client_name}}<br>
  {{client_email}}
</p>

<p style="margin-bottom: 12pt;"><strong>Re: Engagement Letter — {{engagement_name}}</strong></p>

<p style="margin-bottom: 12pt;">Dear {{client_name}},</p>

<p style="margin-bottom: 12pt;">Thank you for choosing {{firm_name}}. This letter confirms the terms of our engagement to prepare your federal and applicable state individual income tax return (Form 1040) for the tax year covered by this engagement.</p>

<p style="margin-bottom: 6pt;"><strong>Scope of Services</strong></p>
<p style="margin-bottom: 12pt;">We will prepare your Form 1040 and any required state returns based on information you provide. Our work does not include audit, review, or verification of source documents. We will rely on the accuracy and completeness of the information you furnish.</p>

<p style="margin-bottom: 6pt;"><strong>Your Responsibilities</strong></p>
<p style="margin-bottom: 12pt;">You agree to provide all documents, records, and information we request in a timely manner. You are responsible for the accuracy and completeness of all information provided and for maintaining all original source documents. You represent that the information you provide is accurate and complete to the best of your knowledge.</p>

<p style="margin-bottom: 6pt;"><strong>Fees</strong></p>
<p style="margin-bottom: 12pt;">Our fee for this engagement is {{fee_amount}}. Fees are due upon completion of services. We reserve the right to suspend services if your account becomes past due.</p>

<p style="margin-bottom: 6pt;"><strong>Filing Deadline</strong></p>
<p style="margin-bottom: 12pt;">The due date for this engagement is {{due_date}}. If we do not receive all required information in sufficient time to complete your return by the deadline, we may need to file for an extension on your behalf.</p>

<p style="margin-bottom: 6pt;"><strong>Confidentiality</strong></p>
<p style="margin-bottom: 12pt;">We will keep your information strictly confidential and will not disclose it to third parties without your consent, except as required by law or professional standards.</p>

<p style="margin-bottom: 6pt;"><strong>Limitation of Liability</strong></p>
<p style="margin-bottom: 12pt;">Our liability in connection with this engagement is limited to the fees paid for the specific service that is the subject of any claim. We are not responsible for any penalties or interest resulting from information you provided that is inaccurate or incomplete.</p>

<p style="margin-bottom: 24pt;">Please sign below to confirm your agreement with these terms. Your signature constitutes acceptance of this engagement letter and authorization for {{firm_name}} to proceed.</p>

<p style="margin-bottom: 6pt;">Sincerely,</p>
<p style="margin-bottom: 48pt;"><strong>{{firm_owner_name}}</strong><br>{{firm_name}}</p>

<hr style="border: none; border-top: 1px solid #111; margin-bottom: 12pt;">

<p style="margin-bottom: 6pt;"><strong>Client Acceptance</strong></p>
<p style="margin-bottom: 24pt;">I have read and agree to the terms of this engagement letter.</p>

<table style="width: 100%; border-collapse: collapse;">
  <tr>
    <td style="width: 50%; padding-right: 24pt;">
      <p style="margin-bottom: 0; border-bottom: 1px solid #111; padding-bottom: 2pt;">&nbsp;</p>
      <p style="margin-top: 4pt; font-size: 10pt;">Signature of {{client_name}}</p>
    </td>
    <td style="width: 50%; padding-left: 24pt;">
      <p style="margin-bottom: 0; border-bottom: 1px solid #111; padding-bottom: 2pt;">&nbsp;</p>
      <p style="margin-top: 4pt; font-size: 10pt;">Date</p>
    </td>
  </tr>
</table>""",
    },
    {
        "name": "Partnership Return Engagement Letter (1065)",
        "engagement_type": "tax_return_1065",
        "variable_fields": ["client_name", "client_email", "firm_name", "firm_owner_name", "engagement_name", "engagement_date", "due_date", "fee_amount"],
        "body_html": """<p style="margin-bottom: 24pt;">{{engagement_date}}</p>

<p style="margin-bottom: 24pt;">
  {{client_name}}<br>
  {{client_email}}
</p>

<p style="margin-bottom: 12pt;"><strong>Re: Engagement Letter — {{engagement_name}}</strong></p>

<p style="margin-bottom: 12pt;">Dear {{client_name}},</p>

<p style="margin-bottom: 12pt;">Thank you for engaging {{firm_name}}. This letter sets forth the terms of our engagement to prepare the federal partnership income tax return (Form 1065) and applicable state returns for the tax year covered by this engagement.</p>

<p style="margin-bottom: 6pt;"><strong>Scope of Services</strong></p>
<p style="margin-bottom: 12pt;">We will prepare Form 1065 and the required Schedules K-1 for each partner based on information and records provided by the partnership. Our engagement does not include an audit, review, or compilation of the partnership's financial statements, nor does it include verification of any partner's individual tax reporting.</p>

<p style="margin-bottom: 6pt;"><strong>Your Responsibilities</strong></p>
<p style="margin-bottom: 12pt;">You agree to provide complete and accurate financial records, partner information, and all other documentation we require. You represent that all information provided reflects the partnership's actual operations and is accurate and complete to the best of your knowledge. You are responsible for maintaining original source documents.</p>

<p style="margin-bottom: 6pt;"><strong>Fees</strong></p>
<p style="margin-bottom: 12pt;">Our fee for this engagement is {{fee_amount}}. Fees are due upon delivery of the completed return. Complexity beyond what was anticipated at engagement may result in additional fees, which we will discuss with you in advance.</p>

<p style="margin-bottom: 6pt;"><strong>Filing Deadline</strong></p>
<p style="margin-bottom: 12pt;">The due date for this engagement is {{due_date}}. Timely delivery of all required information is essential. If documentation is not received in sufficient time, we may file for an extension on the partnership's behalf.</p>

<p style="margin-bottom: 6pt;"><strong>Confidentiality</strong></p>
<p style="margin-bottom: 12pt;">All information provided will be kept strictly confidential. We will not disclose partnership or partner information to any third party without authorization, except as required by applicable law or professional standards.</p>

<p style="margin-bottom: 6pt;"><strong>Limitation of Liability</strong></p>
<p style="margin-bottom: 12pt;">Our liability arising from this engagement is limited to the fees paid. We are not responsible for penalties, interest, or other consequences resulting from inaccurate or incomplete information provided by the partnership.</p>

<p style="margin-bottom: 24pt;">Please sign below to authorize {{firm_name}} to proceed with this engagement on behalf of the partnership.</p>

<p style="margin-bottom: 6pt;">Sincerely,</p>
<p style="margin-bottom: 48pt;"><strong>{{firm_owner_name}}</strong><br>{{firm_name}}</p>

<hr style="border: none; border-top: 1px solid #111; margin-bottom: 12pt;">

<p style="margin-bottom: 6pt;"><strong>Authorized Partner Acceptance</strong></p>
<p style="margin-bottom: 24pt;">I am authorized to sign on behalf of the partnership and agree to the terms of this engagement letter.</p>

<table style="width: 100%; border-collapse: collapse;">
  <tr>
    <td style="width: 50%; padding-right: 24pt;">
      <p style="margin-bottom: 0; border-bottom: 1px solid #111; padding-bottom: 2pt;">&nbsp;</p>
      <p style="margin-top: 4pt; font-size: 10pt;">Authorized Signature — {{client_name}}</p>
    </td>
    <td style="width: 50%; padding-left: 24pt;">
      <p style="margin-bottom: 0; border-bottom: 1px solid #111; padding-bottom: 2pt;">&nbsp;</p>
      <p style="margin-top: 4pt; font-size: 10pt;">Date</p>
    </td>
  </tr>
</table>""",
    },
    {
        "name": "S-Corporation Return Engagement Letter (1120-S)",
        "engagement_type": "tax_return_1120s",
        "variable_fields": ["client_name", "client_email", "firm_name", "firm_owner_name", "engagement_name", "engagement_date", "due_date", "fee_amount"],
        "body_html": """<p style="margin-bottom: 24pt;">{{engagement_date}}</p>

<p style="margin-bottom: 24pt;">
  {{client_name}}<br>
  {{client_email}}
</p>

<p style="margin-bottom: 12pt;"><strong>Re: Engagement Letter — {{engagement_name}}</strong></p>

<p style="margin-bottom: 12pt;">Dear {{client_name}},</p>

<p style="margin-bottom: 12pt;">Thank you for selecting {{firm_name}} to assist with your tax compliance needs. This letter confirms the terms of our engagement to prepare the federal S-Corporation income tax return (Form 1120-S) and applicable state returns for the tax year covered by this engagement.</p>

<p style="margin-bottom: 6pt;"><strong>Scope of Services</strong></p>
<p style="margin-bottom: 12pt;">We will prepare Form 1120-S and Schedules K-1 for each shareholder based on the financial information and records you provide. This engagement does not include an audit or review of the corporation's financial statements. We will rely on the records you provide without independent verification.</p>

<p style="margin-bottom: 6pt;"><strong>Your Responsibilities</strong></p>
<p style="margin-bottom: 12pt;">You agree to provide complete financial records, shareholder information, officer compensation details, and all other documentation necessary to prepare an accurate return. Management is responsible for the accuracy and completeness of all information provided and for retaining original records in accordance with IRS requirements.</p>

<p style="margin-bottom: 6pt;"><strong>Fees</strong></p>
<p style="margin-bottom: 12pt;">Our fee for this engagement is {{fee_amount}}. Payment is due upon completion and delivery of the return. If the complexity of your return exceeds our initial estimate, we will notify you before incurring additional fees.</p>

<p style="margin-bottom: 6pt;"><strong>Filing Deadline</strong></p>
<p style="margin-bottom: 12pt;">The due date for this engagement is {{due_date}}. Please provide all required documentation well in advance of this date. If necessary, we may file an extension on the corporation's behalf to avoid late filing penalties.</p>

<p style="margin-bottom: 6pt;"><strong>Confidentiality</strong></p>
<p style="margin-bottom: 12pt;">We treat all corporate and shareholder information as strictly confidential. Information will not be shared with any third party without your written consent, except as required by law or professional standards.</p>

<p style="margin-bottom: 6pt;"><strong>Limitation of Liability</strong></p>
<p style="margin-bottom: 12pt;">{{firm_name}}'s liability in connection with this engagement shall not exceed the fees paid for the services giving rise to any claim. We shall not be liable for any penalties or interest attributable to information that was inaccurate, incomplete, or not provided to us in a timely manner.</p>

<p style="margin-bottom: 24pt;">By signing below, you confirm that you are authorized to execute this agreement on behalf of the corporation and that you accept its terms.</p>

<p style="margin-bottom: 6pt;">Sincerely,</p>
<p style="margin-bottom: 48pt;"><strong>{{firm_owner_name}}</strong><br>{{firm_name}}</p>

<hr style="border: none; border-top: 1px solid #111; margin-bottom: 12pt;">

<p style="margin-bottom: 6pt;"><strong>Corporate Authorization</strong></p>
<p style="margin-bottom: 24pt;">I am an authorized officer of the corporation and agree to the terms of this engagement letter.</p>

<table style="width: 100%; border-collapse: collapse;">
  <tr>
    <td style="width: 50%; padding-right: 24pt;">
      <p style="margin-bottom: 0; border-bottom: 1px solid #111; padding-bottom: 2pt;">&nbsp;</p>
      <p style="margin-top: 4pt; font-size: 10pt;">Authorized Officer Signature — {{client_name}}</p>
    </td>
    <td style="width: 50%; padding-left: 24pt;">
      <p style="margin-bottom: 0; border-bottom: 1px solid #111; padding-bottom: 2pt;">&nbsp;</p>
      <p style="margin-top: 4pt; font-size: 10pt;">Date</p>
    </td>
  </tr>
</table>""",
    },
    {
        "name": "Advisory / Consulting Engagement Letter",
        "engagement_type": None,
        "variable_fields": ["client_name", "client_email", "firm_name", "firm_owner_name", "engagement_name", "engagement_date", "due_date", "fee_amount"],
        "body_html": """<p style="margin-bottom: 24pt;">{{engagement_date}}</p>

<p style="margin-bottom: 24pt;">
  {{client_name}}<br>
  {{client_email}}
</p>

<p style="margin-bottom: 12pt;"><strong>Re: Engagement Letter — {{engagement_name}}</strong></p>

<p style="margin-bottom: 12pt;">Dear {{client_name}},</p>

<p style="margin-bottom: 12pt;">We are pleased to confirm our engagement with you. This letter sets forth the terms under which {{firm_name}} will provide professional advisory and consulting services as described below.</p>

<p style="margin-bottom: 6pt;"><strong>Scope of Services</strong></p>
<p style="margin-bottom: 12pt;">{{firm_name}} will provide advisory and consulting services in connection with {{engagement_name}}. The specific deliverables, timelines, and any additional terms will be agreed upon between the parties as the engagement progresses. Any material changes to the scope of services will be documented in writing.</p>

<p style="margin-bottom: 6pt;"><strong>Your Responsibilities</strong></p>
<p style="margin-bottom: 12pt;">You agree to provide timely access to all information, personnel, and records reasonably necessary for us to perform our services. You are responsible for management decisions and for the implementation of any advice or recommendations we provide. Our services are advisory in nature and do not constitute legal advice.</p>

<p style="margin-bottom: 6pt;"><strong>Fees</strong></p>
<p style="margin-bottom: 12pt;">Our fee for this engagement is {{fee_amount}}. Fees are due as services are rendered unless otherwise agreed in writing. Out-of-pocket expenses incurred in connection with this engagement will be billed at cost.</p>

<p style="margin-bottom: 6pt;"><strong>Term and Termination</strong></p>
<p style="margin-bottom: 12pt;">This engagement covers the period through {{due_date}} unless extended by mutual written agreement. Either party may terminate this engagement upon written notice. You will remain responsible for fees earned through the date of termination.</p>

<p style="margin-bottom: 6pt;"><strong>Confidentiality</strong></p>
<p style="margin-bottom: 12pt;">All information you share with us in connection with this engagement will be kept strictly confidential. We will not disclose your information to any third party without your consent, except as required by applicable law or professional standards.</p>

<p style="margin-bottom: 6pt;"><strong>Limitation of Liability</strong></p>
<p style="margin-bottom: 12pt;">Our aggregate liability arising from or related to this engagement shall not exceed the fees paid in the three months preceding the event giving rise to the claim. We shall not be liable for any indirect, consequential, or punitive damages.</p>

<p style="margin-bottom: 6pt;"><strong>Independence</strong></p>
<p style="margin-bottom: 12pt;">{{firm_name}} is engaged as an independent contractor. Nothing in this agreement creates an employment, partnership, or joint venture relationship between the parties.</p>

<p style="margin-bottom: 24pt;">Please sign below to confirm your acceptance of these terms and to authorize {{firm_name}} to begin work on this engagement.</p>

<p style="margin-bottom: 6pt;">Sincerely,</p>
<p style="margin-bottom: 48pt;"><strong>{{firm_owner_name}}</strong><br>{{firm_name}}</p>

<hr style="border: none; border-top: 1px solid #111; margin-bottom: 12pt;">

<p style="margin-bottom: 6pt;"><strong>Client Acceptance</strong></p>
<p style="margin-bottom: 24pt;">I have read and agree to the terms of this engagement letter.</p>

<table style="width: 100%; border-collapse: collapse;">
  <tr>
    <td style="width: 50%; padding-right: 24pt;">
      <p style="margin-bottom: 0; border-bottom: 1px solid #111; padding-bottom: 2pt;">&nbsp;</p>
      <p style="margin-top: 4pt; font-size: 10pt;">Signature of {{client_name}}</p>
    </td>
    <td style="width: 50%; padding-left: 24pt;">
      <p style="margin-bottom: 0; border-bottom: 1px solid #111; padding-bottom: 2pt;">&nbsp;</p>
      <p style="margin-top: 4pt; font-size: 10pt;">Date</p>
    </td>
  </tr>
</table>""",
    },
]


def main():
    db = SessionLocal()
    try:
        # Find the Riverside demo firm
        firm = db.query(Firm).filter(Firm.slug == "riverside-tax-advisory").first()
        if not firm:
            # Fall back to first firm
            firm = db.query(Firm).first()
        if not firm:
            print("No firm found. Run seed_riverside_demo.py first.")
            return

        inserted = 0
        for t in TEMPLATES:
            existing = (
                db.query(EngagementLetterTemplate)
                .filter(
                    EngagementLetterTemplate.firm_id == firm.id,
                    EngagementLetterTemplate.name == t["name"],
                )
                .first()
            )
            if existing:
                print(f"  Skipping (already exists): {t['name']}")
                continue

            template = EngagementLetterTemplate(
                firm_id=firm.id,
                name=t["name"],
                engagement_type=t["engagement_type"],
                body_html=t["body_html"],
                variable_fields=t["variable_fields"],
                is_active=True,
            )
            db.add(template)
            inserted += 1
            print(f"  Inserted: {t['name']}")

        db.commit()
        print(f"\nDone. {inserted} template(s) inserted for firm '{firm.name}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
