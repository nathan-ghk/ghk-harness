from pydantic import BaseModel, Field
from typing import List, Optional

class InvestmentDetail(BaseModel):
    company_name: str = Field(..., description="분석 대상 기업의 명칭")
    sector: Optional[str] = Field(None, description="기업의 산업 분야")
    amount: float = Field(..., description="투자 금액 또는 지표 숫자")
    insight: str = Field(..., description="데이터 분석을 통한 비즈너리 관점의 전략적 해석")

class AgentResponse(BaseModel):
    sql_query: str = Field(..., description="데이터 추출에 사용된 최종 SQL 문장")
    data_points: List[InvestmentDetail] = Field(..., description="검증된 상세 데이터 리스트")
    summary: str = Field(..., description="전체 데이터를 관통하는 핵심 요약")
