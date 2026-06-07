# app/services/letter_renderer.py

# Maps every supported merge field name to a human-readable description.
# Used by the UI to show available variables when building a template and
# by validate_context() to catch missing fields before rendering.
SUPPORTED_VARIABLES: dict[str, str] = {
    "client_name": "Full name of the client",
    "client_email": "Client email address",
    "firm_name": "Name of the accounting firm",
    "engagement_name": "Name of the engagement",
    "engagement_type": "Type of engagement",
    "fee_amount": "Fee amount for this engagement",
    "engagement_date": "Date the engagement letter is issued",
    "due_date": "Engagement due date",
    "firm_owner_name": "Name of the firm owner signing the letter",
    "firm_address": "Firm mailing address",
    "firm_phone": "Firm phone number",
    "firm_website": "Firm website URL",
    "firm_contact_email": "Firm contact email address",
}

# Minimal page CSS applied when rendering to PDF so the output looks like
# a real letter rather than a browser viewport screenshot.
_PDF_CSS = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
        font-size: 12pt;
        line-height: 1.6;
        margin: 0;
        padding: 0;
        color: #111;
    }
    @page {
        size: Letter;
        margin: 1in;
    }
"""


def render_template(template_body_html: str, context: dict) -> str:
    """
    Replaces every {{key}} merge field in template_body_html with the
    corresponding value from context.

    Unknown merge fields (keys present in the template but absent from
    context) are left as-is — the caller decides whether that is an error.
    """
    rendered = template_body_html
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered


def validate_context(template_variable_fields: list[str], context: dict) -> list[str]:
    """
    Returns the list of variable_fields required by the template that are
    not present in context. An empty return value means all fields are satisfied.
    """
    return [field for field in template_variable_fields if field not in context]


def render_to_pdf(
    template_body_html: str,
    context: dict,
    firm_settings: dict | None = None,
) -> bytes:
    from app.services.s3 import generate_presigned_url

    logo_html = ""
    if firm_settings:
        s3_key = firm_settings.get("portal_logo_s3_key")
        if s3_key:
            try:
                logo_url = generate_presigned_url(s3_key)
                logo_html = (
                    f'<div style="margin-bottom: 8px;">'
                    f'<img src="{logo_url}" style="max-height: 60px; '
                    f'width: auto; display: block;" /></div>'
                )
            except Exception:
                pass

    rendered_html = render_template(template_body_html, context)

    full_document = (
        "<!DOCTYPE html>"
        "<html>"
        "<head>"
        '<meta charset="utf-8">'
        f"<style>{_PDF_CSS}</style>"
        "</head>"
        "<body>"
        f"{logo_html}"
        f"{rendered_html}"
        "</body>"
        "</html>"
    )

    from weasyprint import HTML
    return HTML(string=full_document).write_pdf()
