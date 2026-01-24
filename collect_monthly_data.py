"""
한 달간 해외시장 지수 데이터를 하나의 파일로 수집
오늘 이전 30일간의 데이터를 하나의 JSON 파일에 저장합니다.
"""

import json
import os
from datetime import datetime, timedelta
from crawlers.market_crawler import crawler


def collect_monthly_data_to_single_file():
    """오늘 이전 30일간의 해외시장 지수 데이터를 하나의 파일로 수집"""
    print("\n" + "="*60)
    print("[DATA] 한 달간 해외시장 지수 데이터 수집 (단일 파일)")
    print("="*60)

    try:
        # data 폴더가 없으면 생성
        os.makedirs('data', exist_ok=True)
        print("[OK] data 폴더 확인 완료")

        # 오늘 날짜
        today = datetime.now()

        # 수집 시작일 (30일 전)
        start_date = today - timedelta(days=30)

        print(f"\n[INFO] 수집 기간: {start_date.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}")
        print(f"[INFO] 총 {31}일치 데이터 수집 예정\n")

        # 전체 데이터를 담을 리스트
        all_data = []
        success_count = 0
        fail_count = 0

        # 30일 전부터 오늘까지 반복
        for i in range(31):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')

            print(f"[{i+1}/31] {date_str} 데이터 수집 중...", end=" ")

            try:
                # 과거 데이터 수집
                market_data = crawler.get_historical_market_summary(current_date)

                if market_data['total_count'] == 0:
                    print(f"[SKIP] 데이터 없음 (주말/휴일)")
                    fail_count += 1
                    # 빈 데이터도 포함 (날짜 연속성 유지)
                    all_data.append({
                        'date': date_str,
                        'has_data': False,
                        'us_market': [],
                        'asia_market': [],
                        'europe_market': [],
                        'total_count': 0
                    })
                else:
                    print(f"[OK] 수집 완료 ({market_data['total_count']}개 지수)")
                    success_count += 1
                    # 날짜 정보 포함하여 저장
                    all_data.append({
                        'date': date_str,
                        'has_data': True,
                        'us_market': market_data['us_market'],
                        'asia_market': market_data['asia_market'],
                        'europe_market': market_data['europe_market'],
                        'total_count': market_data['total_count']
                    })

            except Exception as e:
                print(f"[ERROR] 실패: {e}")
                fail_count += 1
                # 에러 발생 시에도 빈 데이터 추가
                all_data.append({
                    'date': date_str,
                    'has_data': False,
                    'error': str(e),
                    'us_market': [],
                    'asia_market': [],
                    'europe_market': [],
                    'total_count': 0
                })

        # 전체 데이터를 하나의 JSON 파일로 저장
        filename = f'data/global_point_monthly.json'

        monthly_data = {
            'collection_info': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': today.strftime('%Y-%m-%d'),
                'total_days': 31,
                'success_days': success_count,
                'fail_days': fail_count,
                'collected_at': datetime.now().isoformat()
            },
            'data': all_data
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(monthly_data, f, ensure_ascii=False, indent=2)

        file_size = os.path.getsize(filename)

        # 결과 요약
        print("\n" + "="*60)
        print("[DATA] 수집 결과 요약")
        print("="*60)
        print(f"[OK] 성공: {success_count}일")
        print(f"[SKIP] 실패/휴일: {fail_count}일")
        print(f"[FILE] 저장 파일: {filename}")
        print(f"[SIZE] 파일 크기: {file_size:,} bytes ({file_size/1024:.2f} KB)")
        print("="*60 + "\n")

        print(f"[OK] 한 달간 데이터가 하나의 파일로 저장되었습니다!")
        print(f"[FILE] 파일명: {filename}")

        return True

    except Exception as e:
        print(f"\n[ERROR] 전체 프로세스 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n[INFO] 오늘 이전 30일간 해외시장 지수 데이터 수집 (단일 파일)")
    print("[WARNING] 이 작업은 시간이 걸릴 수 있습니다 (약 30초~1분)\n")

    success = collect_monthly_data_to_single_file()

    if not success:
        print("[ERROR] 데이터 수집에 실패했습니다.")
        exit(1)
    else:
        print("[SUCCESS] 데이터 수집이 성공적으로 완료되었습니다.")
        exit(0)
