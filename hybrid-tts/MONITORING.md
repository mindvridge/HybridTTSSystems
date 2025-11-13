# 모니터링 시스템 통합 문서

## 개요

Hybrid TTS Cost Optimizer에 완전히 통합된 모니터링 시스템이 구현되었습니다. 이 시스템은 실시간 메트릭 수집, Prometheus 통합, 그리고 시각적 대시보드를 제공합니다.

## 주요 기능

### 1. 자동 메트릭 수집 ✅

모든 synthesis 요청에서 다음 메트릭이 자동으로 수집됩니다:

- **요청 메소드**: exact, fuzzy, semantic, tts_synthesis
- **응답 시간 (latency)**: 밀리초 단위
- **텍스트 길이**: 입력 텍스트의 문자 수
- **오디오 크기**: 생성된 오디오 바이트 수
- **신뢰도 점수**: 매칭 알고리즘의 confidence score

### 2. Prometheus 메트릭 ✅

다음 Prometheus 메트릭이 자동으로 수집되고 `/api/v1/monitoring/metrics` 엔드포인트에서 노출됩니다:

#### Synthesis 메트릭
- `hybrid_tts_synthesis_requests_total` (Counter)
  - Labels: `method`, `status`
  - 총 synthesis 요청 수

- `hybrid_tts_synthesis_latency_seconds` (Histogram)
  - Labels: `method`
  - Synthesis 요청 지연시간 (초)
  - Buckets: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0

- `hybrid_tts_cache_hit_rate` (Gauge)
  - 현재 캐시 히트율 (%)

- `hybrid_tts_cost_reduction` (Gauge)
  - 추정 비용 절감율 (%)

- `hybrid_tts_audio_bytes_total` (Counter)
  - Labels: `method`
  - 총 제공된 오디오 바이트 수

#### HTTP 요청 메트릭
- `http_requests_total` (Counter)
  - Labels: `method`, `endpoint`, `status`
  - 총 HTTP 요청 수

- `http_request_duration_seconds` (Histogram)
  - Labels: `method`, `endpoint`
  - HTTP 요청 지연시간 (초)

### 3. 실시간 대시보드 ✅

**URL**: `http://localhost:8000/api/v1/monitoring/dashboard`

대시보드는 다음을 표시합니다:

- **주요 성능 지표**
  - 캐시 히트율 (진행 바 포함)
  - 비용 절감율 (진행 바 포함)
  - 평균 응답 시간

- **요청 통계**
  - 총 요청 수
  - 캐시 히트/미스
  - TTS 합성 수

- **매칭 메소드 분포**
  - Exact 매칭 비율
  - Fuzzy 매칭 비율
  - Semantic 매칭 비율
  - TTS 합성 비율

- **목표 달성도**
  - 캐시 히트율 목표 vs 실제
  - 비용 절감 목표 vs 실제
  - 전체 목표 달성 여부

**특징**:
- 30초마다 자동 새로고침
- 다크 모드 디자인
- 반응형 레이아웃
- 실시간 업데이트

## API 엔드포인트

### 모니터링 엔드포인트

#### 1. Prometheus 메트릭
```http
GET /api/v1/monitoring/metrics
```

Prometheus 형식으로 메트릭을 반환합니다.

**사용 예시**:
```bash
curl http://localhost:8000/api/v1/monitoring/metrics
```

#### 2. 통계 요약
```http
GET /api/v1/monitoring/stats
```

현재 시스템 통계를 JSON 형식으로 반환합니다.

**응답 예시**:
```json
{
  "status": "ok",
  "timestamp": "2025-11-13T12:00:00.000000",
  "metrics": {
    "total_requests": 1000,
    "cache_hits": 850,
    "cache_misses": 150,
    "cache_hit_rate": 0.85,
    "avg_latency_ms": 45.2,
    "estimated_cost_reduction": 0.78,
    "method_distribution": {
      "exact_rate": 0.60,
      "fuzzy_rate": 0.15,
      "semantic_rate": 0.10,
      "tts_rate": 0.15
    }
  }
}
```

#### 3. 성능 보고서
```http
GET /api/v1/monitoring/report
```

목표 대비 성능 보고서를 반환합니다.

**응답 예시**:
```json
{
  "summary": { ... },
  "targets": {
    "cache_hit_rate": {
      "target": 0.80,
      "actual": 0.85,
      "met": true
    },
    "cost_reduction": {
      "target": 0.70,
      "actual": 0.78,
      "met": true
    }
  },
  "overall_target_met": true,
  "generated_at": "2025-11-13T12:00:00.000000"
}
```

#### 4. 시계열 데이터
```http
GET /api/v1/monitoring/timeseries?hours=24
GET /api/v1/monitoring/timeseries?start_time=2025-11-13T00:00:00&end_time=2025-11-13T23:59:59
```

시간대별 메트릭 데이터를 반환합니다.

**쿼리 파라미터**:
- `hours`: 조회할 시간 (기본: 24시간)
- `start_time`: 시작 시간 (ISO 8601 형식)
- `end_time`: 종료 시간 (ISO 8601 형식)

#### 5. 대시보드
```http
GET /api/v1/monitoring/dashboard
```

HTML 형식의 실시간 모니터링 대시보드를 반환합니다.

#### 6. 메트릭 플러시
```http
POST /api/v1/monitoring/flush
```

메모리의 메트릭을 디스크에 강제로 기록합니다.

## 구현 세부사항

### 파일 구조

```
hybrid-tts/
├── monitoring.py                 # 메트릭 수집 코어 로직
├── api/
│   ├── main.py                   # 모니터링 라우터 통합
│   ├── middleware.py             # 자동 요청 추적 미들웨어
│   └── routes/
│       ├── monitoring.py         # 모니터링 엔드포인트
│       └── synthesis.py          # 메트릭 수집 통합
└── logs/
    └── metrics.json              # 메트릭 로그 파일
```

### 통합 지점

#### 1. Synthesis 엔드포인트 (`api/routes/synthesis.py`)

모든 synthesis 요청에서 자동으로 메트릭을 수집합니다:

```python
# Exact 매칭
metrics_collector.record_synthesis(
    method="exact",
    latency_ms=latency,
    text_length=len(text_to_synthesize),
    audio_size=len(cached_audio),
    confidence_score=1.0,
)

# Prometheus 메트릭 업데이트
synthesis_requests_total.labels(method="exact", status="success").inc()
synthesis_latency_seconds.labels(method="exact").observe(latency / 1000)
audio_bytes_total.labels(method="exact").inc(len(cached_audio))
```

#### 2. 미들웨어 (`api/middleware.py`)

모든 HTTP 요청을 자동으로 추적합니다:

```python
class MonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        latency = time.time() - start_time

        # 메트릭 기록
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status=status_code
        ).inc()

        return response
```

#### 3. 애플리케이션 라이프사이클 (`api/main.py`)

시작 및 종료 시 메트릭을 관리합니다:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("monitoring_initialized", metrics_enabled=settings.ENABLE_METRICS)

    yield

    # Shutdown - 메트릭 플러시
    if settings.ENABLE_METRICS:
        metrics_collector.flush()
        logger.info("metrics_flushed_on_shutdown")
```

## Prometheus 통합 방법

### 1. Prometheus 설정

`prometheus.yml` 예시:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'hybrid-tts'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/monitoring/metrics'
```

### 2. Prometheus 실행

```bash
prometheus --config.file=prometheus.yml
```

### 3. Grafana 대시보드

Grafana에서 다음 쿼리를 사용할 수 있습니다:

```promql
# 캐시 히트율
hybrid_tts_cache_hit_rate

# 초당 요청 수
rate(hybrid_tts_synthesis_requests_total[5m])

# 평균 응답 시간
rate(hybrid_tts_synthesis_latency_seconds_sum[5m]) /
rate(hybrid_tts_synthesis_latency_seconds_count[5m])

# 메소드별 요청 분포
sum by (method) (rate(hybrid_tts_synthesis_requests_total[5m]))
```

## 설정

### 환경 변수

`.env` 파일에서 다음 설정을 변경할 수 있습니다:

```bash
# 모니터링 활성화/비활성화
ENABLE_METRICS=true

# 메트릭 로그 파일 경로
METRICS_LOG_PATH=./hybrid-tts/logs/metrics.json

# 목표 메트릭
TARGET_CACHE_HIT_RATE=0.80  # 80%
TARGET_COST_REDUCTION=0.70  # 70%
```

### 메트릭 플러시 설정

메트릭은 다음 시점에 디스크에 기록됩니다:

1. **자동 플러시**: 100개의 이벤트가 누적되면 자동으로 플러시
2. **애플리케이션 종료 시**: 모든 메트릭이 자동으로 플러시
3. **수동 플러시**: `/api/v1/monitoring/flush` 엔드포인트 호출

## 사용 예시

### 1. 시스템 시작

```bash
cd hybrid-tts
uvicorn api.main:app --reload
```

### 2. 대시보드 확인

브라우저에서 다음 URL을 엽니다:
```
http://localhost:8000/api/v1/monitoring/dashboard
```

### 3. Prometheus 메트릭 확인

```bash
curl http://localhost:8000/api/v1/monitoring/metrics
```

### 4. 통계 조회

```bash
curl http://localhost:8000/api/v1/monitoring/stats | jq
```

### 5. 성능 보고서 생성

```bash
curl http://localhost:8000/api/v1/monitoring/report | jq
```

### 6. 시계열 데이터 조회

```bash
# 최근 24시간
curl "http://localhost:8000/api/v1/monitoring/timeseries?hours=24" | jq

# 특정 시간대
curl "http://localhost:8000/api/v1/monitoring/timeseries?start_time=2025-11-13T00:00:00&end_time=2025-11-13T12:00:00" | jq
```

## 로깅

모든 메트릭은 다음 위치에 JSON 형식으로 저장됩니다:

```
hybrid-tts/logs/metrics.json
```

각 라인은 개별 메트릭 이벤트입니다:

```json
{"timestamp": "2025-11-13T12:00:00.000000", "event_type": "synthesis", "latency_ms": 45.2, "method": "exact", "text_length": 50, "audio_size": 12345, "confidence_score": 1.0, "metadata": {}}
```

## 성능 고려사항

1. **메모리 사용량**: 메트릭은 100개씩 배치로 플러시되어 메모리 사용량을 최소화합니다.
2. **디스크 I/O**: 로그 파일은 append 모드로 작성되어 효율적입니다.
3. **응답 시간**: 메트릭 수집은 비동기적으로 처리되어 응답 시간에 미치는 영향이 최소화됩니다.

## 문제 해결

### 메트릭이 표시되지 않는 경우

1. `ENABLE_METRICS=true`로 설정되어 있는지 확인
2. 로그 디렉토리에 쓰기 권한이 있는지 확인
3. 애플리케이션 로그에서 오류 메시지 확인

### 대시보드가 로드되지 않는 경우

1. 서버가 실행 중인지 확인: `http://localhost:8000/health`
2. 브라우저 콘솔에서 오류 확인
3. CORS 설정 확인

### Prometheus가 메트릭을 수집하지 못하는 경우

1. `/api/v1/monitoring/metrics` 엔드포인트가 응답하는지 확인
2. Prometheus 설정 파일의 `targets` 확인
3. 네트워크 연결 및 방화벽 설정 확인

## 향후 개선 사항

- [ ] Grafana 대시보드 템플릿 제공
- [ ] 알림 시스템 통합 (목표 미달성 시)
- [ ] 더 상세한 비용 분석
- [ ] 메트릭 집계 및 요약 기능
- [ ] 메트릭 retention 정책
- [ ] 분산 추적 (distributed tracing) 지원

## 요약

✅ **완료된 작업**:

1. ✅ monitoring.py를 API에 통합
2. ✅ Prometheus 메트릭 자동 수집
3. ✅ 실시간 대시보드 구현 (`/api/v1/monitoring/dashboard`)
4. ✅ 모든 synthesis 요청에 메트릭 수집 통합
5. ✅ HTTP 요청 추적 미들웨어 구현
6. ✅ 자동 메트릭 플러시 (100개 이벤트마다, 종료 시)
7. ✅ 시계열 데이터 조회 API
8. ✅ 성능 보고서 생성 API

모니터링 시스템이 완전히 통합되어 실시간으로 시스템 성능을 추적하고 비용 절감 효과를 측정할 수 있습니다.
