from __future__ import annotations

from decimal import Decimal
from html import escape
from pathlib import Path


def money(value: object) -> str:
    return f"${Decimal(str(value or 0)):,.2f}"


def render_html(document: dict, copy_number: int) -> str:
    services = "".join(
        "<tr><td>{}</td><td>{}</td><td class='amount'>{}</td></tr>".format(
            escape(str(item.get("description", "Service"))),
            escape(str(item.get("employeeName", ""))),
            money(item.get("amount")),
        )
        for item in document.get("serviceItems", [])
    )
    decided_tips = "".join(
        "<tr><td>Tip / award — {}</td><td>{}</td><td class='amount'>{}</td></tr>".format(
            escape(str(item.get("reason", "Tip"))),
            escape(str(item.get("employeeName", item.get("employeeId", "")))),
            money(item.get("amount")),
        )
        for item in document.get("tipItems", [])
    )
    recipients = "".join(
        "<tr><td>{}</td><td class='write'></td><td class='write'></td></tr>".format(
            escape(str(item.get("employeeName", "")))
        )
        for item in document.get("tipRecipients", [])
    )
    store = document.get("store") or {}
    customer = document.get("customer") or {}
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Bill {escape(str(document['billNumber']))}</title>
<style>
@page{{size:auto;margin:10mm}}body{{font:14px system-ui,sans-serif;color:#111;max-width:760px;margin:auto}}
h1{{margin-bottom:0}}.meta{{color:#555}}table{{width:100%;border-collapse:collapse;margin:18px 0}}
th,td{{padding:8px;border-bottom:1px solid #bbb;text-align:left}}.amount{{text-align:right}}
.write{{height:34px;border-bottom:1px solid #111}}.signature{{margin-top:32px;border-top:1px solid #111;padding-top:6px}}
.copy{{float:right}}@media print{{button{{display:none}}}}
</style></head><body>
<span class="copy">Copy {copy_number} · Bill version {document['documentVersion']}</span>
<h1>{escape(str(store.get('name') or 'Bay300 store'))}</h1>
<p class="meta">{escape(str(store.get('address') or ''))}<br>Bill {escape(str(document['billNumber']))}
 · Customer {escape(str(customer.get('name') or 'Walk-in customer'))}</p>
<table><thead><tr><th>Item</th><th>Employee</th><th class="amount">Amount</th></tr></thead>
<tbody>{services}{decided_tips}</tbody><tfoot><tr><th colspan="2">Service total</th>
<th class="amount">{money(document.get('serviceTotal'))}</th></tr></tfoot></table>
<h2>Customer tip / extra award</h2>
<p>Write an amount and optional reason beside each intended recipient. Zero or blank means no tip.</p>
<table><thead><tr><th>Recipient</th><th>Amount</th><th>Reason</th></tr></thead><tbody>{recipients}</tbody></table>
<p class="signature">Customer confirmation / signature and date</p>
<p class="meta">Return this form to store staff. Staff must enter the customer decision in Bay300 before final Receiving.</p>
</body></html>"""


def write_html(document: dict, copy_number: int, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_html(document, copy_number), encoding="utf-8")
    return destination


def write_pdf(document: dict, copy_number: int, destination: Path) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    destination.parent.mkdir(parents=True, exist_ok=True)
    styles=getSampleStyleSheet()
    store=document.get("store") or {}; customer=document.get("customer") or {}
    story=[Paragraph(escape(str(store.get("name") or "Bay300 store")),styles["Title"]),
        Paragraph(escape(str(store.get("address") or "")),styles["Normal"]),
        Paragraph(f"Bill {escape(str(document['billNumber']))} · Version {document['documentVersion']} · Copy {copy_number}",styles["Heading2"]),
        Paragraph(f"Customer: {escape(str(customer.get('name') or 'Walk-in customer'))}",styles["Normal"]),Spacer(1,12)]
    service_rows=[["Item","Employee","Amount"]]+[[
        str(item.get("description") or "Service"),str(item.get("employeeName") or ""),money(item.get("amount"))
    ] for item in document.get("serviceItems",[])]
    service_rows.append(["Service total","",money(document.get("serviceTotal"))])
    services=Table(service_rows,colWidths=[3.2*inch,2.0*inch,1.1*inch],repeatRows=1)
    services.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8f2ef")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("ALIGN",(-1,0),(-1,-1),"RIGHT"),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),6),
    ]));story.extend([services,Spacer(1,18),Paragraph("Customer tip / extra award",styles["Heading2"]),
        Paragraph("Write an amount and optional reason beside each intended recipient. Zero or blank means no tip.",styles["Normal"]),Spacer(1,6)])
    tip_rows=[["Recipient","Amount","Reason"]]+[[
        str(item.get("employeeName") or ""),"",""
    ] for item in document.get("tipRecipients",[])]
    tips=Table(tip_rows,colWidths=[2.1*inch,1.4*inch,2.8*inch],rowHeights=[None]+[0.48*inch]*(len(tip_rows)-1),repeatRows=1)
    tips.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8f2ef")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("PADDING",(0,0),(-1,-1),6),
    ]));story.extend([tips,Spacer(1,28),Paragraph("Customer confirmation / signature and date: __________________________________________",styles["Normal"]),Spacer(1,12),
        Paragraph("Return this form to store staff. Staff must enter the customer decision in Bay300 before final Receiving.",styles["Normal"])])
    SimpleDocTemplate(str(destination),pagesize=letter,rightMargin=0.55*inch,leftMargin=0.55*inch,
        topMargin=0.5*inch,bottomMargin=0.5*inch,title=f"Bill {document['billNumber']}").build(story)
    return destination
