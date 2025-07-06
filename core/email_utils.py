from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

def send_templated_email(subject, template_name_html, template_name_txt, context, recipient_list):
    """
    Sends an email using HTML and plain text templates.

    Args:
        subject (str): The email subject.
        template_name_html (str): Path to the HTML email template (e.g., 'emails/welcome.html').
        template_name_txt (str): Path to the plain text email template (e.g., 'emails/welcome.txt').
        context (dict): Context dictionary for rendering the templates.
        recipient_list (list): A list or tuple of recipient email addresses.
    """
    if not recipient_list:
        print("No recipients provided for email.")
        return

    try:
        # Render HTML content
        html_content = render_to_string(template_name_html, context)

        # Render plain text content (either from a specific .txt template or by stripping HTML)
        if template_name_txt:
            text_content = render_to_string(template_name_txt, context)
        else:
            text_content = strip_tags(html_content) # Fallback: strip tags from HTML

        # Ensure sender is configured, default to DEFAULT_FROM_EMAIL
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost')

        msg = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
        msg.attach_alternative(html_content, "text/html")

        msg.send()
        print(f"Email '{subject}' sent successfully to: {', '.join(recipient_list)}")
        return True

    except Exception as e:
        # Log the error appropriately in a real application
        print(f"Error sending email '{subject}' to {', '.join(recipient_list)}: {e}")
        # Consider raising the exception or returning a failure indicator
        return False

# Example usage (will be called from elsewhere, e.g., user signup signal):
# send_templated_email(
#     subject="Welcome to Our Platform!",
#     template_name_html="emails/welcome_email.html",
#     template_name_txt="emails/welcome_email.txt",
#     context={"user_name": "John Doe", "login_url": "https://example.com/login"},
#     recipient_list=["john.doe@example.com"]
# )
