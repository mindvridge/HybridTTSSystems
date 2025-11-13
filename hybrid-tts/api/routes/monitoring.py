"""
Monitoring, metrics, and dashboard endpoints
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, HTMLResponse
from typing import Optional
import structlog
from datetime import datetime, timedelta

from monitoring import metrics_collector
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

logger = structlog.get_logger()

router = APIRouter()

# Prometheus metrics
synthesis_requests_total = Counter(
    "hybrid_tts_synthesis_requests_total",
    "Total number of synthesis requests",
    ["method", "status"],
)

synthesis_latency_seconds = Histogram(
    "hybrid_tts_synthesis_latency_seconds",
    "Synthesis request latency in seconds",
    ["method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

cache_hit_rate_gauge = Gauge(
    "hybrid_tts_cache_hit_rate", "Current cache hit rate percentage"
)

cost_reduction_gauge = Gauge(
    "hybrid_tts_cost_reduction", "Estimated cost reduction percentage"
)

audio_bytes_total = Counter(
    "hybrid_tts_audio_bytes_total", "Total audio bytes served", ["method"]
)

# TTS API Retry metrics
tts_retry_total = Counter(
    "hybrid_tts_api_retry_total",
    "Total number of TTS API retry attempts",
    ["provider", "retry_attempt"],
)

tts_retry_success_total = Counter(
    "hybrid_tts_api_retry_success_total",
    "Total number of successful TTS API calls after retries",
    ["provider"],
)

tts_retry_exhausted_total = Counter(
    "hybrid_tts_api_retry_exhausted_total",
    "Total number of TTS API calls that failed after all retries",
    ["provider", "error_type"],
)


@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus metrics endpoint
    Returns metrics in Prometheus exposition format
    """
    try:
        # Update gauges with current values
        summary = metrics_collector.get_summary_stats()
        cache_hit_rate_gauge.set(summary.get("cache_hit_rate", 0) * 100)
        cost_reduction_gauge.set(summary.get("estimated_cost_reduction", 0) * 100)

        # Generate Prometheus format
        metrics_output = generate_latest()

        return Response(content=metrics_output, media_type=CONTENT_TYPE_LATEST)

    except Exception as e:
        logger.error("metrics_generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate metrics")


@router.get("/stats")
async def get_monitoring_stats():
    """
    Get comprehensive monitoring statistics
    """
    try:
        summary = metrics_collector.get_summary_stats()
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": summary,
        }
    except Exception as e:
        logger.error("stats_retrieval_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")


@router.get("/report")
async def get_performance_report():
    """
    Get detailed performance report with target comparisons
    """
    try:
        report = metrics_collector.generate_report()
        return report
    except Exception as e:
        logger.error("report_generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/timeseries")
async def get_time_series_data(
    start_time: Optional[str] = None, end_time: Optional[str] = None, hours: int = 24
):
    """
    Get time-series metrics data for visualization

    Args:
        start_time: ISO format datetime string (optional)
        end_time: ISO format datetime string (optional)
        hours: Number of hours to look back (default: 24)
    """
    try:
        # If no start_time provided, calculate from hours parameter
        if not start_time:
            start_dt = datetime.utcnow() - timedelta(hours=hours)
            start_time = start_dt.isoformat()

        metrics_data = metrics_collector.get_time_series(start_time, end_time)

        return {
            "start_time": start_time,
            "end_time": end_time or datetime.utcnow().isoformat(),
            "data_points": len(metrics_data),
            "metrics": metrics_data,
        }
    except Exception as e:
        logger.error("timeseries_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to retrieve time series data"
        )


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """
    Real-time monitoring dashboard
    Displays key metrics and visualizations
    """
    try:
        summary = metrics_collector.get_summary_stats()
        report = metrics_collector.generate_report()

        # Generate HTML dashboard
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hybrid TTS - Monitoring Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1419;
            color: #e6edf3;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #30363d;
        }}

        h1 {{
            font-size: 32px;
            margin-bottom: 10px;
            color: #58a6ff;
        }}

        .subtitle {{
            color: #8b949e;
            font-size: 14px;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
        }}

        .card h2 {{
            font-size: 18px;
            margin-bottom: 15px;
            color: #58a6ff;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .metric {{
            margin-bottom: 15px;
        }}

        .metric-label {{
            font-size: 12px;
            color: #8b949e;
            margin-bottom: 5px;
        }}

        .metric-value {{
            font-size: 28px;
            font-weight: 600;
            color: #e6edf3;
        }}

        .metric-unit {{
            font-size: 14px;
            color: #8b949e;
            margin-left: 4px;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}

        .badge-success {{
            background: #238636;
            color: #fff;
        }}

        .badge-warning {{
            background: #9e6a03;
            color: #fff;
        }}

        .badge-error {{
            background: #da3633;
            color: #fff;
        }}

        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #30363d;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }}

        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #58a6ff, #1f6feb);
            transition: width 0.3s ease;
        }}

        .stats-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #30363d;
        }}

        .stats-row:last-child {{
            border-bottom: none;
        }}

        .stats-label {{
            color: #8b949e;
            font-size: 14px;
        }}

        .stats-value {{
            color: #e6edf3;
            font-weight: 600;
        }}

        .target-comparison {{
            display: flex;
            gap: 20px;
            margin-top: 15px;
        }}

        .target-item {{
            flex: 1;
        }}

        .refresh-info {{
            text-align: center;
            margin-top: 30px;
            padding: 15px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            color: #8b949e;
            font-size: 13px;
        }}

        .auto-refresh {{
            color: #58a6ff;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 Hybrid TTS Cost Optimizer</h1>
            <div class="subtitle">Real-time Monitoring Dashboard - Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        </header>

        <div class="grid">
            <!-- Key Metrics -->
            <div class="card">
                <h2>📊 Key Performance Metrics</h2>
                <div class="metric">
                    <div class="metric-label">Cache Hit Rate</div>
                    <div class="metric-value">
                        {summary.get('cache_hit_rate', 0) * 100:.1f}<span class="metric-unit">%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {summary.get('cache_hit_rate', 0) * 100}%"></div>
                    </div>
                </div>
                <div class="metric">
                    <div class="metric-label">Cost Reduction</div>
                    <div class="metric-value">
                        {summary.get('estimated_cost_reduction', 0) * 100:.1f}<span class="metric-unit">%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {summary.get('estimated_cost_reduction', 0) * 100}%"></div>
                    </div>
                </div>
                <div class="metric">
                    <div class="metric-label">Average Latency</div>
                    <div class="metric-value">
                        {summary.get('avg_latency_ms', 0):.0f}<span class="metric-unit">ms</span>
                    </div>
                </div>
            </div>

            <!-- Request Statistics -->
            <div class="card">
                <h2>📈 Request Statistics</h2>
                <div class="stats-row">
                    <span class="stats-label">Total Requests</span>
                    <span class="stats-value">{summary.get('total_requests', 0):,}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Cache Hits</span>
                    <span class="stats-value">{summary.get('cache_hits', 0):,}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Cache Misses</span>
                    <span class="stats-value">{summary.get('cache_misses', 0):,}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">TTS Syntheses</span>
                    <span class="stats-value">{summary.get('tts_syntheses', 0):,}</span>
                </div>
            </div>

            <!-- Method Distribution -->
            <div class="card">
                <h2>🎯 Match Method Distribution</h2>
                <div class="stats-row">
                    <span class="stats-label">Exact Matches</span>
                    <span class="stats-value">{summary.get('method_distribution', {}).get('exact_rate', 0) * 100:.1f}%</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Fuzzy Matches</span>
                    <span class="stats-value">{summary.get('method_distribution', {}).get('fuzzy_rate', 0) * 100:.1f}%</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Semantic Matches</span>
                    <span class="stats-value">{summary.get('method_distribution', {}).get('semantic_rate', 0) * 100:.1f}%</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">TTS Synthesis</span>
                    <span class="stats-value">{summary.get('method_distribution', {}).get('tts_rate', 0) * 100:.1f}%</span>
                </div>
            </div>
        </div>

        <!-- Target Comparison -->
        <div class="card">
            <h2>🎯 Target Achievement</h2>
            <div class="target-comparison">
                <div class="target-item">
                    <div class="metric-label">Cache Hit Rate Target</div>
                    <div class="stats-row">
                        <span class="stats-label">Target</span>
                        <span class="stats-value">{report['targets']['cache_hit_rate']['target'] * 100:.0f}%</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Actual</span>
                        <span class="stats-value">{report['targets']['cache_hit_rate']['actual'] * 100:.1f}%</span>
                    </div>
                    <div style="margin-top: 10px;">
                        <span class="badge {'badge-success' if report['targets']['cache_hit_rate']['met'] else 'badge-warning'}">
                            {'✓ Target Met' if report['targets']['cache_hit_rate']['met'] else '⚠ Below Target'}
                        </span>
                    </div>
                </div>

                <div class="target-item">
                    <div class="metric-label">Cost Reduction Target</div>
                    <div class="stats-row">
                        <span class="stats-label">Target</span>
                        <span class="stats-value">{report['targets']['cost_reduction']['target'] * 100:.0f}%</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Actual</span>
                        <span class="stats-value">{report['targets']['cost_reduction']['actual'] * 100:.1f}%</span>
                    </div>
                    <div style="margin-top: 10px;">
                        <span class="badge {'badge-success' if report['targets']['cost_reduction']['met'] else 'badge-warning'}">
                            {'✓ Target Met' if report['targets']['cost_reduction']['met'] else '⚠ Below Target'}
                        </span>
                    </div>
                </div>
            </div>

            <div style="margin-top: 20px; text-align: center;">
                <span class="badge {'badge-success' if report['overall_target_met'] else 'badge-error'}">
                    {'✓ All Targets Met' if report['overall_target_met'] else '✗ Targets Not Met'}
                </span>
            </div>
        </div>

        <div class="refresh-info">
            <span class="auto-refresh">🔄 Auto-refresh:</span> Page refreshes every 30 seconds
        </div>
    </div>

    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {{
            location.reload();
        }}, 30000);
    </script>
</body>
</html>
        """

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error("dashboard_generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate dashboard")


@router.post("/flush")
async def flush_metrics():
    """
    Manually flush metrics to disk
    """
    try:
        metrics_collector.flush()
        return {"status": "success", "message": "Metrics flushed to disk"}
    except Exception as e:
        logger.error("metrics_flush_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to flush metrics")
