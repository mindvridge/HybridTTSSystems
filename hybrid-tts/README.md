# Hybrid TTS Cost Optimizer

실시간 TTS API 비용을 70-90% 절감하는 하이브리드 음성 합성 시스템

## 개요

이 프로젝트는 사전 녹음된 오디오 캐싱과 지능형 텍스트 매칭을 통해 TTS API 비용을 대폭 절감하는 하이브리드 시스템입니다. 특히 도메인이 좁고 반복적인 대화 패턴이 있는 경우 (은행, 고객 서비스, IVR 등)에 최적화되어 있습니다.

### 주요 특징

- **70-90% 비용 절감**: 파레토 원리를 활용한 지능형 캐싱
- **다단계 매칭 파이프라인**: 정확 → 퍼지 → 시맨틱 → TTS 폴백
- **템플릿 기반 응답**: 파라메트릭 템플릿으로 유연성과 캐시 효율성 양립
- **저지연 응답**: 캐시 히트 시 10-50ms, TTS 폴백 시 200-500ms
- **확장 가능한 아키텍처**: FastAPI + Redis + 모듈형 설계
- **자동 재시도 로직**: Exponential backoff를 통한 일시적 오류 자동 복구

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Server                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐  │
│  │   Template   │   │   Matching   │   │   Cache    │  │
│  │   Manager    │──▶│   Pipeline   │──▶│  Manager   │  │
│  └──────────────┘   └──────────────┘   └────────────┘  │
│         │                   │                   │        │
│         │                   │                   ▼        │
│         │                   │            ┌────────────┐  │
│         │                   │            │   Redis    │  │
│         │                   │            └────────────┘  │
│         │                   │                            │
│         │                   ▼                            │
│         │            ┌────────────┐                      │
│         │            │  Exact     │                      │
│         │            │  Fuzzy     │                      │
│         │            │  Semantic  │                      │
│         │            └────────────┘                      │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐                                        │
│  │ TTS Provider │  (Google Cloud TTS / Amazon Polly)    │
│  └──────────────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐                                        │
│  │    Audio     │                                        │
│  │  Processor   │                                        │
│  └──────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

## 시작하기

### 필수 요구사항

- Python 3.10+
- Redis 6.0+
- Google Cloud TTS 또는 Amazon Polly 계정

### 설치

1. **저장소 클론 및 디렉토리 이동**

```bash
cd hybrid-tts
```

2. **가상 환경 생성 및 활성화**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows
```

3. **의존성 설치**

```bash
pip install -r requirements.txt
```

4. **환경 변수 설정**

```bash
cp .env.example .env
# .env 파일을 편집하여 API 키와 설정을 입력
```

필수 환경 변수:
```env
OPENAI_API_KEY=your-openai-api-key
TTS_PROVIDER=google  # 또는 polly

# TTS API 재시도 설정 (선택사항)
TTS_MAX_RETRY_ATTEMPTS=3           # 최대 재시도 횟수
TTS_RETRY_INITIAL_WAIT_MS=1000     # 초기 대기 시간 (밀리초)
TTS_RETRY_MAX_WAIT_MS=10000        # 최대 대기 시간 (밀리초)
TTS_RETRY_MULTIPLIER=2.0           # Exponential backoff 배수
TTS_REQUEST_TIMEOUT_SEC=30         # 요청 타임아웃 (초)

# Google Cloud TTS 사용 시
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Amazon Polly 사용 시
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

5. **Redis 실행**

Docker를 사용하는 경우:
```bash
docker run -d -p 6379:6379 redis:latest
```

또는 로컬 Redis:
```bash
redis-server
```

### 서버 실행

```bash
cd hybrid-tts
python -m api.main
```

서버가 http://localhost:8000 에서 실행됩니다.

API 문서: http://localhost:8000/docs

## 사용 예제

### 1. 기본 음성 합성

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/synthesize",
    json={"text": "안녕하세요"}
)

with open("output.opus", "wb") as f:
    f.write(response.content)
```

### 2. 템플릿 기반 합성 (권장)

```python
response = httpx.post(
    "http://localhost:8000/api/v1/synthesize/template",
    params={
        "template_id": "balance_inquiry_result",
    },
    json={
        "customer_name": "김철수",
        "balance": "1,250,000"
    }
)
```

### 3. POC 시나리오 실행

```bash
cd hybrid-tts
python examples/banking_poc.py
```

이 POC는 은행 잔액 조회 시나리오로 100개의 요청을 시뮬레이션하여:
- 캐시 히트율 측정
- 비용 절감율 계산
- 지연시간 분석
- 목표 달성 여부 확인

## API 엔드포인트

### 음성 합성

- `POST /api/v1/synthesize` - 기본 음성 합성
- `POST /api/v1/synthesize/template` - 템플릿 기반 합성 (권장)
- `POST /api/v1/synthesize/batch` - 배치 합성

### 템플릿 관리

- `GET /api/v1/templates` - 템플릿 목록 조회
- `GET /api/v1/templates/{template_id}` - 특정 템플릿 조회
- `POST /api/v1/templates/render` - 템플릿 렌더링 (합성 없이)

### 시스템 모니터링

- `GET /health` - 헬스 체크
- `GET /api/v1/stats` - 시스템 통계
- `GET /api/v1/synthesis/stats` - 합성 통계

## 핵심 개념

### 1. 매칭 파이프라인

4단계 폭포수 방식으로 최적의 매칭을 찾습니다:

1. **정확 매칭** (1-5ms): 해시 기반 O(1) 조회
2. **퍼지 매칭** (10-50ms): Token Sort Ratio로 단어 순서 변형 처리
3. **시맨틱 매칭** (50-100ms): Sentence-BERT로 의미 유사도 판단
4. **TTS 폴백** (200-500ms): 모든 매칭 실패 시 새 음성 생성 및 캐싱

### 2. 템플릿 시스템

파라메트릭 템플릿으로 유연성과 캐시 효율성을 동시에 달성:

```yaml
- id: balance_inquiry_result
  pattern: "{customer_name}님의 계좌 잔액은 {balance}원입니다"
  slots:
    - customer_name
    - balance
  category: banking
```

### 3. 캐싱 전략

파레토 원리 적용:
- 상위 20% 문구가 80% 사용량 차지
- LRU 제거 정책
- TTL 기반 만료 (기본 365일)
- Redis 메타데이터 + 로컬 파일시스템 오디오

### 4. TTS API 자동 재시도 로직

네트워크 오류나 일시적인 API 장애에 대응하는 지능형 재시도 메커니즘:

**재시도 대상 오류:**
- Google Cloud TTS: `ServiceUnavailable`, `TooManyRequests`, `InternalServerError`, `DeadlineExceeded`
- Amazon Polly: `Throttling`, `ServiceUnavailable`, `InternalError`, `RequestTimeout`
- 네트워크 오류: `ConnectionError`, `TimeoutError`

**재시도 전략:**
- Exponential backoff: 1초 → 2초 → 4초 → ... (최대 10초)
- 기본 최대 3회 재시도
- 일시적 오류와 영구적 오류 자동 구분
- 재시도 성공/실패 Prometheus 메트릭 자동 수집

**메트릭:**
- `hybrid_tts_api_retry_total`: 재시도 시도 횟수
- `hybrid_tts_api_retry_success_total`: 재시도 후 성공 횟수
- `hybrid_tts_api_retry_exhausted_total`: 재시도 소진 후 실패 횟수

## 성능 목표

| 메트릭 | 목표 | 달성 방법 |
|--------|------|-----------|
| 캐시 히트율 | ≥ 80% | 파레토 원리, 템플릿 시스템 |
| 비용 절감률 | ≥ 70% | 지능형 캐싱 |
| 캐시 응답시간 | < 50ms | Redis + 로컬 스토리지 |
| TTS 응답시간 | 200-500ms | 비동기 처리 |

## 테스트

```bash
# 전체 테스트 실행
pytest

# 빠른 테스트만 (느린 시맨틱 테스트 제외)
pytest -m "not slow"

# 커버리지 포함
pytest --cov=. --cov-report=html
```

## 프로젝트 구조

```
hybrid-tts/
├── api/                    # FastAPI 애플리케이션
│   ├── main.py            # 메인 서버
│   └── routes/            # API 라우트
│       ├── synthesis.py   # 음성 합성 엔드포인트
│       └── templates.py   # 템플릿 관리
├── cache/                 # 캐시 관리
│   ├── manager.py         # Redis 캐시 매니저
│   └── storage/           # 오디오 파일 저장
├── matching/              # 매칭 엔진
│   ├── exact.py           # 정확 매칭
│   ├── fuzzy.py           # 퍼지 매칭
│   ├── semantic.py        # 시맨틱 매칭
│   └── pipeline.py        # 통합 파이프라인
├── templates/             # 템플릿 시스템
│   ├── loader.py          # 템플릿 로더
│   └── data/
│       └── templates.yaml # 템플릿 정의
├── tts/                   # TTS 제공자
│   ├── provider.py        # TTS API 추상화
│   └── audio_processor.py # 오디오 처리
├── examples/              # 예제 및 POC
│   └── banking_poc.py     # 은행 POC
├── tests/                 # 테스트
├── config.py              # 설정 관리
├── monitoring.py          # 모니터링
└── requirements.txt       # 의존성
```

## 도메인별 활용 사례

### 은행/금융 (현재 POC)
- 잔액 조회, 거래 내역, 계좌 정보
- 캐시 히트율: 85%+
- 비용 절감: 80%+

### 고객 서비스
- 표준 응답, 대기 메시지, FAQ
- 캐시 히트율: 80%+
- 비용 절감: 75%+

### IVR 시스템
- 메뉴 안내, 부서 연결, 운영 시간
- 캐시 히트율: 90%+
- 비용 절감: 85%+

## 확장 및 커스터마이징

### 새 도메인 추가

1. `templates/data/templates.yaml`에 도메인별 템플릿 추가
2. 고빈도 문구 식별 및 사전 녹음
3. POC 스크립트로 성능 검증

### TTS 제공자 추가

`tts/provider.py`에서 `TTSProvider` 추상 클래스 구현:

```python
class CustomTTSProvider(TTSProvider):
    async def synthesize(self, text: str, voice: str = None) -> bytes:
        # 구현
        pass
```

## 제한 사항

- 도메인이 넓고 예측 불가능한 대화에는 비효율적
- 초기 캐시 구축 시간 필요 (워밍업)
- 자연스러운 대화 흐름 vs 비용 절감 간 트레이드오프

## 라이선스

MIT License

## 기여

이슈 및 PR 환영합니다!

## 참고 문서

프로젝트는 다음 연구 및 실무 사례를 기반으로 합니다:
- Alibaba 챗봇: 연간 $150M 절감
- Vodafone TOBi: 채팅당 70% 비용 절감
- EazyPay QR Soundbox: 완전 오프라인 TTS 시스템
