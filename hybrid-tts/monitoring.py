"""
Monitoring and metrics collection system
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
import structlog

from config import settings

logger = structlog.get_logger()


@dataclass
class MetricEvent:
    """Represents a single metric event"""

    timestamp: str
    event_type: str  # 'synthesis', 'cache_hit', 'cache_miss', 'match'
    latency_ms: float
    method: str  # 'exact', 'fuzzy', 'semantic', 'tts'
    text_length: int
    audio_size: int = 0
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = None


class MetricsCollector:
    """
    Collects and persists metrics for analysis
    Tracks key performance indicators (KPIs)
    """

    def __init__(self):
        self.metrics: List[MetricEvent] = []
        self.log_path = Path(settings.METRICS_LOG_PATH)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Summary statistics
        self.summary = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "semantic_matches": 0,
            "tts_syntheses": 0,
            "total_latency_ms": 0.0,
            "total_audio_size": 0,
        }

        logger.info("metrics_collector_initialized", log_path=str(self.log_path))

    def record_event(self, event: MetricEvent):
        """Record a metric event"""
        self.metrics.append(event)

        # Update summary
        self.summary["total_requests"] += 1

        if event.method == "exact":
            self.summary["cache_hits"] += 1
            self.summary["exact_matches"] += 1
        elif event.method in ["fuzzy", "semantic"]:
            self.summary["cache_hits"] += 1
            if event.method == "fuzzy":
                self.summary["fuzzy_matches"] += 1
            else:
                self.summary["semantic_matches"] += 1
        elif event.method == "tts_synthesis":
            self.summary["cache_misses"] += 1
            self.summary["tts_syntheses"] += 1

        self.summary["total_latency_ms"] += event.latency_ms
        self.summary["total_audio_size"] += event.audio_size

        # Periodic flush to disk
        if len(self.metrics) >= 100:
            self.flush()

    def record_synthesis(
        self,
        method: str,
        latency_ms: float,
        text_length: int,
        audio_size: int = 0,
        confidence_score: float = 0.0,
        **metadata,
    ):
        """Convenience method to record synthesis event"""
        event = MetricEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type="synthesis",
            latency_ms=latency_ms,
            method=method,
            text_length=text_length,
            audio_size=audio_size,
            confidence_score=confidence_score,
            metadata=metadata,
        )
        self.record_event(event)

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics"""
        total = self.summary["total_requests"]

        if total == 0:
            return self.summary

        cache_hit_rate = self.summary["cache_hits"] / total
        avg_latency = self.summary["total_latency_ms"] / total

        # Calculate cost savings estimate
        # Assume TTS costs 100 units per synthesis
        # Cache hit saves 100 units (only storage cost ~5 units)
        tts_cost = 100
        cache_cost = 5
        total_cost_without_cache = total * tts_cost
        actual_cost = (
            self.summary["cache_hits"] * cache_cost
            + self.summary["tts_syntheses"] * tts_cost
        )
        cost_reduction = 1 - (actual_cost / total_cost_without_cache)

        return {
            **self.summary,
            "cache_hit_rate": round(cache_hit_rate, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "estimated_cost_reduction": round(cost_reduction, 4),
            "method_distribution": {
                "exact_rate": round(self.summary["exact_matches"] / total, 4),
                "fuzzy_rate": round(self.summary["fuzzy_matches"] / total, 4),
                "semantic_rate": round(self.summary["semantic_matches"] / total, 4),
                "tts_rate": round(self.summary["tts_syntheses"] / total, 4),
            },
        }

    def flush(self):
        """Flush metrics to disk"""
        if not self.metrics:
            return

        try:
            # Append to log file
            with open(self.log_path, "a", encoding="utf-8") as f:
                for event in self.metrics:
                    f.write(json.dumps(asdict(event)) + "\n")

            logger.info("metrics_flushed", count=len(self.metrics))
            self.metrics.clear()

        except Exception as e:
            logger.error("metrics_flush_failed", error=str(e))

    def get_time_series(
        self, start_time: str = None, end_time: str = None
    ) -> List[Dict]:
        """
        Get time-series data for visualization
        Returns metrics within time range
        """
        # Load from file
        metrics_data = []

        if self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            event = json.loads(line)
                            # Filter by time range if specified
                            if start_time and event["timestamp"] < start_time:
                                continue
                            if end_time and event["timestamp"] > end_time:
                                continue
                            metrics_data.append(event)
            except Exception as e:
                logger.error("metrics_load_failed", error=str(e))

        # Add in-memory metrics
        for event in self.metrics:
            event_dict = asdict(event)
            if start_time and event_dict["timestamp"] < start_time:
                continue
            if end_time and event_dict["timestamp"] > end_time:
                continue
            metrics_data.append(event_dict)

        return metrics_data

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        summary = self.get_summary_stats()

        # Check if meeting targets
        target_hit_rate = settings.TARGET_CACHE_HIT_RATE
        target_cost_reduction = settings.TARGET_COST_REDUCTION

        actual_hit_rate = summary.get("cache_hit_rate", 0)
        actual_cost_reduction = summary.get("estimated_cost_reduction", 0)

        meets_targets = (
            actual_hit_rate >= target_hit_rate
            and actual_cost_reduction >= target_cost_reduction
        )

        return {
            "summary": summary,
            "targets": {
                "cache_hit_rate": {
                    "target": target_hit_rate,
                    "actual": actual_hit_rate,
                    "met": actual_hit_rate >= target_hit_rate,
                },
                "cost_reduction": {
                    "target": target_cost_reduction,
                    "actual": actual_cost_reduction,
                    "met": actual_cost_reduction >= target_cost_reduction,
                },
            },
            "overall_target_met": meets_targets,
            "generated_at": datetime.utcnow().isoformat(),
        }


# Global metrics collector
metrics_collector = MetricsCollector()
