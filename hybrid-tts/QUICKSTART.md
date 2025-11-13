# 빠른 시작 가이드

Hybrid TTS Cost Optimizer를 5분 안에 실행해보세요!

## 단계 1: 사전 준비

### 필수 항목
- Python 3.10 이상
- Docker (선택 사항, Redis용)

### API 키 준비
다음 중 하나의 TTS 제공자 계정이 필요합니다:

**Option A: Google Cloud TTS** (권장)
1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
2. Text-to-Speech API 활성화
3. 서비스 계정 키(JSON) 다운로드

**Option B: Amazon Polly**
1. AWS 계정 생성
2. IAM에서 Polly 권한이 있는 액세스 키 생성

## 단계 2: Docker로 빠르게 시작 (권장)

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 API 키 입력

# 2. Docker Compose로 실행
docker-compose up -d

# 3. 로그 확인
docker-compose logs -f api
```

서버가 http://localhost:8000 에서 실행됩니다!

## 단계 3: 로컬에서 실행

```bash
# 1. Redis 실행 (별도 터미널)
docker run -d -p 6379:6379 redis:latest

# 2. Python 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp .env.example .env
# .env 파일 편집

# 5. 서버 실행
cd hybrid-tts
python -m api.main
```

## 단계 4: 첫 번째 음성 합성

### 웹 브라우저에서
http://localhost:8000/docs 에 접속하여 Swagger UI에서 직접 테스트

### Python으로

```python
import httpx

# 기본 합성
response = httpx.post(
    "http://localhost:8000/api/v1/synthesize",
    json={"text": "안녕하세요, 하이브리드 TTS 시스템입니다"}
)

with open("output.opus", "wb") as f:
    f.write(response.content)

print(f"캐시 상태: {response.headers.get('X-Cache-Status')}")
print(f"매칭 방법: {response.headers.get('X-Method')}")
print(f"응답 시간: {response.headers.get('X-Latency-Ms')}ms")
```

### cURL로

```bash
curl -X POST "http://localhost:8000/api/v1/synthesize" \
  -H "Content-Type: application/json" \
  -d '{"text": "안녕하세요"}' \
  --output output.opus
```

## 단계 5: POC 시나리오 실행

은행 잔액 조회 시나리오로 시스템 성능을 확인하세요:

```bash
python examples/banking_poc.py
```

출력 예시:
```
================================================================================
Banking Balance Inquiry POC - Hybrid TTS System
================================================================================

Simulating 100 balance inquiries...
Common query ratio: 80.0%

Progress: 10/100 requests completed
Progress: 20/100 requests completed
...
Progress: 100/100 requests completed

================================================================================
POC RESULTS
================================================================================

Total Requests: 100
Cache Hits: 85
Cache Misses: 15
Cache Hit Rate: 85.00%

Latency Statistics:
  Average: 42.35 ms
  Min: 12.50 ms
  Max: 385.20 ms

Method Distribution:
  exact: 60 (60.0%)
  fuzzy: 20 (20.0%)
  semantic: 5 (5.0%)
  tts_synthesis: 15 (15.0%)

Cost Analysis:
  Cost without cache: $0.0800
  Actual cost with cache: $0.0129
  Cost savings: $0.0671
  Cost reduction rate: 83.88%

Target Achievement:
  Cache Hit Rate Target (80%): ✓ ACHIEVED (85.0%)
  Cost Reduction Target (70%): ✓ ACHIEVED (83.9%)

🎉 POC SUCCESS! Both targets achieved!
================================================================================
```

## 단계 6: 시스템 통계 확인

```bash
# 전체 시스템 통계
curl http://localhost:8000/api/v1/stats | jq

# 캐시 통계만
curl http://localhost:8000/api/v1/stats | jq '.cache'

# 템플릿 목록
curl http://localhost:8000/api/v1/templates | jq
```

## 다음 단계

### 커스터마이징
1. `templates/data/templates.yaml` - 도메인별 템플릿 추가
2. `config.py` - 임계값 및 타임아웃 조정
3. `examples/` - 자신만의 POC 시나리오 작성

### 프로덕션 배포
1. `.env`에서 `DEBUG=False` 설정
2. 적절한 `REDIS_PASSWORD` 설정
3. CORS 설정 조정 (`api/main.py`)
4. 모니터링 대시보드 구축

### 성능 최적화
1. 고빈도 문구 사전 녹음 및 캐시 워밍업
2. 퍼지/시맨틱 매칭 임계값 조정
3. Redis 메모리 제한 및 LRU 정책 튜닝

## 문제 해결

### Redis 연결 오류
```bash
# Redis가 실행 중인지 확인
redis-cli ping
# 응답: PONG
```

### TTS API 오류
- `.env` 파일의 API 키 확인
- Google Cloud: 서비스 계정 키 경로 확인
- AWS: 리전 설정 확인 (`AWS_REGION`)

### 모듈 import 오류
```bash
# PYTHONPATH 설정
export PYTHONPATH=/path/to/HybridTTSSystems:$PYTHONPATH

# 또는 hybrid-tts 디렉토리에서 실행
cd hybrid-tts
python -m api.main
```

## 유용한 명령어

```bash
# 캐시 초기화
curl -X POST http://localhost:8000/api/v1/cache/clear

# 헬스 체크
curl http://localhost:8000/health

# 특정 템플릿으로 합성
curl -X POST "http://localhost:8000/api/v1/synthesize/template?template_id=greeting_morning" \
  -H "Content-Type: application/json" \
  -d '{}'

# 테스트 실행
pytest tests/

# 빠른 테스트만 (시맨틱 매칭 제외)
pytest -m "not slow"
```

## 학습 자료

- 📖 [README.md](README.md) - 전체 문서
- 📊 [banking_poc.py](examples/banking_poc.py) - POC 소스 코드
- 🧪 [tests/](tests/) - 테스트 예제
- 🌐 http://localhost:8000/docs - API 문서 (서버 실행 후)

## 지원

문제가 발생하면:
1. 로그 확인: `docker-compose logs api` 또는 콘솔 출력
2. 헬스 체크: `curl http://localhost:8000/health`
3. Redis 상태: `redis-cli ping`

즐거운 개발 되세요! 🚀
