"""
해외시장 지수 자동 수집 스크립트
GitHub Actions에서 실행되어 날짜별 JSON 파일로 저장합니다.
"""

import json
import os
from datetime import datetime
from crawlers.market_crawler import crawler


def collect_and_save():
    """해외시장 지수 데이터를 수집하여 JSON 파일로 저장"""
    print("\n" + "="*60)
    print("📊 해외시장 지수 자동 수집 시작")
    print("="*60)

    try:
        # data 폴더가 없으면 생성
        os.makedirs('data', exist_ok=True)
        print("✅ data 폴더 확인 완료")

        # 현재 날짜로 파일명 생성
        today = datetime.now().strftime('%Y-%m-%d')
        filename = f'data/global_point_{today}.json'

        print(f"📅 수집 날짜: {today}")
        print(f"📁 저장 파일: {filename}")

        # 시장 데이터 수집
        print("\n🌍 해외시장 지수 크롤링 중...")
        market_data = crawler.get_market_summary()

        if market_data['total_count'] == 0:
            print("❌ 수집된 데이터가 없습니다.")
            return False

        # 수집된 데이터 요약 출력
        print(f"\n📈 수집 완료:")
        print(f"  - 미국 시장: {len(market_data['us_market'])}개 지수")
        print(f"  - 아시아 시장: {len(market_data['asia_market'])}개 지수")
        print(f"  - 유럽 시장: {len(market_data['europe_market'])}개 지수")
        print(f"  - 총 {market_data['total_count']}개 지수")

        # JSON 파일로 저장
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(market_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 데이터 저장 완료: {filename}")

        # 파일 크기 확인
        file_size = os.path.getsize(filename)
        print(f"📦 파일 크기: {file_size} bytes")

        print("="*60)
        print("✅ 해외시장 지수 자동 수집 완료!")
        print("="*60 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print("="*60 + "\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = collect_and_save()

    if not success:
        print("⚠️  데이터 수집에 실패했습니다.")
        exit(1)
    else:
        print("🎉 데이터 수집이 성공적으로 완료되었습니다.")
        exit(0)
