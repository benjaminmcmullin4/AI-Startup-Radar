"""Email-based one-time code authentication for Mercato Traverse Radar."""

import random
import string
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st


OTP_EXPIRY_SECONDS = 600  # 10 minutes
OTP_LENGTH = 6


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def _get_email_config() -> dict:
    """Get SMTP config from Streamlit secrets."""
    try:
        return {
            "smtp_server": st.secrets.get("SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(st.secrets.get("SMTP_PORT", 587)),
            "smtp_user": st.secrets.get("SMTP_USER", ""),
            "smtp_password": st.secrets.get("SMTP_PASSWORD", ""),
            "from_email": st.secrets.get("FROM_EMAIL", ""),
        }
    except Exception:
        return {}


def send_otp_email(to_email: str, otp: str) -> bool:
    """Send OTP code via email. Returns True if sent successfully."""
    config = _get_email_config()

    if not config.get("smtp_user"):
        # Fallback: store OTP in session and show it (for demo/dev)
        return True

    try:
        msg = MIMEMultipart()
        msg["From"] = config.get("from_email", config["smtp_user"])
        msg["To"] = to_email
        msg["Subject"] = "Mercato Traverse Radar — Access Code"

        body = f"""
        <html>
        <body style="font-family: -apple-system, sans-serif; background: #f8f9fa; padding: 40px;">
            <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                <h2 style="color: #1a1a2e; margin-bottom: 8px;">Mercato Traverse Radar</h2>
                <p style="color: #6b7280; margin-bottom: 24px;">Your one-time access code:</p>
                <div style="background: #1a1a2e; color: white; font-size: 32px; font-weight: 700; letter-spacing: 8px; text-align: center; padding: 20px; border-radius: 8px; margin-bottom: 24px;">
                    {otp}
                </div>
                <p style="color: #6b7280; font-size: 14px;">This code expires in 10 minutes. Do not share it.</p>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
                <p style="color: #9ca3af; font-size: 12px;">Mercato Partners &mdash; Building Better</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["smtp_user"], config["smtp_password"])
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False


def _get_allowed_domains() -> list[str]:
    """Get list of allowed email domains from secrets."""
    try:
        domains = st.secrets.get("ALLOWED_EMAIL_DOMAINS", "")
        if domains:
            return [d.strip() for d in domains.split(",")]
    except Exception:
        pass
    return []  # empty = allow all


def render_auth_gate() -> bool:
    """Render the authentication gate. Returns True if user is authenticated."""
    if st.session_state.get("authenticated"):
        return True

    # Center the login form
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
        .auth-header { text-align: center; padding: 40px 0 20px; }
        .auth-header h1 { color: #fafafa; font-size: 2.2em; font-weight: 700; margin-bottom: 4px; }
        .auth-header p { color: #9ca3af; font-size: 1.05em; }
        .auth-subtext { color: #6b7280; font-size: 0.85em; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="auth-header">
        <h1>Mercato Traverse Radar</h1>
        <p>Growth Equity Deal Sourcing & Screening</p>
    </div>
    """, unsafe_allow_html=True)

    col_spacer1, col_form, col_spacer2 = st.columns([1, 2, 1])

    with col_form:
        if not st.session_state.get("otp_sent"):
            # Step 1: Email input
            st.markdown("##### Enter your email to receive an access code")
            email = st.text_input("Email address", placeholder="analyst@mercatopartners.com", label_visibility="collapsed")

            if st.button("Send Access Code", type="primary", use_container_width=True):
                if not email or "@" not in email:
                    st.error("Please enter a valid email address.")
                    return False

                # Check allowed domains
                allowed = _get_allowed_domains()
                if allowed:
                    domain = email.split("@")[1].lower()
                    if domain not in allowed:
                        st.error("Access restricted. Please use an authorized email domain.")
                        return False

                otp = _generate_otp()
                st.session_state["otp_code"] = otp
                st.session_state["otp_email"] = email
                st.session_state["otp_time"] = time.time()

                if send_otp_email(email, otp):
                    st.session_state["otp_sent"] = True
                    config = _get_email_config()
                    if not config.get("smtp_user"):
                        # Dev/demo mode — show code directly
                        st.session_state["otp_show_fallback"] = True
                    st.rerun()

            st.markdown('<p class="auth-subtext">A 6-digit code will be sent to your email.</p>', unsafe_allow_html=True)

        else:
            # Step 2: OTP verification
            st.markdown(f"##### Enter the 6-digit code sent to **{st.session_state.get('otp_email', '')}**")

            if st.session_state.get("otp_show_fallback"):
                st.info(f"**Dev Mode** — SMTP not configured. Your code: `{st.session_state.get('otp_code', '')}`")

            code_input = st.text_input("Access code", max_chars=6, placeholder="000000", label_visibility="collapsed")

            col_verify, col_resend = st.columns(2)
            with col_verify:
                if st.button("Verify", type="primary", use_container_width=True):
                    stored_otp = st.session_state.get("otp_code", "")
                    otp_time = st.session_state.get("otp_time", 0)

                    if time.time() - otp_time > OTP_EXPIRY_SECONDS:
                        st.error("Code expired. Please request a new one.")
                        st.session_state["otp_sent"] = False
                        st.rerun()
                    elif code_input == stored_otp:
                        st.session_state["authenticated"] = True
                        st.session_state["user_email"] = st.session_state.get("otp_email", "")
                        # Clean up
                        for key in ("otp_code", "otp_email", "otp_time", "otp_sent", "otp_show_fallback"):
                            st.session_state.pop(key, None)
                        st.rerun()
                    else:
                        st.error("Invalid code. Please try again.")

            with col_resend:
                if st.button("Resend Code", use_container_width=True):
                    st.session_state["otp_sent"] = False
                    st.rerun()

    st.markdown("---")
    st.markdown(
        '<p style="text-align:center;color:#4b5563;font-size:0.8em;">'
        'Mercato Partners &mdash; Building Better &mdash; Since 2007</p>',
        unsafe_allow_html=True,
    )
    return False
