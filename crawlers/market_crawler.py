"""
해외시장 지수 크롤러
주요 해외 시장 지수를 크롤링하여 데이터를 제공합니다.
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import time

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketIndexCrawler:
    """해외시장 지수 크롤러 클래스"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 주요 지수 심볼 매핑
        self.index_symbols = {
            # 미국
            'dow': '^DJI',           # 다우존스
            'sp500': '^GSPC',        # S&P 500
            'nasdaq': '^IXIC',       # 나스닥

            # 아시아
            'nikkei': '^N225',       # 일본 닛케이225
            'hangseng': '^HSI',      # 홍콩 항셍
            'shanghai': '000001.SS', # 중국 상해종합
            'shenzhen': '399001.SZ', # 중국 심천성분

            # 유럽
            'stoxx50': '^STOXX50E',  # 유로 STOXX 50
            'ftse': '^FTSE',         # 영국 FTSE 100
            'dax': '^GDAXI',         # 독일 DAX
        }

        self.index_names = {
            'dow': '다우존스',
            'sp500': 'S&P 500',
            'nasdaq': '나스닥',
            'nikkei': '닛케이225',
            'hangseng': '항셍',
            'shanghai': '상해종합',
            'shenzhen': '심천성분',
            'stoxx50': 'STOXX 50',
            'ftse': 'FTSE 100',
            'dax': 'DAX',
        }

    def get_index_data(self, symbol_key: str) -> Optional[Dict]:
        """
        특정 지수 데이터 조회

        Args:
            symbol_key: 지수 키 (예: 'dow', 'sp500', 'nasdaq')

        Returns:
            지수 데이터 딕셔너리 또는 None
        """
        try:
            symbol = self.index_symbols.get(symbol_key)
            if not symbol:
                logger.error(f"Unknown symbol key: {symbol_key}")
                return None

            # Yahoo Finance API 사용 (비공식)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {
                'interval': '1d',
                'range': '1d'
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # 데이터 추출
            quote = data['chart']['result'][0]
            meta = quote['meta']

            current_price = meta.get('regularMarketPrice', 0)
            previous_close = meta.get('previousClose', 0)
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close else 0

            return {
                'symbol': symbol_key,
                'name': self.index_names.get(symbol_key, symbol_key),
                'current_price': round(current_price, 2),
                'previous_close': round(previous_close, 2),
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'currency': meta.get('currency', 'USD'),
                'market_state': meta.get('marketState', 'UNKNOWN'),
                'timestamp': datetime.fromtimestamp(meta.get('regularMarketTime', 0)).isoformat(),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {symbol_key}: {e}")
            return None
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Data parsing error for {symbol_key}: {e}")
            return None

    def get_all_indices(self, region: Optional[str] = None) -> List[Dict]:
        """
        전체 또는 특정 지역의 지수 데이터 조회

        Args:
            region: 지역 필터 ('us', 'asia', 'europe') 또는 None (전체)

        Returns:
            지수 데이터 리스트
        """
        region_mapping = {
            'us': ['dow', 'sp500', 'nasdaq'],
            'asia': ['nikkei', 'hangseng', 'shanghai', 'shenzhen'],
            'europe': ['stoxx50', 'ftse', 'dax']
        }

        if region and region in region_mapping:
            symbols = region_mapping[region]
        else:
            symbols = list(self.index_symbols.keys())

        results = []
        for symbol_key in symbols:
            data = self.get_index_data(symbol_key)
            if data:
                results.append(data)

        return results

    def get_market_summary(self) -> Dict:
        """
        주요 시장 요약 정보 조회

        Returns:
            시장 요약 데이터
        """
        us_indices = self.get_all_indices('us')
        asia_indices = self.get_all_indices('asia')
        europe_indices = self.get_all_indices('europe')

        return {
            'update_time': datetime.now().isoformat(),
            'us_market': us_indices,
            'asia_market': asia_indices,
            'europe_market': europe_indices,
            'total_count': len(us_indices) + len(asia_indices) + len(europe_indices)
        }

    def get_historical_data(self, symbol_key: str, target_date: datetime) -> Optional[Dict]:
        """
        특정 날짜의 지수 데이터 조회

        Args:
            symbol_key: 지수 키 (예: 'dow', 'sp500', 'nasdaq')
            target_date: 조회할 날짜

        Returns:
            지수 데이터 딕셔너리 또는 None
        """
        try:
            symbol = self.index_symbols.get(symbol_key)
            if not symbol:
                logger.error(f"Unknown symbol key: {symbol_key}")
                return None

            # 날짜를 Unix timestamp로 변환
            period1 = int(target_date.replace(hour=0, minute=0, second=0).timestamp())
            period2 = int((target_date + timedelta(days=1)).replace(hour=0, minute=0, second=0).timestamp())

            # Yahoo Finance API 사용
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {
                'period1': period1,
                'period2': period2,
                'interval': '1d'
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # 데이터 추출
            quote = data['chart']['result'][0]

            # 해당 날짜 데이터가 없을 수 있음 (주말, 휴일 등)
            if 'indicators' not in quote or not quote['indicators']['quote']:
                logger.warning(f"No data for {symbol_key} on {target_date.date()}")
                return None

            indicators = quote['indicators']['quote'][0]
            timestamps = quote['timestamp']

            if not timestamps or not indicators.get('close'):
                logger.warning(f"No trading data for {symbol_key} on {target_date.date()}")
                return None

            # 종가 데이터 추출
            close_price = indicators['close'][0] if indicators['close'][0] is not None else 0
            open_price = indicators['open'][0] if indicators['open'] and indicators['open'][0] is not None else close_price

            # 이전 종가 (전일 종가)
            previous_close = quote['meta'].get('previousClose', open_price)

            change = close_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close else 0

            return {
                'symbol': symbol_key,
                'name': self.index_names.get(symbol_key, symbol_key),
                'current_price': round(close_price, 2),
                'previous_close': round(previous_close, 2),
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'currency': quote['meta'].get('currency', 'USD'),
                'market_state': 'CLOSED',
                'timestamp': target_date.isoformat(),
                'date': target_date.strftime('%Y-%m-%d')
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {symbol_key} on {target_date.date()}: {e}")
            return None
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Data parsing error for {symbol_key} on {target_date.date()}: {e}")
            return None

    def get_historical_market_summary(self, target_date: datetime) -> Dict:
        """
        특정 날짜의 시장 요약 정보 조회

        Args:
            target_date: 조회할 날짜

        Returns:
            시장 요약 데이터
        """
        region_mapping = {
            'us': ['dow', 'sp500', 'nasdaq'],
            'asia': ['nikkei', 'hangseng', 'shanghai', 'shenzhen'],
            'europe': ['stoxx50', 'ftse', 'dax']
        }

        us_indices = []
        asia_indices = []
        europe_indices = []

        # 미국 지수
        for symbol_key in region_mapping['us']:
            data = self.get_historical_data(symbol_key, target_date)
            if data:
                us_indices.append(data)
            time.sleep(0.1)  # API 요청 간격

        # 아시아 지수
        for symbol_key in region_mapping['asia']:
            data = self.get_historical_data(symbol_key, target_date)
            if data:
                asia_indices.append(data)
            time.sleep(0.1)

        # 유럽 지수
        for symbol_key in region_mapping['europe']:
            data = self.get_historical_data(symbol_key, target_date)
            if data:
                europe_indices.append(data)
            time.sleep(0.1)

        return {
            'update_time': datetime.now().isoformat(),
            'target_date': target_date.strftime('%Y-%m-%d'),
            'us_market': us_indices,
            'asia_market': asia_indices,
            'europe_market': europe_indices,
            'total_count': len(us_indices) + len(asia_indices) + len(europe_indices)
        }


# 싱글톤 인스턴스
crawler = MarketIndexCrawler()
