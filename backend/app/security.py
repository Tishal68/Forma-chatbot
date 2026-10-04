import base64
import binascii
import os
import secrets
import time
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

# In-memory sliding window rate limiter: maps "client_ip:category" -> list of timestamps
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = defaultdict(list)
_LAST_CLEANUP: float = 0.0


def get_client_ip(request: Request) -> str:
    """Extract real client IP from forward headers or direct connection."""
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()
    real_ip = request.headers.get('x-real-ip')
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else '127.0.0.1'


def check_rate_limit(client_ip: str, path: str) -> tuple[bool, int]:
    """
    Sliding window rate limiter protecting public endpoints from abuse,
    DDoS attacks, and runaway automated credit consumption.
    Returns: (is_allowed, retry_after_seconds)
    """
    if os.getenv('FORMA_DISABLE_RATE_LIMIT', '').lower() in ('1', 'true', 'yes'):
        return True, 0

    now = time.time()
    global _LAST_CLEANUP
    if now - _LAST_CLEANUP > 60:
        cutoff = now - 60
        for k in list(_RATE_LIMIT_BUCKETS.keys()):
            _RATE_LIMIT_BUCKETS[k] = [t for t in _RATE_LIMIT_BUCKETS[k] if t > cutoff]
            if not _RATE_LIMIT_BUCKETS[k]:
                del _RATE_LIMIT_BUCKETS[k]
        _LAST_CLEANUP = now

    # Path-specific limits: stricter for heavy LLM chat generation
    if path == '/api/chat':
        limit = int(os.getenv('RATE_LIMIT_CHAT_PER_MINUTE', '60'))
        window = 60.0
    elif '/attachments' in path:
        limit = int(os.getenv('RATE_LIMIT_ATTACHMENTS_PER_MINUTE', '40'))
        window = 60.0
    else:
        limit = int(os.getenv('RATE_LIMIT_GENERAL_PER_MINUTE', '240'))
        window = 60.0

    bucket_key = f"{client_ip}:{path == '/api/chat'}"
    window_cutoff = now - window
    timestamps = [t for t in _RATE_LIMIT_BUCKETS[bucket_key] if t > window_cutoff]

    if len(timestamps) >= limit:
        oldest = timestamps[0]
        retry_after = max(1, int(window - (now - oldest)))
        return False, retry_after

    timestamps.append(now)
    _RATE_LIMIT_BUCKETS[bucket_key] = timestamps
    return True, 0


def clear_rate_limits():
    """Clear all rate limit buckets (useful for test isolation)."""
    _RATE_LIMIT_BUCKETS.clear()


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
    Apply modern enterprise-grade security headers (OWASP guidelines):
    - Transport Encryption (HSTS)
    - Anti-clickjacking (X-Frame-Options: DENY)
    - MIME sniffing protection (X-Content-Type-Options: nosniff)
    - Cross-site scripting filter (X-XSS-Protection)
    - Content Security Policy (CSP)
    - Referrer & Permissions policies
    """
    headers = response.headers
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['X-Frame-Options'] = 'DENY'
    headers['X-XSS-Protection'] = '1; mode=block'
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
