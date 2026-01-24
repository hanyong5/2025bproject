"""
한 달간 과거 해외시장 지수 데이터 수집 스크립트
오늘 이전 30일간의 데이터를 날짜별 JSON 파일로 저장합니다.
"""

import json
import os
from datetime import datetime, timedelta
from crawlers.market_crawler import crawler


def collect_last_30_days():
    """오늘 이전 30일간의 해외시장 지수 데이터를 수집"""
    print("\n" + "="*60)
    print("📊 한 달간 해외시장 지수 데이터 수집 시작")
    print("="*60)

    try:
        # data 폴더가 없으면 생성
        os.makedirs('data', exist_ok=True)
        print("✅ data 폴더 확인 완료")

        # 오늘 날짜
        today = datetime.now()

        # 수집 시작일 (30일 전)
        start_date = today - timedelta(days=30)

        print(f"\n📅 수집 기간: {start_date.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}")
        print(f"📦 총 {31}일치 데이터 수집 예정\n")

        success_count = 0
        fail_count = 0

        # 30일 전부터 오늘까지 반복
        for i in range(31):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            filename = f'data/global_point_{date_str}.json'

            # 이미 파일이 존재하는지 확인
            if os.path.exists(filename):
                print(f"⏭️  [{i+1}/31] {date_str} - 파일이 이미 존재합니다. 건너뜁니다.")
                success_count += 1
                continue

            print(f"📥 [{i+1}/31] {date_str} 데이터 수집 중...", end=" ")

            try:
                # 과거 데이터 수집
                market_data = crawler.get_historical_market_summary(current_date)

                if market_data['total_count'] == 0:
                    print(f"❌ 데이터 없음 (주말/휴일)")
                    fail_count += 1
                    continue

                # JSON 파일로 저장
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(market_data, f, ensure_ascii=False, indent=2)

                file_size = os.path.getsize(filename)
                print(f"✅ 저장 완료 ({market_data['total_count']}개 지수, {file_size} bytes)")
                success_count += 1

            except Exception as e:
                print(f"❌ 실패: {e}")
                fail_count += 1

        # 결과 요약
        print("\n" + "="*60)
        print("📊 수집 결과 요약")
        print("="*60)
        print(f"✅ 성공: {success_count}개 파일")
        print(f"❌ 실패: {fail_count}개 파일")
        print(f"📁 저장 위치: data/")
        print("="*60 + "\n")

        # 저장된 파일 목록 출력
        print("📂 저장된 파일 목록:")
        files = sorted([f for f in os.listdir('data') if f.startswith('global_point_')])
        for file in files:
            file_path = os.path.join('data', file)
            file_size = os.path.getsize(file_path)
            print(f"  - {file} ({file_size} bytes)")

        print("\n✅ 한 달간 데이터 수집 완료!")
        return success_count > 0

    except Exception as e:
        print(f"\n❌ 전체 프로세스 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🌍 오늘 이전 30일간 해외시장 지수 데이터 수집")
    print("⚠️  이 작업은 시간이 걸릴 수 있습니다 (약 30초~1분)\n")

    success = collect_last_30_days()

    if not success:
        print("⚠️  일부 데이터 수집에 실패했습니다.")
        exit(1)
    else:
        print("🎉 데이터 수집이 성공적으로 완료되었습니다.")
        exit(0)
