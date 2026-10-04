import base64
import binascii
import hashlib
import hmac
import ipaddress
import os
import secrets
import time
from collections import defaultdict
from fastapi import Request
from .config import settings

# In-memory sliding window rate limiters:
# _IP_RATE_BUCKETS maps "client_ip:category" -> list of timestamps
_IP_RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)
# _VISITOR_RATE_BUCKETS maps "visitor_id" -> list of timestamps in last 60s
_VISITOR_RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)
# _VISITOR_DAILY_COUNTS maps "visitor_id" -> list of timestamps in last 24h
_VISITOR_DAILY_COUNTS: dict[str, list[float]] = defaultdict(list)
_LAST_CLEANUP: float = 0.0


def is_trusted_proxy(ip: str) -> bool:
    """Check if an IP address belongs to configured trusted proxies."""
    if not ip:
        return False
    trusted = settings.TRUSTED_PROXIES
    if '*' in trusted:
        return True
    if ip in trusted or ip in ('127.0.0.1', '::1', 'testclient', 'localhost'):
        return True
    for entry in trusted:
        if '/' in entry:
            try:
                if ipaddress.ip_address(ip) in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                pass
    return False


def get_client_ip(request: Request) -> str:
    """
    Extract real client IP address safely.
    ONLY trusts proxy headers (X-Forwarded-For, X-Real-IP) if the direct peer
    connection is from a configured trusted proxy. If the direct peer is untrusted,
    proxy headers are ignored to prevent IP-spoofing and rate-limit evasion.
    """
    peer_ip = request.client.host if request.client else '127.0.0.1'
    if not is_trusted_proxy(peer_ip):
        # Peer is not trusted; ignore any forged headers sent by the client
        return peer_ip

    # Peer is a trusted proxy: parse X-Forwarded-For from right to left
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        parts = [p.strip() for p in forwarded.split(',') if p.strip()]
        # Walk backwards to find the rightmost IP that is not a trusted proxy
        for ip in reversed(parts):
            if not is_trusted_proxy(ip):
                return ip
        if parts:
            return parts[0]

    real_ip = request.headers.get('x-real-ip')
    if real_ip:
        ip = real_ip.strip()
        if not is_trusted_proxy(ip):
            return ip

    return peer_ip


def sign_session_token(visitor_id: str) -> str:
    """Sign visitor ID with HMAC-SHA256 to ensure authenticity."""
    secret = settings.SESSION_SECRET.encode('utf-8')
    sig = hmac.new(secret, visitor_id.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{visitor_id}.{sig}"


def verify_session_token(token: str | None) -> str | None:
    """Verify HMAC signature and return visitor ID, or None if invalid/tampered."""
    if not token or '.' not in token:
        return None
    try:
        visitor_id, sig = token.rsplit('.', 1)
        if not visitor_id.startswith('v_') or visitor_id == '__legacy_archive__':
            return None
        secret = settings.SESSION_SECRET.encode('utf-8')
        expected = hmac.new(secret, visitor_id.encode('utf-8'), hashlib.sha256).hexdigest()
        if secrets.compare_digest(sig, expected):
            return visitor_id
    except Exception:
        return None
    return None


def generate_visitor_id() -> str:
    """Generate a high-entropy anonymous visitor ID."""
    return 'v_' + secrets.token_urlsafe(24)


def generate_csrf_token() -> str:
    """Generate a random CSRF token."""
    return secrets.token_urlsafe(24)


def _cleanup_rate_limits(now: float):
    cutoff_short = now - 120.0
    for k in list(_IP_RATE_BUCKETS.keys()):
        _IP_RATE_BUCKETS[k] = [t for t in _IP_RATE_BUCKETS[k] if t > cutoff_short]
        if not _IP_RATE_BUCKETS[k]:
            del _IP_RATE_BUCKETS[k]

    for k in list(_VISITOR_RATE_BUCKETS.keys()):
        _VISITOR_RATE_BUCKETS[k] = [t for t in _VISITOR_RATE_BUCKETS[k] if t > cutoff_short]
        if not _VISITOR_RATE_BUCKETS[k]:
            del _VISITOR_RATE_BUCKETS[k]

    cutoff_day = now - 86400.0
    for k in list(_VISITOR_DAILY_COUNTS.keys()):
        _VISITOR_DAILY_COUNTS[k] = [t for t in _VISITOR_DAILY_COUNTS[k] if t > cutoff_day]
        if not _VISITOR_DAILY_COUNTS[k]:
            del _VISITOR_DAILY_COUNTS[k]


def check_rate_limit(
    client_ip: str,
    visitor_or_path: str,
    path: str | None = None,
    return_detail: bool = False,
):
    """
    Sliding window rate limiter protecting public endpoints from abuse, DDoS,
    and runaway automated AI spending.
    Supports:
      check_rate_limit(client_ip, path) -> (is_allowed, retry_after)
      check_rate_limit(client_ip, visitor_id, path, return_detail=True) -> (is_allowed, retry_after, detail)
    """
    if path is None:
        actual_path = visitor_or_path
        visitor_id = None
    else:
        visitor_id = visitor_or_path
        actual_path = path

    default_detail = 'Rate limit exceeded. Please wait a moment before sending more requests.'

    if os.getenv('FORMA_DISABLE_RATE_LIMIT', '').lower() in ('1', 'true', 'yes'):
        return (True, 0, '') if return_detail else (True, 0)

    now = time.time()
    global _LAST_CLEANUP
    if now - _LAST_CLEANUP > 60:
        _cleanup_rate_limits(now)
        _LAST_CLEANUP = now

    is_chat = actual_path == '/api/chat'
    is_attach = '/attachments' in actual_path

    # 1. IP rate limiting
    if is_chat:
        ip_limit = settings.RATE_LIMIT_CHAT_PER_MINUTE
        ip_window = 60.0
        ip_key = f"{client_ip}:chat"
    elif is_attach:
        ip_limit = settings.RATE_LIMIT_ATTACHMENTS_PER_MINUTE
        ip_window = 60.0
        ip_key = f"{client_ip}:attach"
    else:
        ip_limit = settings.RATE_LIMIT_GENERAL_PER_MINUTE
        ip_window = 60.0
        ip_key = f"{client_ip}:general"

    cutoff = now - ip_window
    ip_ts = [t for t in _IP_RATE_BUCKETS[ip_key] if t > cutoff]
    if len(ip_ts) >= ip_limit:
        oldest = ip_ts[0]
        retry_after = max(1, int(ip_window - (now - oldest)))
        detail = 'Rate limit exceeded for this IP. Please wait a moment.'
        return (False, retry_after, detail) if return_detail else (False, retry_after)

    # 2. Visitor generation rate limits and spending controls (for /api/chat)
    if is_chat and visitor_id and visitor_id != '__legacy_archive__':
        v_min_limit = settings.RATE_LIMIT_VISITOR_CHAT_PER_MINUTE
        v_min_window = 60.0
        v_cutoff = now - v_min_window
        v_ts = [t for t in _VISITOR_RATE_BUCKETS[visitor_id] if t > v_cutoff]
        if len(v_ts) >= v_min_limit:
            oldest = v_ts[0]
            retry_after = max(1, int(v_min_window - (now - oldest)))
            detail = 'Too many chat requests for this session. Please wait a moment.'
            return (False, retry_after, detail) if return_detail else (False, retry_after)

        v_day_limit = settings.RATE_LIMIT_VISITOR_CHAT_PER_DAY
        v_day_window = 86400.0
        day_cutoff = now - v_day_window
        day_ts = [t for t in _VISITOR_DAILY_COUNTS[visitor_id] if t > day_cutoff]
        if len(day_ts) >= v_day_limit:
            oldest = day_ts[0]
            retry_after = max(1, int(v_day_window - (now - oldest)))
            detail = 'Daily generation allowance reached for this session. Please try again tomorrow.'
            return (False, retry_after, detail) if return_detail else (False, retry_after)

        v_ts.append(now)
        _VISITOR_RATE_BUCKETS[visitor_id] = v_ts
        day_ts.append(now)
        _VISITOR_DAILY_COUNTS[visitor_id] = day_ts

    ip_ts.append(now)
    _IP_RATE_BUCKETS[ip_key] = ip_ts
    return (True, 0, '') if return_detail else (True, 0)


def clear_rate_limits():
    """Clear all rate limit buckets (useful for test isolation)."""
    _IP_RATE_BUCKETS.clear()
    _VISITOR_RATE_BUCKETS.clear()
    _VISITOR_DAILY_COUNTS.clear()


def get_allowed_origins() -> set[str]:
    """Return the set of origins permitted to make state-changing requests."""
    allowed = {
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://testserver',
        'http://test',
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
