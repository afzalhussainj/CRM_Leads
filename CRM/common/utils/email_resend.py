from resend import Resend
from django.conf import settings

client = Resend(settings.RESEND_API_KEY)


def send_reset_email(email, reset_link):
    """
    Send password reset email using Resend API.
    
    Args:
        email: Recipient email address
        reset_link: Password reset link
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        response = client.emails.send({
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [email],
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
                        <p>We received a request to reset your password. Click the button below to reset it:</p>
                        <a href="{reset_link}" class="button">Reset Password</a>
                        <p>Or copy and paste this link into your browser:</p>
                        <p><a href="{reset_link}">{reset_link}</a></p>
                        <p>If you didn't request this password reset, please ignore this email.</p>
                        <div class="footer">
                            <p>This link will expire in 24 hours for security reasons.</p>
                        </div>
                    </div>
                </body>
                </html>
            """
        })
        return True
    except Exception as e:
        print(f"Resend error: {e}")
        return False


def send_email_html(subject, to_email, html_content, from_email=None):
    """
    Send a generic HTML email using Resend API.
    
    Args:
        subject: Email subject
        to_email: Recipient email address
        html_content: HTML content of the email
        from_email: Sender email (optional, uses DEFAULT_FROM_EMAIL if not provided)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    try:
        response = client.emails.send({
            "from": from_email,
            "to": [to_email] if isinstance(to_email, str) else to_email,
            "subject": subject,
            "html": html_content
        })
        return True
    except Exception as e:
        print(f"Resend error: {e}")
        return False
