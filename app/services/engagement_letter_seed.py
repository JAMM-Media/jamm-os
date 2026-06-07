# app/services/engagement_letter_seed.py

from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.engagement_letter_template import EngagementLetterTemplate


def seed_firm_letter_templates(firm_id: UUID, db: Session) -> int:
    now = datetime.now(timezone.utc)
    templates = _get_default_letter_templates(firm_id, now)
    for t in templates:
        db.add(EngagementLetterTemplate(**t))
    db.commit()
    return len(templates)


def _get_default_letter_templates(firm_id: UUID, now) -> list[dict]:
    return [
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Individual Tax Return Engagement Letter",
            "engagement_type": "tax_return_1040",
            "body_html": (
                '<div style="font-family: Georgia, serif; font-size: 12pt;'
                ' line-height: 1.6; color: #111;">'
                '\n\n'
                '  <div style="margin-bottom: 32px;">\n'
                '    <p style="margin: 0; font-weight: bold; font-size: 13pt;">\n'
                '      {{firm_name}}</p>\n'
                '    <p style="margin: 4px 0 0 0;">{{firm_address}}</p>\n'
                '    <p style="margin: 4px 0 0 0;">{{firm_phone}} &nbsp;|&nbsp;\n'
                '      {{firm_contact_email}}</p>\n'
                '  </div>\n\n'
                '  <p style="margin-bottom: 24px;">{{engagement_date}}</p>\n\n'
                '  <p style="margin-bottom: 24px;">Dear {{client_name}},</p>\n\n'
                '  <p>Thank you for entrusting {{firm_name}} with your tax\n'
                '  preparation needs. This letter confirms the terms of our\n'
                '  engagement for the preparation of your federal and applicable\n'
                '  state individual income tax returns (Form 1040) for the tax\n'
                '  year referenced above.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Scope of Services</h3>\n\n'
                '  <p>Our engagement includes the preparation of your federal\n'
                '  Form 1040 and any required state individual income tax\n'
                '  returns based on the information and documents you provide.\n'
                '  We will review your tax situation for potential deductions\n'
                '  and credits and advise you of planning opportunities we\n'
                '  identify in the course of our work.</p>\n\n'
                '  <p>Our services do not include audit representation,\n'
                '  response to IRS or state notices unrelated to the current\n'
                '  tax year, amended returns, or bookkeeping services unless\n'
                '  separately agreed upon in writing.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Your Responsibilities</h3>\n\n'
                '  <p>To complete your returns accurately and on time, you\n'
                '  agree to provide all income statements, expense records,\n'
                '  and supporting documents in a timely manner. You confirm\n'
                '  that all information provided to {{firm_name}} is accurate\n'
                '  and complete to the best of your knowledge. Delays in\n'
                '  providing information may affect our ability to meet filing\n'
                '  deadlines.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Professional Fees</h3>\n\n'
                '  <p>Our fee for this engagement is <strong>{{fee_amount}}\n'
                '  </strong>. This fee covers the scope of services described\n'
                '  above. Fees for services outside this scope will be\n'
                '  discussed and agreed upon before any additional work\n'
                '  begins. Payment is due upon delivery of your completed\n'
                '  returns.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Confidentiality</h3>\n\n'
                '  <p>All information you share with {{firm_name}} is held\n'
                '  in strict confidence and will not be disclosed to any\n'
                '  third party without your written consent, except as\n'
                '  required by law or professional standards.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Limitation of Liability</h3>\n\n'
                '  <p>Our liability in connection with this engagement is\n'
                '  limited to the fees paid for the specific services giving\n'
                '  rise to the claim. We are not responsible for any\n'
                '  penalties, interest, or other consequences arising from\n'
                '  information provided to us that is incomplete, inaccurate,\n'
                '  or untimely.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Agreement</h3>\n\n'
                '  <p>Please review this letter carefully. Your electronic\n'
                '  signature below constitutes your agreement to the terms\n'
                '  described and authorizes {{firm_name}} to proceed with\n'
                '  the preparation of your returns.</p>\n\n'
                '  <p style="margin-top: 32px;">Sincerely,</p>\n'
                '  <p style="margin-top: 8px;"><strong>{{firm_owner_name}}\n'
                '  </strong><br>{{firm_name}}</p>\n\n'
                '</div>'
            ),
            "variable_fields": [
                "client_name", "firm_name", "firm_owner_name",
                "firm_address", "firm_phone", "firm_contact_email",
                "engagement_date", "fee_amount",
            ],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Business Tax Return Engagement Letter",
            "engagement_type": "tax_return_1120s",
            "body_html": (
                '<div style="font-family: Georgia, serif; font-size: 12pt;'
                ' line-height: 1.6; color: #111;">'
                '\n\n'
                '  <div style="margin-bottom: 32px;">\n'
                '    <p style="margin: 0; font-weight: bold; font-size: 13pt;">\n'
                '      {{firm_name}}</p>\n'
                '    <p style="margin: 4px 0 0 0;">{{firm_address}}</p>\n'
                '    <p style="margin: 4px 0 0 0;">{{firm_phone}} &nbsp;|&nbsp;\n'
                '      {{firm_contact_email}}</p>\n'
                '  </div>\n\n'
                '  <p style="margin-bottom: 24px;">{{engagement_date}}</p>\n\n'
                '  <p style="margin-bottom: 24px;">Dear {{client_name}},</p>\n\n'
                '  <p>Thank you for selecting {{firm_name}} to assist with\n'
                '  your business tax compliance. This letter confirms the\n'
                '  scope and terms of our engagement for the preparation of\n'
                '  your business income tax return for the tax year\n'
                '  referenced above.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Scope of Services</h3>\n\n'
                '  <p>Our engagement includes the preparation of your federal\n'
                '  business income tax return ({{engagement_type}}) and any\n'
                '  required state returns, based on the financial information\n'
                '  and supporting documents you provide. We will identify\n'
                '  available deductions and advise on planning opportunities\n'
                '  noted in the course of our review.</p>\n\n'
                '  <p>This engagement does not include audit representation,\n'
                '  payroll tax filings, sales tax compliance, financial\n'
                '  statement preparation, or responses to government notices\n'
                '  unrelated to the current return unless separately agreed\n'
                '  upon in writing.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Your Responsibilities</h3>\n\n'
                '  <p>You agree to provide complete and accurate financial\n'
                '  records, bank statements, payroll summaries, and any other\n'
                '  documentation necessary to prepare your return. Management\n'
                '  is responsible for the accuracy of all information provided.\n'
                '  {{firm_name}} will rely on the information supplied without\n'
                '  independent verification. Timely delivery of records is\n'
                '  necessary to meet filing deadlines.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Professional Fees</h3>\n\n'
                '  <p>Our fee for this engagement is <strong>{{fee_amount}}\n'
                '  </strong>. This fee is based on the scope described above\n'
                '  and assumes the records provided are complete and organized.\n'
                '  Should significant additional work be required, we will\n'
                '  discuss revised fees before proceeding. Payment is due upon\n'
                '  delivery of the completed return.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Confidentiality</h3>\n\n'
                '  <p>All business and financial information shared with\n'
                '  {{firm_name}} is maintained in strict confidence. We will\n'
                '  not disclose your information to any third party without\n'
                '  your written authorization, except as required by\n'
                '  applicable law or professional standards.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Limitation of Liability</h3>\n\n'
                '  <p>Our liability arising from this engagement is limited\n'
                '  to the fees paid for the services described herein.\n'
                '  {{firm_name}} is not responsible for penalties, interest,\n'
                '  or losses resulting from inaccurate, incomplete, or\n'
                '  untimely information provided by you or any third party\n'
                '  on your behalf.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Agreement</h3>\n\n'
                '  <p>Please review this letter carefully. Your electronic\n'
                '  signature below confirms your agreement to the terms of\n'
                '  this engagement and authorizes {{firm_name}} to proceed\n'
                '  with the preparation of your business return.</p>\n\n'
                '  <p style="margin-top: 32px;">Sincerely,</p>\n'
                '  <p style="margin-top: 8px;"><strong>{{firm_owner_name}}\n'
                '  </strong><br>{{firm_name}}</p>\n\n'
                '</div>'
            ),
            "variable_fields": [
                "client_name", "firm_name", "firm_owner_name",
                "firm_address", "firm_phone", "firm_contact_email",
                "engagement_date", "fee_amount", "engagement_type",
            ],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Bookkeeping & Advisory Services Engagement Letter",
            "engagement_type": None,
            "body_html": (
                '<div style="font-family: Georgia, serif; font-size: 12pt;'
                ' line-height: 1.6; color: #111;">'
                '\n\n'
                '  <div style="margin-bottom: 32px;">\n'
                '    <p style="margin: 0; font-weight: bold; font-size: 13pt;">\n'
                '      {{firm_name}}</p>\n'
                '    <p style="margin: 4px 0 0 0;">{{firm_address}}</p>\n'
                '    <p style="margin: 4px 0 0 0;">{{firm_phone}} &nbsp;|&nbsp;\n'
                '      {{firm_contact_email}}</p>\n'
                '  </div>\n\n'
                '  <p style="margin-bottom: 24px;">{{engagement_date}}</p>\n\n'
                '  <p style="margin-bottom: 24px;">Dear {{client_name}},</p>\n\n'
                '  <p>We are pleased to confirm our engagement to provide\n'
                '  bookkeeping and advisory services to you. This letter\n'
                '  describes the scope of our work, our mutual responsibilities,\n'
                '  and the terms under which services will be provided.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Scope of Services</h3>\n\n'
                '  <p>{{firm_name}} will provide ongoing bookkeeping and\n'
                '  financial advisory services as agreed, which may include\n'
                '  transaction categorization and reconciliation, monthly or\n'
                '  quarterly financial statement preparation, accounts payable\n'
                '  and receivable support, cash flow analysis, and advisory\n'
                '  consultations on financial matters relevant to your\n'
                '  business.</p>\n\n'
                '  <p>Specific deliverables, reporting frequency, and service\n'
                '  parameters will be agreed upon at the start of each period.\n'
                '  Services outside the agreed scope will be quoted separately\n'
                '  before work begins.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Your Responsibilities</h3>\n\n'
                '  <p>You agree to provide access to all financial accounts,\n'
                '  statements, and records necessary for us to perform our\n'
                '  work accurately. You will review all financial reports\n'
                '  provided by {{firm_name}} and promptly notify us of any\n'
                '  discrepancies. Management remains responsible for all\n'
                '  financial decisions made on the basis of our work\n'
                '  product.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Professional Fees</h3>\n\n'
                '  <p>Our fee for these services is <strong>{{fee_amount}}\n'
                '  </strong> per month, billed on the first of each month.\n'
                '  Fees are subject to review annually and will be discussed\n'
                '  with you in advance of any adjustment. Invoices are due\n'
                '  within fifteen days of receipt.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Term and Termination</h3>\n\n'
                '  <p>This engagement begins on the date of signature and\n'
                '  continues on a month-to-month basis. Either party may\n'
                '  terminate with thirty days written notice. Upon termination,\n'
                '  all fees for services rendered through the termination date\n'
                '  remain due and payable.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Confidentiality</h3>\n\n'
                '  <p>{{firm_name}} will maintain the confidentiality of all\n'
                '  financial and business information provided by you. We will\n'
                '  not share your information with any third party without\n'
                '  your written consent, except as required by law.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Limitation of Liability</h3>\n\n'
                '  <p>Our liability in connection with services provided under\n'
                '  this engagement is limited to fees paid in the three months\n'
                '  preceding the claim. We are not liable for business\n'
                '  decisions made by management based on financial information\n'
                '  we prepare.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Agreement</h3>\n\n'
                '  <p>Your electronic signature below confirms your agreement\n'
                '  to the terms of this engagement and authorizes\n'
                '  {{firm_name}} to begin providing services as described.</p>\n\n'
                '  <p style="margin-top: 32px;">Sincerely,</p>\n'
                '  <p style="margin-top: 8px;"><strong>{{firm_owner_name}}\n'
                '  </strong><br>{{firm_name}}</p>\n\n'
                '</div>'
            ),
            "variable_fields": [
                "client_name", "firm_name", "firm_owner_name",
                "firm_address", "firm_phone", "firm_contact_email",
                "engagement_date", "fee_amount",
            ],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Nonprofit Tax Return Engagement Letter (990)",
            "engagement_type": "tax_return_990",
            "body_html": (
                '<div style="font-family: Georgia, serif; font-size: 12pt;'
                ' line-height: 1.6; color: #111;">'
                '\n\n'
                '  <div style="margin-bottom: 32px;">\n'
                '    <p style="margin: 0; font-weight: bold; font-size: 13pt;">\n'
                '      {{firm_name}}</p>\n'
                '    <p style="margin: 4px 0 0 0;">{{firm_address}}</p>\n'
                '    <p style="margin: 4px 0 0 0;">{{firm_phone}} &nbsp;|&nbsp;\n'
                '      {{firm_contact_email}}</p>\n'
                '  </div>\n\n'
                '  <p style="margin-bottom: 24px;">{{engagement_date}}</p>\n\n'
                '  <p style="margin-bottom: 24px;">Dear {{client_name}},</p>\n\n'
                '  <p>Thank you for engaging {{firm_name}} to assist your\n'
                '  organization with its federal tax compliance. This letter\n'
                '  confirms the terms of our engagement for the preparation\n'
                '  of your federal Form 990 (or applicable variant) for the\n'
                '  fiscal year referenced above.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Scope of Services</h3>\n\n'
                '  <p>Our engagement includes the preparation of your federal\n'
                '  Form 990, 990-EZ, or 990-N as applicable, along with any\n'
                '  required schedules, based on the financial and program\n'
                '  information your organization provides. We will review\n'
                '  the return for compliance with IRS requirements applicable\n'
                '  to tax-exempt organizations and advise on any issues we\n'
                '  identify in the course of our work.</p>\n\n'
                '  <p>This engagement does not include preparation of state\n'
                '  charitable registration filings, unrelated business income\n'
                '  tax returns (Form 990-T), audit or review of financial\n'
                '  statements, or grant compliance reporting unless separately\n'
                '  agreed upon in writing.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Your Responsibilities</h3>\n\n'
                '  <p>Your organization agrees to provide complete and\n'
                '  accurate financial statements, board-approved budgets,\n'
                '  program service descriptions, compensation information\n'
                '  for officers and key employees, and any other records\n'
                '  necessary to prepare an accurate return. Management and\n'
                '  the board are responsible for the accuracy of all\n'
                '  information provided. Form 990 is a public document\n'
                '  and you should review it carefully before filing.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Professional Fees</h3>\n\n'
                '  <p>Our fee for this engagement is <strong>{{fee_amount}}\n'
                '  </strong>. This fee covers the scope of services described\n'
                '  above. Significant complexity, late delivery of records,\n'
                '  or additional schedules beyond those anticipated may\n'
                '  require a fee adjustment, which we will discuss with you\n'
                '  before proceeding. Payment is due upon delivery of the\n'
                '  completed return.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Public Disclosure</h3>\n\n'
                '  <p>Form 990 is a public document. Your organization is\n'
                '  required to make it available for public inspection upon\n'
                '  request. We will not file your return without your review\n'
                '  and authorization. Please notify us promptly of any\n'
                '  questions or concerns before signing.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Confidentiality</h3>\n\n'
                '  <p>Except for information required by law to be publicly\n'
                '  disclosed, all information shared with {{firm_name}} is\n'
                '  held in strict confidence and will not be released to any\n'
                '  third party without your written authorization.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Limitation of Liability</h3>\n\n'
                '  <p>Our liability in connection with this engagement is\n'
                '  limited to fees paid for the services described herein.\n'
                '  {{firm_name}} is not responsible for penalties, interest,\n'
                '  or consequences arising from inaccurate or incomplete\n'
                '  information provided by your organization.</p>\n\n'
                '  <h3 style="margin-top: 28px; margin-bottom: 8px;\n'
                '    font-size: 12pt; border-bottom: 1px solid #ccc;\n'
                '    padding-bottom: 4px;">Agreement</h3>\n\n'
                '  <p>Please review this letter carefully. Your electronic\n'
                '  signature below, provided on behalf of the organization,\n'
                '  confirms agreement to the terms described and authorizes\n'
                '  {{firm_name}} to prepare your Form 990 as outlined\n'
                '  above.</p>\n\n'
                '  <p style="margin-top: 32px;">Sincerely,</p>\n'
                '  <p style="margin-top: 8px;"><strong>{{firm_owner_name}}\n'
                '  </strong><br>{{firm_name}}</p>\n\n'
                '</div>'
            ),
            "variable_fields": [
                "client_name", "firm_name", "firm_owner_name",
                "firm_address", "firm_phone", "firm_contact_email",
                "engagement_date", "fee_amount",
            ],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    ]
