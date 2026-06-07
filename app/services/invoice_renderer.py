# app/services/invoice_renderer.py

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.invoice import Invoice
    from app.models.firm import Firm
    from app.models.client import Client


_STATUS_COLORS: dict[str, str] = {
    "draft": "#6b7280",
    "sent": "#2563eb",
    "paid": "#16a34a",
    "overdue": "#dc2626",
    "void": "#6b7280",
}


def _fmt_currency(value) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _fmt_date(d) -> str:
    if d is None:
        return "No due date"
    try:
        return d.strftime("%B %d, %Y")
    except Exception:
        return str(d)


def _build_invoice_html(
    invoice: "Invoice",
    firm: "Firm",
    client: "Client",
    engagement_name: str | None = None,
    logo_url: str | None = None,
) -> str:
    status_val = invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status)
    badge_color = _STATUS_COLORS.get(status_val, "#6b7280")

    line_items = invoice.line_items or []
    line_rows = ""
    for item in line_items:
        desc = item.get("description", "")
        qty = item.get("quantity", "0")
        unit = item.get("unit_price", "0")
        total = item.get("total", "0")
        line_rows += f"""
        <tr>
            <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;">{desc}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;text-align:center;">{qty}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;text-align:right;">{_fmt_currency(unit)}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;text-align:right;">{_fmt_currency(total)}</td>
        </tr>"""

    tax_pct = float(invoice.tax_rate) * 100 if invoice.tax_rate is not None else 0.0

    engagement_section = ""
    if invoice.engagement_id is not None and engagement_name:
        engagement_section = f"""
        <div style="margin-bottom:24px;">
            <span style="color:#6b7280;font-size:13px;">For:</span>
            <span style="font-size:14px;font-weight:600;margin-left:6px;">{engagement_name}</span>
        </div>"""

    notes_section = ""
    if invoice.notes_client_visible:
        notes_section = f"""
        <div style="margin-top:32px;padding:16px;background:#f9fafb;border-radius:6px;border:1px solid #e5e7eb;">
            <div style="font-weight:600;margin-bottom:6px;color:#111111;">Notes:</div>
            <div style="font-size:14px;color:#374151;">{invoice.notes_client_visible}</div>
        </div>"""

    client_name = getattr(client, "display_name", None) or getattr(client, "name", "")
    client_email = getattr(client, "email", "") or ""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {{ size: Letter; margin: 0.75in; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        font-size: 14px;
        color: #111827;
        background: #ffffff;
        margin: 0;
        padding: 0;
    }}
</style>
</head>
<body>
    <!-- HEADER -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:40px;padding-bottom:24px;border-bottom:3px solid #111111;">
        <div>
            {'<img src="' + logo_url + '" style="max-height:60px;width:auto;display:block;margin-bottom:4px;" />' if logo_url else f'<div style="font-size:26px;font-weight:700;color:#111111;">{firm.name}</div>'}
        </div>
        <div style="text-align:right;">
            <div style="font-size:28px;font-weight:700;color:#111111;letter-spacing:2px;">INVOICE</div>
            <div style="font-size:16px;color:#6b7280;margin-top:4px;">{invoice.invoice_number}</div>
            <div style="margin-top:8px;">
                <span style="display:inline-block;padding:3px 12px;border-radius:12px;font-size:12px;font-weight:600;color:#ffffff;background:{badge_color};">{status_val.upper()}</span>
            </div>
        </div>
    </div>

    <!-- META ROW -->
    <div style="display:flex;justify-content:space-between;margin-bottom:32px;">
        <div>
            <div style="font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Bill To</div>
            <div style="font-size:16px;font-weight:600;color:#111111;">{client_name}</div>
            <div style="font-size:14px;color:#6b7280;">{client_email}</div>
        </div>
        <div style="text-align:right;">
            <div style="margin-bottom:6px;">
                <span style="font-size:12px;color:#6b7280;">Date Issued:</span>
                <span style="font-size:13px;font-weight:500;margin-left:6px;">{_fmt_date(invoice.created_at)}</span>
            </div>
            <div>
                <span style="font-size:12px;color:#6b7280;">Due Date:</span>
                <span style="font-size:13px;font-weight:500;margin-left:6px;">{_fmt_date(invoice.due_date)}</span>
            </div>
        </div>
    </div>

    {engagement_section}

    <!-- LINE ITEMS TABLE -->
    <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
        <thead>
            <tr style="background:#111111;color:#ffffff;">
                <th style="padding:12px;text-align:left;font-size:13px;font-weight:600;">Description</th>
                <th style="padding:12px;text-align:center;font-size:13px;font-weight:600;">Qty</th>
                <th style="padding:12px;text-align:right;font-size:13px;font-weight:600;">Unit Price</th>
                <th style="padding:12px;text-align:right;font-size:13px;font-weight:600;">Total</th>
            </tr>
        </thead>
        <tbody>
            {line_rows}
        </tbody>
    </table>

    <!-- TOTALS -->
    <div style="display:flex;justify-content:flex-end;margin-bottom:32px;">
        <table style="min-width:260px;border-collapse:collapse;">
            <tr>
                <td style="padding:8px 12px;color:#6b7280;font-size:13px;">Subtotal</td>
                <td style="padding:8px 12px;text-align:right;font-size:13px;">{_fmt_currency(invoice.subtotal)}</td>
            </tr>
            <tr>
                <td style="padding:8px 12px;color:#6b7280;font-size:13px;">Tax ({tax_pct:.2f}%)</td>
                <td style="padding:8px 12px;text-align:right;font-size:13px;">{_fmt_currency(invoice.tax_amount)}</td>
            </tr>
            <tr style="border-top:2px solid #111111;">
                <td style="padding:10px 12px;font-size:16px;font-weight:700;color:#111111;">Total</td>
                <td style="padding:10px 12px;text-align:right;font-size:16px;font-weight:700;color:#111111;">{_fmt_currency(invoice.total_amount)}</td>
            </tr>
        </table>
    </div>

    {notes_section}

    <!-- FOOTER -->
    <div style="margin-top:48px;padding-top:16px;border-top:1px solid #e5e7eb;text-align:center;color:#6b7280;font-size:13px;">
        <div>Thank you for your business.</div>
        <div style="margin-top:4px;font-weight:600;color:#111111;">{firm.name}</div>
    </div>
</body>
</html>"""
    return html


def render_invoice_to_pdf(
    invoice: "Invoice",
    firm: "Firm",
    client: "Client",
    engagement_name: str | None = None,
) -> bytes:
    from weasyprint import HTML
    firm_settings = firm.settings or {} if firm.settings else {}
    s3_key = firm_settings.get("portal_logo_s3_key")
    logo_url = None
    if s3_key:
        try:
            from app.services.s3 import generate_presigned_url
            logo_url = generate_presigned_url(s3_key)
        except Exception:
            pass
    html_content = _build_invoice_html(
        invoice, firm, client, engagement_name, logo_url=logo_url
    )
    return HTML(string=html_content).write_pdf()
