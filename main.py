from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from statistics import mean

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="학생 점수 관리 API",
    description="학생들의 점수를 관리하는 FastAPI 샘플 애플리케이션",
    version="1.0.0"
)

# 초기 점수 데이터
score = [
    ['정약용', 85, 90, 80, 75],
    ['이순신', 78, 82, 90, 88],
    ['이율곡', 92, 85, 87, 95],
    ['홍길동', 80, 76, 70, 82],
    ['신사임당', 95, 98, 94, 99],
    ['최무선', 73, 70, 78, 80],
    ['장영실', 88, 89, 85, 92],
    ['김유신', 77, 75, 73, 70],
    ['안중근', 84, 83, 80, 79],
    ['세종대왕', 99, 97, 98, 96]
]
# 각 항목: [이름, 국어, 영어, 수학, 과학]


# Pydantic 모델 정의
class ScoreInput(BaseModel):
    """점수 입력 모델"""
    name: str = Field(..., description="학생 이름", example="홍길동")
    korean: int = Field(..., ge=0, le=100, description="국어 점수", example=85)
    english: int = Field(..., ge=0, le=100, description="영어 점수", example=90)
    math: int = Field(..., ge=0, le=100, description="수학 점수", example=80)
    science: int = Field(..., ge=0, le=100, description="과학 점수", example=75)


class ScoreResponse(BaseModel):
    """점수 응답 모델"""
    name: str = Field(..., description="학생 이름")
    korean: int = Field(..., description="국어 점수")
    english: int = Field(..., description="영어 점수")
    math: int = Field(..., description="수학 점수")
    science: int = Field(..., description="과학 점수")
    total: int = Field(..., description="총점")
    average: float = Field(..., description="평균 점수")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "정약용",
                "korean": 85,
                "english": 90,
                "math": 80,
                "science": 75,
                "total": 330,
                "average": 82.5
            }
        }


class StatisticsResponse(BaseModel):
    """통계 응답 모델"""
    total_students: int = Field(..., description="전체 학생 수")
    average_korean: float = Field(..., description="국어 평균")
    average_english: float = Field(..., description="영어 평균")
    average_math: float = Field(..., description="수학 평균")
    average_science: float = Field(..., description="과학 평균")
    overall_average: float = Field(..., description="전체 평균")
    top_student: str = Field(..., description="최고 점수 학생")


# 데이터를 딕셔너리 형태로 변환하는 헬퍼 함수
def convert_to_dict(score_list: List) -> dict:
    """점수 리스트를 딕셔너리로 변환"""
    return {
        "name": score_list[0],
        "korean": score_list[1],
        "english": score_list[2],
        "math": score_list[3],
        "science": score_list[4]
    }


def calculate_scores(score_dict: dict) -> dict:
    """총점과 평균을 계산하여 응답 모델 생성"""
    total = score_dict["korean"] + score_dict["english"] + score_dict["math"] + score_dict["science"]
    average = round(total / 4, 2)
    
    return {
        **score_dict,
        "total": total,
        "average": average
    }


# API 엔드포인트

@app.get("/", tags=["기본"])
async def root():
    """루트 엔드포인트 - API 정보"""
    return {
        "message": "학생 점수 관리 API에 오신 것을 환영합니다!",
        "docs": "/docs",
        "endpoints": {
            "전체 학생 목록": "/students",
            "학생 조회": "/students/{name}",
            "통계 정보": "/statistics"
        }
    }


@app.get("/students", response_model=List[ScoreResponse], tags=["학생 관리"])
async def get_all_students():
    """
    전체 학생 목록과 점수를 조회합니다.
    
    - **name**: 학생 이름
    - **korean**: 국어 점수
    - **english**: 영어 점수
    - **math**: 수학 점수
    - **science**: 과학 점수
    - **total**: 총점
    - **average**: 평균 점수
    """
    result = []
    for student_score in score:
        score_dict = convert_to_dict(student_score)
        result.append(calculate_scores(score_dict))
    
    return result


@app.get("/students/{name}", response_model=ScoreResponse, tags=["학생 관리"])
async def get_student(name: str):
    """
    특정 학생의 점수를 조회합니다.
    
    - **name**: 조회할 학생 이름
    """
    for student_score in score:
        if student_score[0] == name:
            score_dict = convert_to_dict(student_score)
            return calculate_scores(score_dict)
    
    raise HTTPException(status_code=404, detail=f"학생 '{name}'을(를) 찾을 수 없습니다.")


@app.get("/statistics", response_model=StatisticsResponse, tags=["통계"])
async def get_statistics():
    """
    전체 학생들의 점수 통계를 조회합니다.
    
    - **total_students**: 전체 학생 수
    - **average_korean**: 국어 평균 점수
    - **average_english**: 영어 평균 점수
    - **average_math**: 수학 평균 점수
    - **average_science**: 과학 평균 점수
    - **overall_average**: 전체 과목 평균
    - **top_student**: 최고 점수 학생
    """
    if not score:
        raise HTTPException(status_code=404, detail="점수 데이터가 없습니다.")
    
    # 각 과목별 점수 리스트 추출
    korean_scores = [s[1] for s in score]
    english_scores = [s[2] for s in score]
    math_scores = [s[3] for s in score]
    science_scores = [s[4] for s in score]
    
    # 평균 계산
    avg_korean = round(mean(korean_scores), 2)
    avg_english = round(mean(english_scores), 2)
    avg_math = round(mean(math_scores), 2)
    avg_science = round(mean(science_scores), 2)
    overall_avg = round(mean([avg_korean, avg_english, avg_math, avg_science]), 2)
    
    # 최고 점수 학생 찾기
    student_totals = []
    for student_score in score:
        total = sum(student_score[1:])
        student_totals.append((student_score[0], total))
    
    top_student = max(student_totals, key=lambda x: x[1])[0]
    
    return {
        "total_students": len(score),
        "average_korean": avg_korean,
        "average_english": avg_english,
        "average_math": avg_math,
        "average_science": avg_science,
        "overall_average": overall_avg,
        "top_student": top_student
    }


@app.post("/students", response_model=ScoreResponse, tags=["학생 관리"])
async def create_student(score_input: ScoreInput):
    """
    새로운 학생의 점수를 추가합니다.
    
    - **name**: 학생 이름
    - **korean**: 국어 점수 (0-100)
    - **english**: 영어 점수 (0-100)
    - **math**: 수학 점수 (0-100)
    - **science**: 과학 점수 (0-100)
    """
    # 중복 체크
    for student_score in score:
        if student_score[0] == score_input.name:
            raise HTTPException(
                status_code=400, 
                detail=f"학생 '{score_input.name}'은(는) 이미 존재합니다."
            )
    
    # 새 학생 추가
    new_student = [
        score_input.name,
        score_input.korean,
        score_input.english,
        score_input.math,
        score_input.science
    ]
    score.append(new_student)
    
    score_dict = convert_to_dict(new_student)
    return calculate_scores(score_dict)


@app.put("/students/{name}", response_model=ScoreResponse, tags=["학생 관리"])
async def update_student(name: str, score_input: ScoreInput):
    """
    기존 학생의 점수를 수정합니다.
    
    - **name**: 수정할 학생 이름
    - **score_input**: 새로운 점수 정보
    """
    for i, student_score in enumerate(score):
        if student_score[0] == name:
            # 점수 업데이트
            score[i] = [
                score_input.name,
                score_input.korean,
                score_input.english,
                score_input.math,
                score_input.science
            ]
            score_dict = convert_to_dict(score[i])
            return calculate_scores(score_dict)
    
    raise HTTPException(status_code=404, detail=f"학생 '{name}'을(를) 찾을 수 없습니다.")


@app.delete("/students/{name}", tags=["학생 관리"])
async def delete_student(name: str):
    """
    학생을 삭제합니다.
    
    - **name**: 삭제할 학생 이름
    """
    for i, student_score in enumerate(score):
        if student_score[0] == name:
            deleted_student = score.pop(i)
            return {
                "message": f"학생 '{name}'이(가) 삭제되었습니다.",
                "deleted_student": convert_to_dict(deleted_student)
            }
    
    raise HTTPException(status_code=404, detail=f"학생 '{name}'을(를) 찾을 수 없습니다.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
