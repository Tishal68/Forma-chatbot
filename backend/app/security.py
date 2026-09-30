import base64
import binascii
import os
import secrets
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

def get_allowed_origins() -> set[str]:
    """Return the set of origins permitted to make state-changing requests."""
    allowed = {
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    }
    configured = os.getenv('ALLOWED_ORIGINS', '')
    if configured:
        allowed.update(x.strip().rstrip('/') for x in configured.split(',') if x.strip())
    if os.getenv('RENDER_EXTERNAL_URL'):
        allowed.add(os.environ['RENDER_EXTERNAL_URL'].rstrip('/'))
    if os.getenv('RAILWAY_PUBLIC_DOMAIN'):
        allowed.add('https://' + os.environ['RAILWAY_PUBLIC_DOMAIN'].rstrip('/'))
    return allowed


def verify_basic_auth(auth_header: str | None, expected_user: str, expected_pass: str) -> bool:
    """Verify HTTP Basic Auth credentials using constant-time comparison."""
    if not auth_header or not expected_user or not expected_pass:
        return False
    try:
        scheme, encoded = auth_header.split(' ', 1)
        if scheme.lower() != 'basic':
            return False
        supplied_user, supplied_pass = base64.b64decode(encoded, validate=True).decode('utf-8').split(':', 1)
        user_matches = secrets.compare_digest(supplied_user.encode('utf-8'), expected_user.encode('utf-8'))
        pass_matches = secrets.compare_digest(supplied_pass.encode('utf-8'), expected_pass.encode('utf-8'))
        return user_matches and pass_matches
    except (ValueError, UnicodeError, binascii.Error):
        return False


def apply_security_headers(response, is_production: bool = False, is_https: bool = False):
    """
    Apply modern security hardening headers:
    - Transport Encryption (HSTS)
    - Anti-clickjacking (X-Frame-Options)
    - MIME sniffing protection (X-Content-Type-Options)
    - Content Security Policy (CSP)
    - Referrer & Permissions policies
    """
    headers = response.headers
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['X-Frame-Options'] = 'DENY'
    headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), browsing-topics=()'

    # Content Security Policy
    headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    # HTTP Strict Transport Security (HSTS) enforces HTTPS for 1 year
    if is_production or is_https:
        headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
