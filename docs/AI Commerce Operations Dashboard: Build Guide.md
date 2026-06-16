# AI Commerce Operations Dashboard: Build Guide

이 문서는 제공된 CSV 데이터를 이용하여 **AI 커머스 운영 대시보드**와 **리포트 자동화 시스템**을 구축하는 데 필요한 지침을 제공합니다. 전체 워크플로우는 데이터를 로드하고, 이벤트를 탐지하며, 상관관계를 분석하고, 주간 리포트와 액션플랜을 자동 생성하는 것을 목표로 합니다.

## 1. 데이터셋 개요

폴더에는 7개의 CSV 파일이 포함되어 있습니다. 각 파일은 2026년 3월 중순부터 2026년 6월 14일까지 90일간의 데이터를 저장합니다.

| 파일명 | 설명 |
| --- | --- |
| **sales_data.csv** | 일자별로 상품 판매 실적을 기록합니다. 컬럼: `date`, `product_id`, `product_name`, `category`, `quantity_sold`, `revenue`, `orders`. |
| **product_data.csv** | 상품 기본 정보입니다. 컬럼: `product_id`, `product_name`, `category`, `cost`, `price`, `safe_stock`. |
| **marketing_data.csv** | 채널별 광고 지출 및 성과입니다. 컬럼: `date`, `channel`, `campaign`, `ad_spend`, `clicks`, `conversions`, `ROAS`. |
| **customer_data.csv** | 일자별 고객 관련 지표입니다. 컬럼: `date`, `new_customers`, `returning_customers`, `signups`, `cart_abandon_rate`. |
| **inventory_data.csv** | 일자별 재고 수준을 나타냅니다. 컬럼: `date`, `product_id`, `current_stock`, `safe_stock`. |
| **review_cs_data.csv** | 주차별 리뷰 및 CS 지표입니다. 컬럼: `date`, `product_id`, `product_name`, `rating`, `review_count`, `inquiry_count`, `refund_count`. |
| **recommendation_log.csv** | AI 추천 노출 및 성과 기록입니다. 컬럼: `date`, `product_id`, `product_name`, `recommended_count`, `click_count`, `conversion_count`. |

## 2. 대시보드 구축 흐름

1. **데이터 로딩**  
   각 CSV 파일을 pandas 등의 라이브러리로 불러오고 `date` 컬럼을 날짜형으로 변환합니다. 상품 ID를 기준으로 다른 데이터와 조인할 수 있도록 `product_id` 컬럼을 유지합니다.

2. **이벤트 탐지**  
   판매 급상승, 판매 급감, 품절 위험, 인기상품 진입, 광고 효율 저하 등 이벤트를 계산합니다. 예를 들어 3일 이동 평균 대비 판매량이 50% 이상 증가하면 `판매 급상승` 이벤트로 플래그를 설정할 수 있습니다. 이벤트 정보는 별도의 DataFrame으로 저장합니다.

3. **상관관계 분석**  
   수집된 지표와 이벤트 간의 관계를 파악하기 위해 상관관계 행렬을 계산합니다. `quantity_sold`, `ad_spend`, `clicks`, `conversions`, `revenue`, `current_stock`, `rating`, `recommended_count`, `click_count`, `conversion_count` 등 여러 변수들의 피어슨 혹은 스피어만 상관계수를 구하고, 상위·하위 상관쌍을 추려냅니다. 상관관계는 반드시 분석 기간(예: 최근 1주, 2주)을 지정하여 계산합니다.

4. **시각화**  
   * **Executive Summary**: 전체 KPI 요약과 상관관계 TOP 3를 표시합니다.  
   * **Event Correlation Network**: 이벤트를 노드로 하여 상관관계를 엣지로 표현합니다. 엣지 가중치는 상관계수이며, 양수와 음수를 색상으로 구분합니다.  
   * **Correlation Heatmap**: 모든 주요 지표의 상관관계 행렬을 열 지도 형태로 표시합니다.  
   * **Detailed Charts**: 상관관계를 확인하고 싶은 두 지표를 선택하면 트렌드 그래프 또는 산점도를 보여줍니다.  
   * **Role-Specific Action Board**: 다음 섹션의 액션플랜을 반영한 업무 보드를 표시합니다.

5. **주간 리포트 생성**  
   매주 월요일에 최근 한 주간의 데이터를 요약하여 Markdown 또는 PDF 형태로 리포트를 작성합니다. 리포트에는 주요 KPI 변화, 탐지된 이벤트 목록, 상관관계 분석 결과, 추천 액션 등이 포함되어야 합니다.

6. **액션플랜 및 역할 배정**  
   이벤트와 상관분석 결과를 기반으로 마케팅팀, MD팀, CRM/CS팀, 대표 등 역할별 실행 과제를 추출합니다. 예를 들어 `판매 급상승`과 `재고 부족`이 상관될 경우 MD팀에 발주를 요청하고, `광고 효율 저하`가 나타나면 마케팅팀에 소재 교체를 지시합니다. 각 액션에는 우선순위, 담당자, 마감일을 설정합니다.

7. **리포트 및 대시보드 자동화**  
   Python 스크립트나 LangChain을 이용해 위의 데이터 처리, 분석, 리포트 생성 과정을 자동화하고, Streamlit 등으로 대시보드를 구현합니다. 필요하다면 스케줄러(cron)나 워크플로우 툴(n8n 등)을 통해 주간 보고서 발행을 자동화합니다.

## 3. 개발 팁

* **시간 필터**: 대시보드에서 사용자가 기간을 선택할 수 있게 해 상관관계 및 트렌드 분석을 특정 기간에 한정할 수 있게 합니다.
* **상관관계 해석 주의**: 높은 상관이 반드시 인과관계를 의미하지 않음을 리포트에 명시하세요. 분석 결과를 설명할 때는 외부 요인(예: 프로모션, 계절성)도 함께 고려합니다.
* **시각적 강조**: 상관관계 네트워크에서는 중요한 노드(이벤트)를 색상이나 크기로 강조하여, 사용자에게 우선적으로 주목해야 할 이벤트를 명확히 전달합니다.
* **반복 가능성**: CSV 파일은 임의로 생성된 샘플이므로 실제 데이터를 대체할 수 있습니다. 구조를 그대로 유지하면 실데이터로 쉽게 교체할 수 있습니다.

이 지침에 따라 데이터를 로드하고, 이벤트를 탐지하며, 상관분석과 시각화를 수행하면 풍부한 인사이트와 실행 가능한 액션플랜을 포함한 AI 기반 운영 대시보드와 리포트 시스템을 구축할 수 있습니다.
