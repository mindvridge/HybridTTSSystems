# Grafana Dashboard Setup for Hybrid TTS Cost Optimizer

This document describes how to set up and use the Grafana monitoring dashboards for the Hybrid TTS Cost Optimizer.

## Quick Start

### Using Docker Compose (Recommended)

Start all services including Grafana:

```bash
cd hybrid-tts
docker-compose up -d
```

Access Grafana at: http://localhost:3000

**Default Credentials:**
- Username: `admin`
- Password: `hybrid-tts-admin`

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Hybrid TTS    │────▶│   Prometheus    │────▶│     Grafana     │
│      API        │     │                 │     │                 │
│  :8000/metrics  │     │    :9090        │     │    :3000        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │
         │
┌─────────────────┐     ┌─────────────────┐
│     Redis       │────▶│ Redis Exporter  │
│    :6379        │     │    :9121        │
└─────────────────┘     └─────────────────┘
```

## Available Dashboards

### 1. Hybrid TTS Overview Dashboard
**Path:** `/d/hybrid-tts-overview`

Main monitoring dashboard with:

- **Key Performance Indicators**
  - Cache Hit Rate (%)
  - Cost Reduction (%)
  - Total Synthesis Requests
  - P95 Latency

- **Request Performance**
  - Requests per Second by Method
  - Synthesis Latency Percentiles (P50, P90, P95, P99)

- **Cache & Cost Analysis**
  - Cache & Cost Performance Over Time
  - Request Distribution by Method (Pie Chart)
  - Request Status Distribution

- **TTS API & Retry Metrics**
  - TTS API Retry Attempts
  - Success vs Exhausted Retries

- **HTTP Requests & Throughput**
  - Requests by Endpoint
  - HTTP Response Time

- **Audio & Data Volume**
  - Audio Bytes Served by Method
  - Total Audio Bytes
  - Error Rate

### 2. Redis Cache Dashboard
**Path:** `/d/hybrid-tts-redis`

Detailed Redis monitoring:

- **Redis Overview**
  - Status (UP/DOWN)
  - Connected Clients
  - Memory Used
  - Total Keys
  - Uptime
  - Keyspace Hit Rate

- **Memory & Performance**
  - Memory Usage Over Time
  - Commands Processed

- **Cache Hit/Miss**
  - Keyspace Hits vs Misses
  - Hit Rate Over Time

- **Network & Connections**
  - Network I/O
  - Client Connections

## Prometheus Metrics

### Application Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `hybrid_tts_synthesis_requests_total` | Counter | method, status | Total synthesis requests |
| `hybrid_tts_synthesis_latency_seconds` | Histogram | method | Synthesis latency |
| `hybrid_tts_cache_hit_rate` | Gauge | - | Cache hit rate (%) |
| `hybrid_tts_cost_reduction` | Gauge | - | Cost reduction (%) |
| `hybrid_tts_audio_bytes_total` | Counter | method | Audio bytes served |
| `hybrid_tts_api_retry_total` | Counter | provider, retry_attempt | TTS API retries |
| `hybrid_tts_api_retry_success_total` | Counter | provider | Successful retries |
| `hybrid_tts_api_retry_exhausted_total` | Counter | provider, error_type | Exhausted retries |
| `http_requests_total` | Counter | method, endpoint, status | HTTP requests |
| `http_request_duration_seconds` | Histogram | method, endpoint | HTTP duration |

### Redis Metrics (via redis_exporter)

| Metric | Description |
|--------|-------------|
| `redis_up` | Redis availability |
| `redis_connected_clients` | Number of clients |
| `redis_memory_used_bytes` | Memory usage |
| `redis_keyspace_hits_total` | Cache hits |
| `redis_keyspace_misses_total` | Cache misses |
| `redis_commands_processed_total` | Commands processed |

## Alerting

Prometheus alerting rules are defined in `monitoring/prometheus/alerts.yml`:

### Application Alerts
- **HybridTTSAPIDown**: API unavailable for 1 minute
- **LowCacheHitRate**: Cache hit rate < 70%
- **CriticalCacheHitRate**: Cache hit rate < 50%
- **HighSynthesisLatency**: P95 latency > 1 second
- **CriticalSynthesisLatency**: P95 latency > 5 seconds
- **HighErrorRate**: Error rate > 5%
- **CriticalErrorRate**: Error rate > 20%
- **LowCostReduction**: Cost reduction < 60%
- **HighRetryRate**: TTS API retry rate > 20%
- **TTSAPIExhaustedRetries**: Retries being exhausted

### Redis Alerts
- **RedisDown**: Redis unavailable
- **RedisHighMemoryUsage**: Memory usage > 80%
- **RedisTooManyConnections**: Connections > 100

## Configuration

### Prometheus Configuration
File: `monitoring/prometheus/prometheus.yml`

```yaml
scrape_configs:
  - job_name: 'hybrid-tts-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /api/v1/monitoring/metrics
    scrape_interval: 10s
```

### Grafana Data Source
File: `monitoring/grafana/provisioning/datasources/datasources.yml`

Prometheus is configured as the default data source.

### Dashboard Provisioning
File: `monitoring/grafana/provisioning/dashboards/dashboards.yml`

Dashboards are auto-loaded from `/var/lib/grafana/dashboards`.

## Customization

### Adding Custom Panels

1. Log into Grafana
2. Open the dashboard
3. Click "Add panel"
4. Select visualization type
5. Write PromQL query
6. Save dashboard

### Creating New Dashboards

1. Click "+" > "Dashboard"
2. Add panels with metrics
3. Save with appropriate tags (`hybrid-tts`)
4. Export JSON to `monitoring/grafana/dashboards/`

### Modifying Alerts

Edit `monitoring/prometheus/alerts.yml`:

```yaml
groups:
  - name: custom-alerts
    rules:
      - alert: CustomAlert
        expr: your_metric > threshold
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Custom alert triggered"
```

Reload Prometheus: `curl -X POST http://localhost:9090/-/reload`

## Troubleshooting

### Grafana Shows "No Data"

1. Check Prometheus target status: http://localhost:9090/targets
2. Verify API is running: `curl http://localhost:8000/api/v1/monitoring/metrics`
3. Check Grafana data source: Settings > Data Sources > Prometheus > Test

### High Memory Usage

1. Adjust Prometheus retention: `--storage.tsdb.retention.time=7d`
2. Reduce scrape frequency in `prometheus.yml`

### Missing Redis Metrics

1. Verify redis_exporter is running: `docker ps | grep redis-exporter`
2. Check exporter logs: `docker logs hybrid-tts-redis-exporter`

## Best Practices

1. **Set appropriate refresh intervals** - Use 10-30s for real-time monitoring
2. **Use template variables** - Enable switching between environments
3. **Create focused dashboards** - One dashboard per concern
4. **Document thresholds** - Explain why specific thresholds are used
5. **Test alerts** - Verify alerts fire correctly before production
