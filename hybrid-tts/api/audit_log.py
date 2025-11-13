"""
Audit Logging System for Security Events
"""
from datetime import datetime
from typing import Optional, List, Dict
import json
import structlog
from cache.manager import cache_manager

logger = structlog.get_logger()


class AuditLog:
    """Log sensitive operations for audit trails"""

    # Define auditable events
    AUDIT_EVENTS = [
        "api_key_created",
        "api_key_deleted",
        "api_key_revoked",
        "cache_cleared",
        "metrics_flushed",
        "admin_operation",
        "authentication_failure",
        "authentication_success",
        "rate_limit_exceeded",
        "unauthorized_access_attempt",
    ]

    @staticmethod
    async def log_event(
        event: str,
        api_key: Optional[str] = None,
        client_ip: Optional[str] = None,
        details: Optional[Dict] = None,
        severity: str = "INFO"
    ):
        """
        Log audit event to Redis

        Args:
            event: Event type (must be in AUDIT_EVENTS)
            api_key: API key (public part only will be stored)
            client_ip: Client IP address
            details: Additional event details
            severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
        """

        if event not in AuditLog.AUDIT_EVENTS:
            logger.warning("unknown_audit_event", event=event)
            # Still log it, but mark as unknown
            event = f"unknown_{event}"

        # Create audit entry
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "api_key": api_key.split(':')[0] if api_key and ':' in api_key else api_key,
            "client_ip": client_ip,
            "severity": severity,
            "details": details or {}
        }

        try:
            # Store in Redis sorted set (sorted by timestamp)
            score = datetime.utcnow().timestamp()
            cache_manager.redis_client.zadd(
                "audit_log",
                {json.dumps(entry): score}
            )

            # Keep only last 10,000 entries to prevent unbounded growth
            cache_manager.redis_client.zremrangebyrank("audit_log", 0, -10001)

            # Also log structurally for immediate visibility
            logger.info(
                f"audit_{event}",
                api_key=entry["api_key"],
                client_ip=client_ip,
                severity=severity,
                **entry["details"]
            )

        except Exception as e:
            logger.error("audit_log_storage_failed", error=str(e), event=event)

    @staticmethod
    async def get_audit_log(
        limit: int = 100,
        event_filter: Optional[str] = None,
        severity_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve recent audit log entries

        Args:
            limit: Maximum number of entries to return
            event_filter: Filter by event type
            severity_filter: Filter by severity level

        Returns:
            List of audit log entries (most recent first)
        """
        try:
            # Get entries from Redis (most recent first)
            entries = cache_manager.redis_client.zrevrange(
                "audit_log",
                0,
                limit * 2  # Get more than needed for filtering
            )

            # Parse and filter
            parsed_entries = []
            for entry in entries:
                if isinstance(entry, bytes):
                    entry = entry.decode('utf-8')

                parsed = json.loads(entry)

                # Apply filters
                if event_filter and parsed["event"] != event_filter:
                    continue

                if severity_filter and parsed["severity"] != severity_filter:
                    continue

                parsed_entries.append(parsed)

                # Stop if we have enough
                if len(parsed_entries) >= limit:
                    break

            return parsed_entries

        except Exception as e:
            logger.error("audit_log_retrieval_failed", error=str(e))
            return []

    @staticmethod
    async def get_audit_stats() -> Dict:
        """
        Get audit log statistics

        Returns:
            Dictionary with audit log stats
        """
        try:
            # Get total count
            total_count = cache_manager.redis_client.zcard("audit_log")

            # Get recent entries to calculate stats
            recent_entries = await AuditLog.get_audit_log(limit=1000)

            # Count by event type
            event_counts = {}
            severity_counts = {}

            for entry in recent_entries:
                event = entry.get("event", "unknown")
                severity = entry.get("severity", "INFO")

                event_counts[event] = event_counts.get(event, 0) + 1
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

            return {
                "total_entries": total_count,
                "recent_entries_analyzed": len(recent_entries),
                "event_counts": event_counts,
                "severity_counts": severity_counts
            }

        except Exception as e:
            logger.error("audit_stats_failed", error=str(e))
            return {
                "total_entries": 0,
                "error": str(e)
            }


# Helper function to log common security events
async def log_authentication_attempt(
    success: bool,
    api_key: Optional[str],
    client_ip: str,
    endpoint: str
):
    """Log authentication attempt"""
    event = "authentication_success" if success else "authentication_failure"
    severity = "INFO" if success else "WARNING"

    await AuditLog.log_event(
        event=event,
        api_key=api_key,
        client_ip=client_ip,
        details={"endpoint": endpoint},
        severity=severity
    )


async def log_admin_operation(
    operation: str,
    api_key: str,
    client_ip: str,
    details: Optional[Dict] = None
):
    """Log administrative operation"""
    await AuditLog.log_event(
        event="admin_operation",
        api_key=api_key,
        client_ip=client_ip,
        details={"operation": operation, **(details or {})},
        severity="WARNING"
    )
