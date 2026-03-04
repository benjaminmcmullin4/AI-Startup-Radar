"""Email-based one-time code authentication for Growth Equity Radar."""

from __future__ import annotations

import random
import string
import time

import resend
import streamlit as st

from config import COLORS, FIRM_NAME


OTP_EXPIRY_SECONDS = 600  # 10 minutes
OTP_LENGTH = 6


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def _get_resend_key() -> str:
    """Get Resend API key from Streamlit secrets."""
    try:
        return st.secrets.get("RESEND_API_KEY", "")
    except Exception:
        return ""


def send_otp_email(to_email: str, otp: str) -> bool:
    """Send OTP code via email using Resend. Returns True if sent successfully."""
    api_key = _get_resend_key()

    if not api_key:
        # Fallback: store OTP in session and show it (for demo/dev)
        return True

    try:
        resend.api_key = api_key
        try:
            from_email = st.secrets.get("FROM_EMAIL", "onboarding@resend.dev")
        except Exception:
            from_email = "onboarding@resend.dev"

        resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": f"{FIRM_NAME} — Access Code",
            "html": f"""
        <html>
        <body style="font-family: 'Inter', -apple-system, sans-serif; background: {COLORS['bg']}; padding: 40px;">
            <div style="max-width: 480px; margin: 0 auto; background: {COLORS['white']}; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                <h2 style="color: {COLORS['navy']}; margin-bottom: 8px;">{FIRM_NAME}</h2>
                <p style="color: {COLORS['muted']}; margin-bottom: 24px;">Your one-time access code:</p>
                <div style="background: {COLORS['navy']}; color: white; font-size: 32px; font-weight: 700; letter-spacing: 8px; text-align: center; padding: 20px; border-radius: 8px; margin-bottom: 24px;">
                    {otp}
                </div>
                <p style="color: {COLORS['muted']}; font-size: 14px;">This code expires in 10 minutes. Do not share it.</p>
                <hr style="border: none; border-top: 1px solid {COLORS['light_gray']}; margin: 24px 0;">
                <p style="color: {COLORS['muted']}; font-size: 12px;">{FIRM_NAME}</p>
            </div>
        </body>
        </html>
            """,
        })
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

    # Light-theme auth styles: navy text, teal accent
    st.markdown(f"""
    <style>
        [data-testid="stSidebar"] {{ display: none; }}
        .auth-header {{ text-align: center; padding: 40px 0 20px; }}
        .auth-header h1 {{ color: {COLORS['navy']}; font-size: 2.2em; font-weight: 700; margin-bottom: 4px; }}
        .auth-header .accent {{ color: {COLORS['teal']}; }}
        .auth-header p {{ color: {COLORS['muted']}; font-size: 1.05em; }}
        .auth-subtext {{ color: {COLORS['muted']}; font-size: 0.85em; text-align: center; }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="auth-header">
        <h1>{FIRM_NAME}</h1>
        <p>Growth Equity Deal Sourcing & Screening</p>
    </div>
    """, unsafe_allow_html=True)

    col_spacer1, col_form, col_spacer2 = st.columns([1, 2, 1])

    with col_form:
        if not st.session_state.get("otp_sent"):
            # Step 1: Email input
            st.markdown("##### Enter your email to receive an access code")
            email = st.text_input("Email address", placeholder="analyst@example.com", label_visibility="collapsed")

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
                    if not _get_resend_key():
                        # Dev/demo mode -- show code directly
                        st.session_state["otp_show_fallback"] = True
                    st.rerun()

            st.markdown('<p class="auth-subtext">A 6-digit code will be sent to your email.</p>', unsafe_allow_html=True)

        else:
            # Step 2: OTP verification
            st.markdown(f"##### Enter the 6-digit code sent to **{st.session_state.get('otp_email', '')}**")

            if st.session_state.get("otp_show_fallback"):
                st.info(f"**Dev Mode** — Resend not configured. Your code: `{st.session_state.get('otp_code', '')}`")

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
        f'<p style="text-align:center;color:{COLORS["muted"]};font-size:0.8em;">'
        f'{FIRM_NAME} &mdash; Deal Sourcing & Screening</p>',
        unsafe_allow_html=True,
    )
    return False
