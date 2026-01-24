"""
해외시장 지수 크롤링 API
실행 시 자동으로 해외시장 지수를 수집하여 날짜별 JSON 파일로 저장합니다.
"""

from fastapi import FastAPI, HTTPException
from typing import Optional
from datetime import datetime
import json
import os
from crawlers.market_crawler import crawler

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="해외시장 지수 크롤링 API",
    description="해외 주요 시장 지수를 실시간으로 조회하고 수집하는 API",
    version="1.0.0"
)


# ========================================
# 데이터 저장 함수
# ========================================

def save_market_data_to_json():
    """해외시장 지수 데이터를 날짜별 JSON 파일로 저장"""
    try:
        # data 폴더가 없으면 생성
        os.makedirs('data', exist_ok=True)

        # 현재 날짜로 파일명 생성
        today = datetime.now().strftime('%Y-%m-%d')
        filename = f'data/global_point_{today}.json'

        # 시장 데이터 수집
        print("📊 해외시장 지수 데이터 수집 중...")
        market_data = crawler.get_market_summary()

        # JSON 파일로 저장
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(market_data, f, ensure_ascii=False, indent=2)

        print(f"✅ 해외시장 지수 데이터 저장 완료: {filename}")
        return filename

    except Exception as e:
        print(f"❌ 데이터 저장 실패: {e}")
        return None


# ========================================
# FastAPI 이벤트 핸들러
# ========================================

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 자동으로 해외시장 지수 데이터 수집 및 저장"""
    print("\n" + "="*60)
    print("🚀 해외시장 지수 크롤링 API 서버 시작")
    print("="*60)
    save_market_data_to_json()
    print("="*60)
    print("✅ 서버 준비 완료!")
    print("📖 API 문서: http://localhost:8000/docs")
    print("="*60 + "\n")


# ========================================
# API 엔드포인트
# ========================================

@app.get("/", tags=["기본"])
async def root():
    """루트 엔드포인트 - API 정보"""
    return {
        "title": "해외시장 지수 크롤링 API",
        "version": "1.0.0",
        "description": "해외 주요 시장 지수를 실시간으로 조회하고 수집합니다.",
        "docs": "/docs",
        "endpoints": {
            "전체 지수 조회": "GET /market/indices",
            "지역별 지수 조회": "GET /market/indices?region={us|asia|europe}",
            "특정 지수 조회": "GET /market/index/{symbol}",
            "시장 요약": "GET /market/summary",
            "데이터 수집 및 저장": "POST /market/collect"
        },
        "supported_indices": {
            "미국": ["dow", "sp500", "nasdaq"],
            "아시아": ["nikkei", "hangseng", "shanghai", "shenzhen"],
            "유럽": ["stoxx50", "ftse", "dax"]
        }
    }


@app.get("/market/indices", tags=["해외시장 지수"])
async def get_market_indices(region: Optional[str] = None):
    """
    해외시장 지수를 조회합니다.

    - **region**: 지역 필터 (us, asia, europe) - 생략 시 전체 조회

    **지원 지수:**
    - 미국: 다우존스, S&P 500, 나스닥
    - 아시아: 닛케이225, 항셍, 상해종합, 심천성분
    - 유럽: STOXX 50, FTSE 100, DAX
    """
    try:
        if region and region not in ['us', 'asia', 'europe']:
            raise HTTPException(
                status_code=400,
                detail="region은 'us', 'asia', 'europe' 중 하나여야 합니다."
            )

        indices = crawler.get_all_indices(region)

        if not indices:
            raise HTTPException(
                status_code=503,
                detail="지수 데이터를 가져올 수 없습니다. 잠시 후 다시 시도해주세요."
            )

        return {
            "region": region or "all",
            "count": len(indices),
            "indices": indices,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


@app.get("/market/index/{symbol}", tags=["해외시장 지수"])
async def get_market_index(symbol: str):
    """
    특정 해외시장 지수를 조회합니다.

    - **symbol**: 지수 심볼

    **지원되는 심볼:**
    - dow: 다우존스
    - sp500: S&P 500
    - nasdaq: 나스닥
    - nikkei: 닛케이225
    - hangseng: 항셍
    - shanghai: 상해종합
    - shenzhen: 심천성분
    - stoxx50: STOXX 50
    - ftse: FTSE 100
    - dax: DAX
    """
    try:
        data = crawler.get_index_data(symbol)

        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"지수 '{symbol}'을(를) 찾을 수 없습니다. 지원되는 심볼: dow, sp500, nasdaq, nikkei, hangseng, shanghai, shenzhen, stoxx50, ftse, dax"
            )

        return data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


@app.get("/market/summary", tags=["해외시장 지수"])
async def get_market_summary():
    """
    전체 시장 요약 정보를 조회합니다.

    미국, 아시아, 유럽 주요 지수를 한번에 조회할 수 있습니다.
    """
    try:
        summary = crawler.get_market_summary()

        if summary['total_count'] == 0:
            raise HTTPException(
                status_code=503,
                detail="시장 데이터를 가져올 수 없습니다. 잠시 후 다시 시도해주세요."
            )

        return summary

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


@app.post("/market/collect", tags=["해외시장 지수"])
async def collect_market_data():
    """
    해외시장 지수 데이터를 수집하여 날짜별 JSON 파일로 저장합니다.

    파일은 data/global_point_YYYY-MM-DD.json 형식으로 저장됩니다.
    """
    try:
        filename = save_market_data_to_json()

        if filename:
            return {
                "status": "success",
                "message": "해외시장 지수 데이터 수집 및 저장 완료",
                "filename": filename,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="데이터 수집 및 저장 실패"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("\n🌍 해외시장 지수 크롤링 서버를 시작합니다...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
