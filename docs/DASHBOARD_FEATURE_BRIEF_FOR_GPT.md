# AI 커머스 운영 대시보드 기능 브리프

이 문서는 GPT에게 첨부해 현재 대시보드의 기능, 데이터 구조, LLM 활용 방식, 개선 제약을 학습시키기 위한 요약 자료입니다. 목적은 최신 LLM 기반 커머스 대시보드 기능을 리서치한 뒤, 현재 MVP에 적용할 수 있는 핵심 기능을 선정하는 것입니다.

## 1. 제품 목적

AI 커머스 운영 대시보드는 커머스 운영자가 매출, 상품, 마케팅, 고객 CS, 재고, 추천 데이터를 한 화면에서 이해하고, 탐지된 운영 이슈를 액션과 보고서로 연결하도록 돕는 Streamlit MVP입니다.

사용자는 사이드바에서 분석 기간, 역할, 상관분석 방식을 선택하고, 본문 대시보드와 우측 AI 채팅 패널을 함께 사용합니다. 사용자-facing 문구는 한국어입니다.

## 2. 현재 기술 구조

- 프레임워크: Streamlit
- 주요 언어: Python
- 데이터 처리: pandas
- 시각화: Plotly
- LLM 연동: OpenAI Responses API
- 기본 모델: `gpt-5.4-mini`, `.env`의 `OPENAI_MODEL`로 변경 가능
- API 키 저장: `.env`에만 저장하며 코드나 로그에 출력하지 않음
- 대체 답변: OpenAI 연결 실패 또는 API 키 미설정 시 규칙 기반 fallback 답변 사용

주요 파일:

- `main.py`: Streamlit 진입점
- `dashboard.py`: UI, 필터, 차트, 리포트, 채팅 패널
- `src/agents.py`: 8개 분석 에이전트와 KPI 계산
- `src/openai_service.py`: OpenAI Responses API 연동 및 대시보드 컨텍스트 직렬화
- `src/chat.py`: 규칙 기반 fallback 답변
- `src/role_agents.py`: 직무 답변 에이전트 메타데이터와 deterministic routing
- `agent/`: 직무 답변 에이전트별 Markdown 지침
- `src/workflow_patterns.py`: 질문별 LLM workflow pattern 분류
- `db/`: 7개 CSV fixture 데이터

## 3. 사용 데이터

현재 대시보드는 7개 CSV를 사용합니다.

| 도메인 | 파일 | 주요 컬럼 |
| --- | --- | --- |
| 매출·상품 | `sales_data.csv` | `date`, `product_id`, `product_name`, `category`, `quantity_sold`, `revenue`, `orders` |
| 매출·상품 | `product_data.csv` | `product_id`, `product_name`, `category`, `cost`, `price`, `safe_stock` |
| 마케팅 | `marketing_data.csv` | `date`, `channel`, `campaign`, `ad_spend`, `clicks`, `conversions`, `ROAS` |
| 고객·CS | `customer_data.csv` | `date`, `new_customers`, `returning_customers`, `signups`, `cart_abandon_rate` |
| 고객·CS | `review_cs_data.csv` | `date`, `product_id`, `product_name`, `rating`, `review_count`, `inquiry_count`, `refund_count` |
| 재고·추천 | `inventory_data.csv` | `date`, `product_id`, `current_stock`, `safe_stock` |
| 재고·추천 | `recommendation_log.csv` | `date`, `product_id`, `product_name`, `recommended_count`, `click_count`, `conversion_count` |

분석 기간은 데이터의 `date` 기준으로 필터링됩니다. 상품 조인은 `product_id`를 기준으로 합니다.

## 4. 현재 화면 구성

사이드바에는 6개 페이지가 있습니다.

1. Home
   - 전체 KPI 카드
   - 매출·상품, 마케팅, 고객·CS, 재고·추천 탭
   - 핵심 인사이트
   - 강한 상관관계 Top 5

2. Events
   - 탐지된 운영 이벤트 테이블
   - 도메인 필터
   - 심각도 필터
   - High, Medium, Low 이벤트 카운트

3. Analytics
   - Pearson 또는 Spearman 상관관계 히트맵
   - 상관관계 Top 12
   - 두 지표 선택 후 산점도 확인
   - 상관관계는 인과관계가 아님을 명시

4. Tasks
   - 이벤트 기반 액션 보드
   - 역할별 필터링
   - 우선순위, 담당팀, 마감일, 세부 지침
   - 상태값: `대기`, `진행중`, `완료`

5. Agents
   - 8개 분석 에이전트 실행 상태
   - 데이터 품질 테이블

6. Reports
   - 주간 리포트 Markdown 생성 및 다운로드
   - 대표 보고서 Markdown 생성 및 다운로드

## 5. 현재 분석 파이프라인

현재 8개 분석 에이전트는 별도 서비스가 아니라 Python 모듈로 구현되어 있습니다.

1. Data Loader Agent
   - 7개 CSV 로딩
   - `date` 컬럼 날짜형 변환
   - 행 수, 컬럼 수, 결측치, 중복 여부 등 데이터 품질 확인

2. Event Detector Agent
   - 판매 급상승: 상품별 3일 기준 판매량 대비 50% 이상 증가
   - 판매 급감: 상품별 3일 기준 판매량 대비 30% 이상 감소
   - 품절 위험: 현재 재고가 안전재고 이하
   - 품절: 현재 재고 0
   - 광고 효율 저하: 최근 7일 ROAS가 이전 7일 대비 20% 이상 감소
   - 인기상품 진입: 기간 내 카테고리별 판매량 Top 3
   - 추천상품 성과 우수: 추천 CTR 또는 CVR이 평균 대비 30% 이상 높음

3. Correlation Analyzer Agent
   - 선택 기간 기준 일자별 지표 테이블 생성
   - 대상 지표: `quantity_sold`, `revenue`, `current_stock`, `ad_spend`, `clicks`, `conversions`, `rating`, `recommended_count`, `click_count`, `conversion_count`
   - Pearson 또는 Spearman 상관계수 계산
   - 절대값 기준 상위 상관쌍 추출

4. Insight Generator Agent
   - High 이벤트, 재고 이벤트, 마케팅 이벤트, 상관관계 Top pair를 바탕으로 핵심 인사이트 생성
   - 사용자가 선택한 역할 관점을 반영
   - 상관관계는 인과관계가 아님을 안내

5. Weekly Report Agent
   - KPI, 핵심 인사이트, 주요 이벤트, 상관관계 Top 3를 Markdown 리포트로 생성

6. Action Planner Agent
   - 이벤트를 실행 가능한 액션으로 변환
   - 담당팀, 우선순위, 마감일, 세부 지침, 상태를 생성

7. Task Assignment Agent
   - 선택 담당에 맞는 액션 권고 우선순위화
   - 마감 초과 여부 계산

8. Executive Report Agent
   - 대표가 볼 수 있는 요약 보고서 생성
   - High 우선순위 액션 중 승인·결정이 필요한 항목 강조

## 6. 현재 KPI와 시각화

주요 KPI:

- 매출
- 주문 수
- 평균 ROAS
- 품절 위험 건수
- 신규 고객
- 재구매 고객
- 평균 평점
- 환불 건수
- 광고비
- 광고 클릭
- 광고 전환
- 전체 재고
- 추천 CTR
- 추천 CVR

주요 차트:

- 매출 추이 라인 차트
- 상품별 성과 테이블
- 채널별 ROAS 라인 차트
- 채널별 광고비 막대 차트
- 고객 구성 area chart
- 상품별 CS 신호 scatter chart
- 안전재고 대비 현재 재고 bar chart
- AI 추천 성과 scatter chart
- 상관관계 히트맵
- 선택 지표 간 상세 산점도

## 7. 현재 LLM 채팅 기능

우측에는 고정형 AI 채팅 패널이 있습니다. 데스크톱에서는 브라우저 viewport 우측에 고정되고, 메시지 히스토리만 스크롤됩니다. 모바일 또는 좁은 화면에서는 일반 문서 흐름으로 돌아갑니다.

채팅은 현재 선택된 분석 기간, KPI, 이벤트, 상관관계, 액션 데이터를 바탕으로 답변합니다. 전체 CSV 원본을 LLM에 보내지 않고, `build_dashboard_context`가 만든 집계 컨텍스트만 전달합니다.

채팅 기능:

- 빠른 질문 버튼
- 사용자의 자유 질문 입력
- 질문 입력 후 사용자 메시지를 먼저 표시하고 assistant 답변 스트리밍
- OpenAI 사용 가능 시 Responses API로 답변 생성
- OpenAI 실패 시 규칙 기반 fallback 답변
- 답변별 출처 표시: OpenAI 또는 규칙 기반 fallback
- OpenAI 연결 오류는 별도 expander에서 확인
- 질문과 답변은 `chat.txt`에 append 저장

## 8. 직무 답변 에이전트

분석 파이프라인과 별도로, 채팅 답변은 6개 답변 담당 에이전트 중 하나 또는 여러 개가 담당합니다.

1. 마케팅 담당
   - 광고비, 채널, 캠페인, ROAS, 클릭, 전환 중심
   - 마케팅 이벤트와 예산 우선순위를 설명

2. 고객 CS 담당
   - 신규·재구매 고객, 리뷰, 평점, 문의, 환불 중심
   - 고객 영향과 CS 대응을 설명

3. 재고관리 담당
   - 현재 재고, 안전재고, 품절 위험, 발주 우선순위 중심
   - 긴급도와 발주 또는 대체 상품 대응을 제시

4. 매출 상품 담당
   - 매출, 주문, 판매량, 상품별 판매 성과 중심
   - 전체 실적과 상품별 기여를 구분

5. 제품 기획 담당
   - 상품 구성, 인기상품, 추천 성과, 가격·프로모션·신상품 기회 중심
   - 단기 운영 조치와 제품 가설을 구분

6. 제품총괄
   - 다른 담당 답변을 종합·평가
   - 최종 의사결정 관점의 권고와 다음 액션을 정리

답변 담당 배정 방식:

- 자동 배정: 질문 키워드 기반 deterministic routing
- 직접 지정: 사용자가 하나 이상의 담당을 선택
- 복수 지정: 여러 담당의 답변을 각각 생성
- 답변에는 담당 에이전트명, 배정 방식, 배정 근거가 표시됨

## 9. LLM Workflow Pattern 표시

각 채팅 답변 아래에는 선택된 LLM workflow pattern이 표시됩니다.

현재 분류되는 패턴:

- Augmented LLM
- Routing
- Parallelization
- 별도 패턴: Workflow intent detected
- 별도 패턴: Orchestration intent detected
- 별도 패턴: Evaluator-optimizer

현재 구현은 실제 다중 agent orchestration이라기보다, 질문 의도와 담당 선택 방식에 따라 어떤 LLM workflow pattern에 가까운지 설명하는 방식입니다.

## 10. 현재 강점

- CSV 기반 MVP이지만 매출, 마케팅, 고객 CS, 재고, 추천 데이터를 한 흐름에서 연결함
- 이벤트 탐지 → 상관 분석 → 인사이트 → 액션 → 보고서로 이어지는 운영형 워크플로우가 있음
- LLM 답변이 현재 선택된 기간과 분석 결과에 grounding됨
- OpenAI 실패 시 fallback이 있어 데모 안정성이 높음
- 직무별 답변 에이전트가 있어 CEO/운영자/마케팅/CS/MD 관점 질의에 대응 가능
- 상관관계를 인과관계로 단정하지 않는 안전장치가 있음
- 보고서와 액션 보드까지 연결되어 단순 분석 화면보다 실행 지향적임

## 11. 현재 한계

- 실시간 데이터 연동이 아니라 CSV fixture 기반
- 사용자의 액션 상태 변경은 현재 세션 중심이며 영속 DB가 없음
- LLM이 차트 특정 영역이나 테이블 행을 자동 하이라이트하지는 않음
- 답변에서 언급한 근거와 대시보드 컴포넌트 간 클릭 가능한 evidence link가 없음
- 이상 탐지와 예측은 단순 규칙과 상관계수 중심
- “왜 이런 일이 발생했는가”에 대한 인과 추론, 시나리오 분석, 실험 설계 기능은 없음
- 개인화된 사용자 권한, 팀별 알림, Slack/Email 발송은 없음
- 상품 상세 drill-down 페이지가 없음
- 외부 시장/경쟁사/트렌드 데이터를 반영하지 않음
- 추천 로그를 분석하지만 추천 알고리즘 자체를 개선하거나 재랭킹하지는 않음

## 12. 적용 후보 기능을 선정할 때의 기준

최신 LLM 커머스 대시보드 기능을 조사한 뒤, 아래 기준으로 현재 MVP에 적용할 핵심 기능을 골라야 합니다.

우선순위가 높은 기능:

- 현재 7개 CSV와 기존 분석 결과만으로도 구현 가능한 기능
- Streamlit/Python 구조 안에서 빠르게 추가 가능한 기능
- 평가자에게 “LLM을 실질적으로 활용했다”는 인상을 줄 수 있는 기능
- 한국어 운영자에게 바로 가치가 보이는 기능
- 기존 채팅 패널, 이벤트, 액션, 보고서 구조와 자연스럽게 연결되는 기능
- OpenAI 실패 시 fallback 또는 graceful degradation이 가능한 기능

우선순위가 낮은 기능:

- 실시간 커넥터, 대규모 데이터 웨어하우스, 권한 관리가 필수인 기능
- 별도 프론트엔드 런타임이나 복잡한 백엔드 인프라가 필요한 기능
- 현 데이터에 없는 개인 식별 정보나 주문 상세 로그가 필요한 기능
- 정확한 수요 예측을 위해 장기간 데이터와 모델 검증이 필요한 기능
- 상관관계를 인과관계처럼 표현할 위험이 큰 기능

## 13. 현재 구조에 특히 잘 맞는 개선 후보

아래 후보들은 현재 대시보드 구조와 궁합이 좋은 방향입니다. 최신 기능 리서치 후 이 목록을 확장하거나 우선순위를 조정할 수 있습니다.

1. 답변 기반 대시보드 내비게이션
   - AI 답변 후 관련 페이지로 이동
   - 관련 이벤트, 지표, 액션을 하이라이트
   - 현재 `page_hint`가 저장되어 있어 확장하기 쉬움

2. Evidence-linked Answer
   - 답변 문장마다 근거 KPI, 이벤트 ID, 액션 ID, 상관쌍을 연결
   - 사용자가 “왜 이렇게 답했는지” 즉시 검증 가능

3. What-if 시나리오
   - 광고비, 재고 보충, 추천 노출 증가 등 가정 입력
   - 현재 KPI와 상관관계 기반으로 예상 영향 범위를 설명
   - 단, 인과가 아니라 “가정 기반 추정”으로 표시 필요

4. 액션 자동 우선순위 재정렬
   - 심각도, 마감일, 매출 영향, 재고 위험, 담당팀 기준으로 액션을 재정렬
   - LLM은 우선순위 변경 사유를 한국어로 설명

5. 원인 후보 분석
   - 판매 급상승/급감 또는 ROAS 하락 이벤트에 대해 가능한 원인 후보를 구조화
   - 광고, 재고, 추천, 리뷰, 고객 지표를 함께 확인
   - “확인된 사실”과 “가설”을 분리

6. 보고서 개선
   - 주간 리포트를 역할별 섹션으로 더 풍부하게 생성
   - 대표용 1페이지 요약, 실무자용 액션 중심 보고서 분리

7. 대화 로그 기반 후속 질문
   - `chat.txt` 또는 세션 히스토리를 활용해 반복 질문, 미해결 액션, 자주 묻는 지표를 요약

8. 알림 문안 생성
   - 품절, 재입고, CS 대응, 마케팅 캠페인 조정에 필요한 한국어 메시지 초안 생성
   - 운영자가 복사해 Slack, Email, 고객 안내문에 활용 가능

## 14. GPT에게 요청할 리서치 질문 예시

아래 문장을 그대로 사용하거나 수정해서 GPT에게 최신 기능 리서치를 요청할 수 있습니다.

```text
첨부한 Markdown은 현재 우리가 만든 AI 커머스 운영 대시보드의 기능 브리프입니다.

너는 LLM 기반 커머스 분석 SaaS와 운영 대시보드 전문가입니다.
2025~2026년 기준으로 LLM을 활용한 최신 커머스 대시보드 기능 트렌드를 조사하고,
첨부 문서의 현재 기능과 비교해 우리 MVP에 적용할 핵심 기능을 선정해주세요.

요구사항:
1. 최신 LLM 커머스 대시보드 기능을 10개 이상 정리해주세요.
2. 각 기능이 어떤 사용자 문제를 해결하는지 설명해주세요.
3. 우리 현재 대시보드에 적용 가능성을 High/Medium/Low로 평가해주세요.
4. CSV 기반 Streamlit MVP에서 빠르게 구현 가능한 기능을 우선 추천해주세요.
5. 최종적으로 다음 개발 스프린트에서 구현할 Top 5 기능을 선정해주세요.
6. 각 Top 5 기능에 대해 예상 구현 범위, 필요한 데이터, UI 변경점, LLM 프롬프트/컨텍스트 변경점, fallback 전략을 제안해주세요.
7. 상관관계를 인과관계로 단정하지 않도록 UX/문구 안전장치도 함께 제안해주세요.

답변은 한국어로 작성해주세요.
```

## 15. GPT가 기능을 추천할 때 반드시 고려할 제약

- 전체 CSV 원본을 LLM에 보내지 않고 집계 컨텍스트만 전달해야 함
- 답변은 현재 선택된 기간, KPI, 이벤트, 상관관계, 액션에 grounded되어야 함
- OpenAI 연결이 실패해도 핵심 사용 흐름은 fallback으로 유지되어야 함
- 사용자-facing 문구는 한국어여야 함
- Streamlit 컴포넌트를 기본 구현 표면으로 유지해야 함
- 기존 8개 분석 에이전트와 6개 답변 담당 에이전트 구조를 최대한 유지해야 함
- 상관관계를 인과관계로 표현하면 안 됨
- 7개 CSV fixture는 데이터 구조를 바꾸지 않는 것이 좋음
- 평가자가 짧은 시간 안에 기능 가치를 확인할 수 있어야 함
