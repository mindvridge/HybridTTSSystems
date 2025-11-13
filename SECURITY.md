# Security Features - Hybrid TTS Cost Optimizer

## Overview

The Hybrid TTS API has been secured with comprehensive protection against common attacks and abuse. This document outlines all security features and how to use them.

## Security Features Implemented

### ✅ 1. Rate Limiting

**Protection Against:** DDoS attacks, API abuse, cost amplification

**Implementation:**
- Synthesis endpoints: 10 requests/minute per IP
- Batch synthesis: 5 requests/minute per IP
- Admin operations: 5 requests/hour per IP
- Public endpoints: 100 requests/minute per IP

**Response when exceeded:**
```json
{
  "detail": "Rate limit exceeded: 10 per 1 minute",
  "error": "TOO_MANY_REQUESTS"
}
```
HTTP Status: `429 Too Many Requests`

### ✅ 2. API Key Authentication

**Protection Against:** Unauthorized access, cache tampering

**Required for:**
- `POST /api/v1/cache/clear` - Clear entire cache
- `POST /api/v1/monitoring/flush` - Flush metrics
- `POST /api/v1/admin/api-keys/*` - API key management
- `GET /api/v1/admin/audit-log` - View audit logs

**Usage:**
```bash
curl -X POST http://localhost:8000/api/v1/cache/clear \
  -H "X-API-Key: hybrid-tts_admin_ABC123:secret_key_here"
```

### ✅ 3. Input Validation & Size Limits

**Protection Against:** Memory exhaustion, cost amplification

**Limits:**
- Maximum text length: 5,000 characters
- Maximum batch size: 100 items
- Maximum request body: 10 MB

**Response when exceeded:**
```json
{
  "detail": "Text cannot exceed 5000 characters"
}
```
HTTP Status: `400 Bad Request`

### ✅ 4. CORS Restriction

**Protection Against:** Cross-site attacks, unauthorized web access

**Configuration:**
- Development mode (`DEBUG=True`): All origins allowed
- Production mode: Only specified domains in `CORS_ORIGINS`

**Environment variable:**
```env
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### ✅ 5. Security Headers

**Protection Against:** XSS, clickjacking, MIME sniffing

**Headers added to all responses:**
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HTTPS only)
- `Content-Security-Policy: default-src 'self'`
- `Referrer-Policy: strict-origin-when-cross-origin`

### ✅ 6. Audit Logging

**Protection Against:** Accountability gaps, forensic analysis

**Logged events:**
- API key creation/deletion/revocation
- Cache clear operations
- Metrics flush operations
- Authentication failures
- Rate limit violations
- All admin operations

**Access audit logs:**
```bash
curl -X GET http://localhost:8000/api/v1/admin/audit-log \
  -H "X-API-Key: your_api_key"
```

---

## Getting Started

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

The security system requires `slowapi==0.1.9` for rate limiting.

### 2. Create Initial API Key

**Important:** You need an API key before the API will accept admin operations.

```bash
# From the project root
python hybrid-tts/scripts/create_api_key.py admin
```

**Output:**
```
======================================================================
🔐 API Key Created Successfully!
======================================================================

Public Key: hybrid-tts_admin_a1b2c3d4
Full API Key: hybrid-tts_admin_a1b2c3d4:AbCdEf123456789...

⚠️  IMPORTANT:
  - Save this API key securely - it will NOT be shown again
  - Use it in the X-API-Key header for admin operations
  - Example: curl -H 'X-API-Key: <full_api_key>' ...
======================================================================
```

**Save the Full API Key** - you'll need it for admin operations.

### 3. Configure Environment

Create or update `.env` file:

```env
# Security Settings
API_REQUIRE_AUTH=true
API_KEY_ENABLED=true
ENABLE_RATE_LIMITING=true
ENABLE_SECURITY_HEADERS=true
ENABLE_AUDIT_LOG=true

# Rate Limits (optional - defaults provided)
RATE_LIMIT_SYNTHESIS=10/minute
RATE_LIMIT_BATCH=5/minute
RATE_LIMIT_ADMIN=5/hour

# Request Limits
MAX_TEXT_LENGTH=5000
MAX_BATCH_SIZE=100
MAX_REQUEST_SIZE_MB=10

# CORS (production only)
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# For development/testing, you can disable security:
# API_REQUIRE_AUTH=false
# ENABLE_RATE_LIMITING=false
```

### 4. Start the API

```bash
cd hybrid-tts
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Check logs for security initialization:**
```
{"event": "rate_limiting_enabled", "limits": {...}}
{"event": "request_size_limits_enabled", "max_size_mb": 10}
{"event": "security_headers_enabled"}
{"event": "cors_restricted_mode", "allowed_origins": [...]}
```

---

## Using the API

### Public Endpoints (No Authentication)

```bash
# Health check
curl http://localhost:8000/health

# Synthesize speech (rate limited: 10/min)
curl -X POST http://localhost:8000/api/v1/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'

# Get stats
curl http://localhost:8000/api/v1/stats
```

### Admin Endpoints (Require API Key)

```bash
# Clear cache (REQUIRES API KEY)
curl -X POST http://localhost:8000/api/v1/cache/clear \
  -H "X-API-Key: hybrid-tts_admin_ABC:secret123"

# Create additional API key
curl -X POST "http://localhost:8000/api/v1/admin/api-keys/create?name=service1" \
  -H "X-API-Key: hybrid-tts_admin_ABC:secret123"

# List all API keys
curl http://localhost:8000/api/v1/admin/api-keys/list \
  -H "X-API-Key: hybrid-tts_admin_ABC:secret123"

# Revoke API key
curl -X DELETE http://localhost:8000/api/v1/admin/api-keys/hybrid-tts_service1_XYZ \
  -H "X-API-Key: hybrid-tts_admin_ABC:secret123"

# View audit log
curl "http://localhost:8000/api/v1/admin/audit-log?limit=50" \
  -H "X-API-Key: hybrid-tts_admin_ABC:secret123"
```

---

## API Key Management

### Create API Key

```bash
# Method 1: Using the script (recommended for first key)
python hybrid-tts/scripts/create_api_key.py myservice

# Method 2: Using the API (requires existing key)
curl -X POST "http://localhost:8000/api/v1/admin/api-keys/create?name=myservice" \
  -H "X-API-Key: existing_key_here"
```

### List API Keys

```bash
curl http://localhost:8000/api/v1/admin/api-keys/list \
  -H "X-API-Key: your_admin_key"
```

**Response:**
```json
{
  "status": "success",
  "api_keys": [
    "hybrid-tts_admin_a1b2c3d4",
    "hybrid-tts_service1_e5f6g7h8"
  ],
  "count": 2
}
```

### Revoke API Key

```bash
curl -X DELETE http://localhost:8000/api/v1/admin/api-keys/hybrid-tts_service1_e5f6g7h8 \
  -H "X-API-Key: your_admin_key"
```

---

## Testing Security

### Test Rate Limiting

```bash
# Send 20 requests quickly (should hit rate limit after ~10)
for i in {1..20}; do
  curl -X POST http://localhost:8000/api/v1/synthesize \
    -H "Content-Type: application/json" \
    -d '{"text":"test"}' \
    -w "\nStatus: %{http_code}\n"
  sleep 0.1
done
```

Expected: HTTP 429 after 10 requests

### Test API Key Authentication

```bash
# Without key - should fail
curl -X POST http://localhost:8000/api/v1/cache/clear
# Expected: 401 Unauthorized

# With invalid key - should fail
curl -X POST http://localhost:8000/api/v1/cache/clear \
  -H "X-API-Key: invalid_key"
# Expected: 401 Unauthorized

# With valid key - should succeed
curl -X POST http://localhost:8000/api/v1/cache/clear \
  -H "X-API-Key: your_valid_key"
# Expected: 200 OK
```

### Test Input Validation

```bash
# Text too long - should fail
curl -X POST http://localhost:8000/api/v1/synthesize \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"$(python3 -c 'print("x"*6000)')\"}"
# Expected: 400 Bad Request

# Batch too large - should fail
curl -X POST http://localhost:8000/api/v1/synthesize/batch \
  -H "Content-Type: application/json" \
  -d "{\"texts\":$(python3 -c 'import json; print(json.dumps(["test"]*101))')}"
# Expected: 400 Bad Request
```

---

## Security Configuration

All security settings are in `config.py`:

```python
# Security Settings
API_REQUIRE_AUTH: bool = True
API_KEY_ENABLED: bool = True

# Rate Limiting
ENABLE_RATE_LIMITING: bool = True
RATE_LIMIT_SYNTHESIS: str = "10/minute"
RATE_LIMIT_BATCH: str = "5/minute"
RATE_LIMIT_ADMIN: str = "5/hour"
RATE_LIMIT_PUBLIC: str = "100/minute"

# Request Limits
MAX_TEXT_LENGTH: int = 5000
MAX_BATCH_SIZE: int = 100
MAX_REQUEST_SIZE_MB: int = 10

# CORS
CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

# Security Headers
ENABLE_SECURITY_HEADERS: bool = True
ENABLE_HTTPS_REDIRECT: bool = False  # Set True in production

# Audit Logging
ENABLE_AUDIT_LOG: bool = True
AUDIT_LOG_RETENTION_DAYS: int = 90
```

Override in `.env` file or environment variables.

---

## Troubleshooting

### "Missing API key" Error

**Problem:** Getting 401 on admin endpoints

**Solution:**
1. Create an API key: `python hybrid-tts/scripts/create_api_key.py admin`
2. Include in header: `-H "X-API-Key: your_full_key"`
3. Check format: `public_key:secret`

### Rate Limit Exceeded

**Problem:** Getting 429 errors

**Solution:**
1. Wait for rate limit window to reset
2. Reduce request frequency
3. For testing, disable: `ENABLE_RATE_LIMITING=false` in `.env`

### CORS Error in Browser

**Problem:** Browser blocks requests from your frontend

**Solution:**
1. Add your frontend URL to `CORS_ORIGINS` in `.env`
2. Example: `CORS_ORIGINS=http://localhost:3000,https://app.example.com`
3. Restart API server

### API Key Not Working

**Problem:** Valid API key returns 401

**Solutions:**
1. Check Redis is running: `redis-cli ping`
2. Verify key format: should be `public:secret`
3. Check if key was revoked: `curl /api/v1/admin/api-keys/list`
4. Recreate key if necessary

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Create strong API keys for all services
- [ ] Set `DEBUG=False` in environment
- [ ] Configure `CORS_ORIGINS` with actual domains (remove `*`)
- [ ] Enable HTTPS/TLS
- [ ] Set `ENABLE_HTTPS_REDIRECT=True`
- [ ] Review and adjust rate limits based on expected traffic
- [ ] Set up monitoring alerts for:
  - Rate limit violations
  - Authentication failures
  - Admin operations
- [ ] Regularly review audit logs
- [ ] Implement API key rotation policy
- [ ] Set up Redis persistence for API keys
- [ ] Configure firewall to restrict Redis access
- [ ] Enable Redis authentication (if not already)
- [ ] Test all security features in staging environment

---

## Security Best Practices

1. **API Keys:**
   - Never commit API keys to version control
   - Use environment variables or secret management
   - Rotate keys regularly (every 90 days)
   - Use different keys for different services
   - Revoke compromised keys immediately

2. **Rate Limits:**
   - Monitor rate limit violations
   - Adjust limits based on legitimate traffic patterns
   - Consider per-user limits for multi-tenant systems

3. **Audit Logs:**
   - Review logs regularly for suspicious activity
   - Set up alerts for critical operations
   - Keep logs for at least 90 days
   - Export to external SIEM if available

4. **Network Security:**
   - Use HTTPS in production (always)
   - Restrict Redis port (6379) to localhost
   - Use firewall rules to limit API access
   - Consider VPN or IP whitelisting for admin endpoints

5. **Monitoring:**
   - Track authentication failures
   - Monitor rate limit hits
   - Alert on cache clear operations
   - Watch for unusual traffic patterns

---

## Support

For security issues or questions:
- Review this documentation
- Check audit logs for suspicious activity
- Test in development environment first
- Contact your security team for critical issues

---

**Last Updated:** 2025-01-13
**Security Version:** 1.0.0
