import resend
from django.conf import settings

# Set API key once
resend.api_key = settings.RESEND_API_KEY


def send_reset_email(email, reset_link):
    """
    Send password reset email using Resend API.
    """
    try:
        resend.Emails.send({
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": email,
            "subject": "Password Reset Request",
            "html": f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                        .button {{ 
                            display: inline-block; 
                            padding: 12px 24px; 
                            background-color: #007bff; 
                            color: white; 
                            text-decoration: none; 
                            border-radius: 5px; 
                            margin: 20px 0;
                        }}
                        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>Password Reset Request</h2>
                        <p>Hello,</p>
                        <p>Click the button below to reset your password:</p>
                        <a href="{reset_link}" class="button">Reset Password</a>
                        <p>If you didn’t request this, please ignore this email.</p>
                        <div class="footer">
                            <p>This link expires in 24 hours.</p>
                        </div>
                    </div>
                </body>
                </html>
            """
        })
        return True
    except Exception as e:
        print("Resend error:", e)
        return False


def send_email_html(subject, to_email, html_content, from_email=None):
    """
    Send a generic HTML email using Resend API.
    """
    try:
        resend.Emails.send({
            "from": from_email or settings.DEFAULT_FROM_EMAIL,
            "to": to_email,
            "subject": subject,
            "html": html_content,
        })
        return True
    except Exception as e:
        print("Resend error:", e)
        return False
