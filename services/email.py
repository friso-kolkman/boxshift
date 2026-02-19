"""Email service using Resend."""

import config

def send_waitlist_confirmation(to_email: str, position: int):
    """Send waitlist confirmation email."""
    if not config.RESEND_API_KEY:
        return None

    import resend
    resend.api_key = config.RESEND_API_KEY

    return resend.Emails.send({
        "from": config.EMAIL_FROM,
        "to": [to_email],
        "subject": f"Je staat op de BoxShift waitlist (#{position})",
        "html": f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; color: #e6edf3; background: #0d1117; padding: 40px; border-radius: 12px;">
    <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 24px; margin: 0; color: #e6edf3;">
            <span style="color: #f85149;">Box</span><span style="color: #58a6ff;">Shift</span>
        </h1>
    </div>

    <h2 style="font-size: 20px; color: #e6edf3; margin-bottom: 8px;">Welkom op de waitlist!</h2>
    <p style="color: #8b949e; font-size: 15px; line-height: 1.6;">
        Bedankt voor je aanmelding. Je bent <strong style="color: #58a6ff;">nummer #{position}</strong> op de waitlist.
    </p>

    <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin: 24px 0;">
        <p style="color: #8b949e; font-size: 14px; margin: 0 0 8px 0;">Wat is BoxShift?</p>
        <p style="color: #e6edf3; font-size: 15px; line-height: 1.6; margin: 0;">
            Vanaf 2028 betaal je in Box 3 <strong>36% belasting over ongerealiseerde winsten</strong>.
            Via een beleggings-BV (Box 2) betaal je alleen over wat je echt verdient.
            BoxShift regelt de BV-oprichting en volledige administratie met AI.
        </p>
    </div>

    <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin: 24px 0;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="color: #f85149; font-size: 24px; font-weight: 700; padding: 8px 0; text-align: center;">36%</td>
                <td style="color: #8b949e; padding: 8px 16px; text-align: center; font-size: 20px;">&rarr;</td>
                <td style="color: #3fb950; font-size: 24px; font-weight: 700; padding: 8px 0; text-align: center;">19%</td>
            </tr>
            <tr>
                <td style="color: #8b949e; font-size: 12px; text-align: center;">Box 3 (nieuw)</td>
                <td></td>
                <td style="color: #8b949e; font-size: 12px; text-align: center;">Box 2 (BV)</td>
            </tr>
        </table>
    </div>

    <p style="color: #8b949e; font-size: 14px; line-height: 1.6;">
        We nemen contact op zodra BoxShift live gaat. In de tussentijd kun je alvast je
        <a href="https://boxshift.nl/static/calculator.html" style="color: #58a6ff;">besparing berekenen</a>.
    </p>

    <hr style="border: none; border-top: 1px solid #30363d; margin: 32px 0;">
    <p style="color: #484f58; font-size: 12px; text-align: center; margin: 0;">
        BoxShift &mdash; Van Box 3 naar Box 2, zonder gedoe.<br>
        <a href="https://boxshift.nl" style="color: #484f58;">boxshift.nl</a>
    </p>
</div>
""",
    })
