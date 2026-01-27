import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import random
import re
from datetime import datetime, timedelta
import json
import os
import hashlib
import glob

URL = "https://finance.naver.com/news/mainnews.naver"

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
]

accept_languages = [
    "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "ko,en-US;q=0.9,en;q=0.8",
    "en-US,en;q=0.9,ko-KR;q=0.8,ko;q=0.7"
]

headers = {
    "User-Agent": random.choice(user_agents),
    "Accept-Language": random.choice(accept_languages),
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://finance.naver.com/",
    "Cache-Control": "no-cache",
}

# 오늘 날짜를 YYYY-MM-DD 형식으로 가져오기
def get_today_date():
    """오늘 날짜를 YYYY-MM-DD 형식으로 반환"""
    return datetime.now().strftime('%Y-%m-%d')

# 날짜와 페이지를 포함한 URL 생성
def build_url_with_params(date=None, page=1):
    """날짜와 페이지 파라미터를 포함한 URL 생성"""
    if date is None:
        date = get_today_date()
    
    return f"{URL}?date={date}&page={page}"

# 데이터 해시값 계산 (중복 체크용)
def calculate_data_hash(data):
    """데이터의 해시값을 계산하여 반환"""
    data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(data_str.encode('utf-8')).hexdigest()

# 기존 데이터 로드
def load_existing_data(filepath):
    """기존 JSON 파일에서 데이터를 로드"""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"⚠️ 기존 데이터 로드 실패: {e}")
            return None
    return None

# 데이터 저장
def save_data_to_json(data, filepath):
    """데이터를 JSON 파일로 저장"""
    try:
        # data 폴더가 없으면 생성
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # 데이터에 메타데이터 추가
        output_data = {
            "date": get_today_date(),
            "timestamp": datetime.now().isoformat(),
            "total_count": len(data),
            "data_hash": calculate_data_hash(data),
            "news": data
        }
        
        # JSON 파일로 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 데이터 저장 완료: {filepath}")
        return True
    except Exception as e:
        print(f"❌ 데이터 저장 실패: {e}")
        return False

# 데이터 중복 체크
def is_data_duplicate(new_data, existing_data):
    """새 데이터와 기존 데이터가 동일한지 확인"""
    if not existing_data:
        return False
    
    # 해시값 비교
    new_hash = calculate_data_hash(new_data)
    existing_hash = existing_data.get("data_hash", "")
    
    if new_hash == existing_hash:
        return True
    
    # 해시값이 없거나 다른 경우, 실제 데이터 비교
    new_news = new_data
    existing_news = existing_data.get("news", [])
    
    if len(new_news) != len(existing_news):
        return False
    
    # 제목 기준으로 비교
    new_titles = {item.get("제목", "") for item in new_news}
    existing_titles = {item.get("제목", "") for item in existing_news}
    
    return new_titles == existing_titles

# 오늘 날짜의 다음 파일 번호 찾기
def get_next_file_number(data_dir, date):
    """오늘 날짜의 기존 파일들을 확인하여 다음 번호 반환"""
    pattern = os.path.join(data_dir, f"{date}_*.json")
    existing_files = glob.glob(pattern)
    
    if not existing_files:
        return "01"
    
    # 파일명에서 번호 추출
    numbers = []
    for filepath in existing_files:
        filename = os.path.basename(filepath)
        # YYYY-MM-DD_NN.json 형식에서 NN 추출
        try:
            parts = filename.replace('.json', '').split('_')
            if len(parts) >= 2:
                num_str = parts[-1]
                if num_str.isdigit():
                    numbers.append(int(num_str))
        except:
            continue
    
    if not numbers:
        return "01"
    
    # 다음 번호 계산
    next_num = max(numbers) + 1
    return f"{next_num:02d}"

# 파일명 생성
def generate_filename(data_dir, date):
    """날짜와 번호를 포함한 파일명 생성"""
    file_number = get_next_file_number(data_dir, date)
    filename = f"{date}_{file_number}.json"
    return os.path.join(data_dir, filename)

# 5일 이상 지난 파일 삭제
def delete_old_files(data_dir, days=5):
    """지정된 일수 이상 지난 파일 삭제"""
    try:
        if not os.path.exists(data_dir):
            return
        
        # 현재 날짜
        today = datetime.now()
        cutoff_date = today - timedelta(days=days)
        
        # data 폴더의 모든 JSON 파일 확인
        pattern = os.path.join(data_dir, "*.json")
        files = glob.glob(pattern)
        
        deleted_count = 0
        for filepath in files:
            try:
                # 파일명에서 날짜 추출 (YYYY-MM-DD_NN.json 형식)
                filename = os.path.basename(filepath)
                date_str = filename.split('_')[0]
                
                # 날짜 파싱
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                # 5일 이상 지난 파일 삭제
                if file_date < cutoff_date:
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"🗑️ 오래된 파일 삭제: {filename}")
            except Exception as e:
                # 날짜 파싱 실패 시 스킵
                continue
        
        if deleted_count > 0:
            print(f"✅ 총 {deleted_count}개의 오래된 파일을 삭제했습니다.")
        else:
            print(f"ℹ️ 삭제할 오래된 파일이 없습니다.")
            
    except Exception as e:
        print(f"⚠️ 오래된 파일 삭제 중 오류 발생: {e}")

# .Nnavi를 통해 오늘 날짜의 페이지 개수 파악
def get_today_page_count(date=None):
    """Nnavi 클래스를 통해 지정된 날짜의 페이지 개수 파악"""
    try:
        if date is None:
            date = get_today_date()
        
        # 오늘 날짜의 첫 페이지로 요청
        url_with_date = build_url_with_params(date=date, page=1)
        response = requests.get(url_with_date, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'euc-kr'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # .Nnavi 클래스를 가진 요소 찾기
        nnavi_elements = soup.select('.Nnavi')
        
        if not nnavi_elements:
            return 0
        
        page_numbers = []
        max_page = 0
        
        # 오늘 날짜 확인
        today = datetime.now().strftime('%Y%m%d')
        
        for nnavi_container in nnavi_elements:
            # 페이지네이션 링크 찾기 (일반적으로 a 태그에 페이지 번호가 있음)
            # 페이지 번호 패턴: 숫자만 있는 링크나 페이지 번호가 포함된 링크
            page_links = nnavi_container.find_all('a', href=True)
            
            # "다음", "마지막", "Last" 등의 버튼 찾기
            next_buttons = nnavi_container.find_all(['a', 'span', 'button'], 
                                                    string=lambda x: x and any(keyword in str(x) for keyword in ['다음', '마지막', 'Last', 'next', '>', '»']))
            
            for link in page_links:
                href = link.get('href', '')
                link_text = link.get_text(strip=True)
                
                # 링크 텍스트가 숫자인 경우
                if link_text.isdigit():
                    page_num = int(link_text)
                    page_numbers.append(page_num)
                    if page_num > max_page:
                        max_page = page_num
                
                # "마지막", "Last" 등의 텍스트가 있는 링크에서 페이지 번호 추출
                if any(keyword in link_text for keyword in ['마지막', 'Last', '끝']):
                    # URL에서 페이지 번호 추출 시도
                    if href:
                        parsed_url = urlparse(href)
                        query_params = parse_qs(parsed_url.query)
                        for param in ['page', 'p', 'pageno', 'pagenum', 'pageNum']:
                            if param in query_params:
                                try:
                                    page_num = int(query_params[param][0])
                                    if page_num > max_page:
                                        max_page = page_num
                                except (ValueError, IndexError):
                                    pass
                
                # URL에 페이지 번호가 포함된 경우 (예: page=2, p=3 등)
                if href:
                    # URL 파라미터에서 페이지 번호 찾기
                    parsed_url = urlparse(href)
                    query_params = parse_qs(parsed_url.query)
                    
                    # 일반적인 페이지 파라미터명들
                    page_params = ['page', 'p', 'pageno', 'pagenum', 'pageNum']
                    for param in page_params:
                        if param in query_params:
                            try:
                                page_num = int(query_params[param][0])
                                page_numbers.append(page_num)
                                if page_num > max_page:
                                    max_page = page_num
                            except (ValueError, IndexError):
                                pass
                    
                    # URL 경로에서 페이지 번호 찾기 (예: /page/2, /p/3)
                    path_parts = parsed_url.path.split('/')
                    for part in path_parts:
                        if part.isdigit():
                            page_num = int(part)
                            # 너무 큰 숫자는 제외 (연도 등)
                            if 1 <= page_num <= 1000:
                                page_numbers.append(page_num)
                                if page_num > max_page:
                                    max_page = page_num
            
            # 페이지 번호가 아닌 다른 형태로 표시된 경우
            # 예: "1 2 3 ... 10" 형태의 텍스트
            text_content = nnavi_container.get_text()
            # 숫자 패턴 찾기
            number_pattern = r'\b(\d+)\b'
            numbers = re.findall(number_pattern, text_content)
            for num_str in numbers:
                try:
                    num = int(num_str)
                    # 페이지 번호로 보이는 범위 (1~1000)
                    if 1 <= num <= 1000:
                        page_numbers.append(num)
                        if num > max_page:
                            max_page = num
                except ValueError:
                    pass
        
        # 중복 제거 및 정렬
        unique_pages = sorted(set(page_numbers))
        
        # 최대 페이지 번호 반환 (페이지 번호가 있으면)
        if max_page > 0:
            return max_page
        
        # 페이지 번호가 없으면 고유한 페이지 번호 개수 반환
        return len(unique_pages) if unique_pages else 0
        
    except Exception as e:
        print(f"⚠️ 페이지 개수 파악 중 오류: {e}")
        return 0

# 뉴스 상세 내용 가져오기 및 요약
def fetch_news_content(link):
    """뉴스 상세 페이지에서 본문 내용 가져오기"""
    try:
        if not link:
            return None
        
        response = requests.get(link, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'euc-kr'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 네이버 뉴스 본문 찾기 (일반적인 구조)
        content_selectors = [
            '#articleBodyContents',
            '#articleBody',
            '.article_body',
            '.articleBody',
            '.news_end_body',
            '.article_view',
            '#newsEndContents',
            '#articleBodyContents .go_trans _article_content',
            '.article_info'
        ]
        
        content = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # 스크립트 태그 제거
                for script in content_elem(["script", "style", "iframe", "noscript"]):
                    script.decompose()
                content = content_elem.get_text(separator=' ', strip=True)
                if content and len(content) > 50:  # 최소 50자 이상
                    break
        
        # 본문을 찾지 못한 경우, 일반적인 본문 태그 찾기
        if not content or len(content) < 50:
            # id에 body가 포함된 div 찾기
            content_elem = soup.find('div', id=lambda x: x and 'body' in str(x).lower())
            if not content_elem:
                # article 태그 찾기
                content_elem = soup.find('article')
            if not content_elem:
                # class에 article이 포함된 요소 찾기
                content_elem = soup.find('div', class_=lambda x: x and 'article' in str(x).lower())
            
            if content_elem:
                for script in content_elem(["script", "style", "iframe", "noscript"]):
                    script.decompose()
                content = content_elem.get_text(separator=' ', strip=True)
        
        # 본문 정리 (너무 짧거나 의미없는 텍스트 제거)
        if content:
            content = ' '.join(content.split())  # 연속 공백 제거
            # 광고나 불필요한 텍스트 패턴 제거
            lines = content.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line and len(line) > 10:
                    # 광고 관련 키워드가 포함된 줄 제외
                    if not any(keyword in line for keyword in ['광고', 'AD', 'Advertisement', '무단전재', '저작권']):
                        cleaned_lines.append(line)
            content = ' '.join(cleaned_lines)
        
        return content if content and len(content) > 50 else None
        
    except Exception as e:
        return None

# 특정 페이지의 뉴스 리스트 가져오기
def fetch_news_list_from_page(date=None, page=1):
    """특정 날짜와 페이지의 뉴스 리스트 가져오기"""
    try:
        if date is None:
            date = get_today_date()
        
        url_with_params = build_url_with_params(date=date, page=page)
        response = requests.get(url_with_params, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'euc-kr'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_items = []
        
        # .newsList 클래스를 가진 요소 찾기
        news_list = soup.select('.newsList')
        
        if news_list:
            # 각 뉴스 리스트 컨테이너 처리
            for news_container in news_list:
                # 뉴스 항목들 찾기 (일반적으로 li 태그나 article 태그)
                news_items_in_container = news_container.find_all(['li', 'article', 'div'], class_=lambda x: x and ('news' in x.lower() or 'item' in x.lower()))
                
                # 만약 직접적인 뉴스 항목이 없다면, a 태그로 링크가 있는 항목 찾기
                if not news_items_in_container:
                    news_items_in_container = news_container.find_all('a', href=True)
                
                for item in news_items_in_container:
                    # 제목 추출
                    title_elem = item.find(['a', 'strong', 'span', 'h3', 'h4'])
                    if not title_elem:
                        title_elem = item
                    
                    title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
                    
                    # 링크 추출
                    link_elem = item.find('a', href=True) if item.name != 'a' else item
                    link = urljoin(URL, link_elem['href']) if link_elem and link_elem.get('href') else None
                    
                    # 시간/날짜 추출 - .articleSummary .wdate 우선 사용
                    time_elem = item.select_one('.articleSummary .wdate')
                    if not time_elem:
                        time_elem = item.find(['span', 'em', 'time'], class_=lambda x: x and ('time' in x.lower() or 'date' in x.lower() or 'wdate' in x.lower()))
                    if not time_elem:
                        time_elem = item.find('span', string=lambda x: x and any(char in str(x) for char in ['분', '시간', '일', ':', '-']))
                    time_text = time_elem.get_text(strip=True) if time_elem else ""
                    
                    # 요약/내용 추출 - .articleSummary 우선 사용
                    summary_elem = item.select_one('.articleSummary')
                    if summary_elem:
                        # .wdate는 시간이므로 제외하고 요약만 추출
                        wdate_elem = summary_elem.select_one('.wdate')
                        if wdate_elem:
                            wdate_elem.decompose()  # 시간 부분 제거
                        summary = summary_elem.get_text(strip=True)
                    else:
                        summary_elem = item.find(['p', 'span', 'div'], class_=lambda x: x and ('summary' in x.lower() or 'desc' in x.lower() or 'content' in x.lower()))
                        summary = summary_elem.get_text(strip=True) if summary_elem else ""
                    
                    if title and title != "제목 없음":
                        news_items.append({
                            "제목": title,
                            "링크": link,

                        })
        else:
            # .newsList가 없는 경우, 다른 일반적인 뉴스 구조 시도
            # ul.newsList 또는 div.newsList 등
            news_list_alt = soup.select('ul.newsList, div.newsList, .newsList ul, .newsList li')
            
            for item in news_list_alt:
                title_elem = item.find('a')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = urljoin(URL, title_elem.get('href', ''))
                    
                    # 시간/날짜 추출 - .articleSummary .wdate 우선 사용
                    time_elem = item.select_one('.articleSummary .wdate')
                    if not time_elem:
                        time_elem = item.find(['span', 'em'], class_=lambda x: x and ('time' in str(x).lower() or 'wdate' in str(x).lower()))
                    time_text = time_elem.get_text(strip=True) if time_elem else ""
                    
                    # 요약/내용 추출 - .articleSummary 우선 사용
                    summary_elem = item.select_one('.articleSummary')
                    if summary_elem:
                        # .wdate는 시간이므로 제외하고 요약만 추출
                        wdate_elem = summary_elem.select_one('.wdate')
                        if wdate_elem:
                            wdate_elem.decompose()  # 시간 부분 제거
                        summary = summary_elem.get_text(strip=True)
                    else:
                        summary = ""
                    
                    if title:
                        news_items.append({
                            "제목": title,
                            "링크": link,

                        })
        
        # .Nnavi 클래스를 가진 요소 찾기 (추가 데이터)
        nnavi_elements = soup.select('.Nnavi')
        
        if nnavi_elements:
            for nnavi_container in nnavi_elements:
                # Nnavi 내부의 뉴스 항목들 찾기
                nnavi_items = nnavi_container.find_all(['li', 'article', 'div', 'a'], recursive=True)
                
                for item in nnavi_items:
                    # 제목 추출
                    title_elem = item.find(['a', 'strong', 'span', 'h3', 'h4', 'dt', 'dd'])
                    if not title_elem:
                        # 직접 텍스트가 있는 경우
                        if item.name == 'a' or item.get_text(strip=True):
                            title_elem = item
                    
                    title = title_elem.get_text(strip=True) if title_elem else ""
                    
                    # 링크 추출
                    link_elem = item.find('a', href=True) if item.name != 'a' else item
                    if item.name == 'a' and item.get('href'):
                        link_elem = item
                    
                    link = None
                    if link_elem:
                        href = link_elem.get('href') if hasattr(link_elem, 'get') else (link_elem['href'] if 'href' in link_elem.attrs else None)
                        if href:
                            link = urljoin(URL, href)
                    
                    # 시간/날짜 추출 - .articleSummary .wdate 우선 사용
                    time_elem = item.select_one('.articleSummary .wdate')
                    if not time_elem:
                        time_elem = item.find(['span', 'em', 'time', 'dd'], class_=lambda x: x and ('time' in x.lower() or 'date' in x.lower() or 'wdate' in x.lower()))
                    if not time_elem:
                        time_elem = item.find('span', string=lambda x: x and any(char in str(x) for char in ['분', '시간', '일', ':', '-']))
                    time_text = time_elem.get_text(strip=True) if time_elem else ""
                    
                    # 요약/내용 추출 - .articleSummary 우선 사용
                    summary_elem = item.select_one('.articleSummary')
                    if summary_elem:
                        # .wdate는 시간이므로 제외하고 요약만 추출
                        wdate_elem = summary_elem.select_one('.wdate')
                        if wdate_elem:
                            wdate_elem.decompose()  # 시간 부분 제거
                        summary = summary_elem.get_text(strip=True)
                    else:
                        summary_elem = item.find(['p', 'span', 'div', 'dd'], class_=lambda x: x and ('summary' in x.lower() or 'desc' in x.lower() or 'content' in x.lower()))
                        if not summary_elem:
                            # Nnavi 내부의 설명 텍스트 찾기
                            summary_elem = item.find(['p', 'span', 'div'], string=lambda x: x and len(str(x).strip()) > 20)
                        summary = summary_elem.get_text(strip=True) if summary_elem else ""
                    
                    # 중복 제거: 이미 추가된 뉴스와 제목이 같으면 스킵
                    if title and title != "제목 없음" and len(title) > 5:
                        # 중복 체크
                        is_duplicate = any(existing.get("제목") == title for existing in news_items)
                        if not is_duplicate:
                            news_items.append({
                                "제목": title,
                                "링크": link,
                                "출처": "Nnavi"  # Nnavi에서 가져온 데이터임을 표시
                            })
        
        return news_items
        
    except Exception as e:
        print(f"⚠️ 뉴스 데이터를 가져오는 중 오류가 발생했습니다: {e}")
        return []

# 오늘 날짜의 모든 페이지에서 뉴스 데이터 누적 수집
def fetch_all_pages_news(date=None):
    """지정된 날짜의 모든 페이지에서 뉴스 데이터를 누적하여 수집"""
    if date is None:
        date = get_today_date()
    
    all_news_items = []
    seen_titles = set()  # 중복 제거를 위한 제목 집합
    
    # 먼저 페이지 개수 파악
    page_count = get_today_page_count(date=date)
    
    if page_count == 0:
        # 페이지 개수를 파악하지 못한 경우, 첫 페이지만 수집
        page_count = 1
    
    print(f"📄 총 {page_count}페이지 수집 시작...")
    
    # 각 페이지를 순회하며 데이터 수집
    for page in range(1, page_count + 1):
        try:
            print(f"📄 페이지 {page}/{page_count} 수집 중...")
            
            # 페이지별 뉴스 데이터 가져오기
            page_news = fetch_news_list_from_page(date=date, page=page)
            
            # 중복 제거하면서 추가
            for news in page_news:
                title = news.get("제목", "")
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    news["페이지"] = page  # 어느 페이지에서 가져왔는지 표시
                    all_news_items.append(news)
            
            # API 호출 제한을 고려한 짧은 대기
            time.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️ 페이지 {page} 수집 중 오류 발생: {e}")
            continue
    
    print(f"✅ 총 {len(all_news_items)}개의 뉴스를 수집했습니다.")
    
    return all_news_items

# 메인 실행 함수
def main():
    """메인 실행 함수"""
    print("\n" + "="*60)
    print("📰 네이버 금융 뉴스 데이터 수집 시작")
    print("="*60)
    
    # 파일 경로 설정
    data_dir = "data"
    today_date = get_today_date()
    print(f"📅 날짜: {today_date}")
    
    # 오래된 파일 삭제 (5일 이상)
    print("\n🗑️ 오래된 파일 정리 중...")
    delete_old_files(data_dir, days=5)
    
    # 오늘 날짜의 모든 페이지에서 뉴스 데이터 가져오기
    news_list = fetch_all_pages_news(date=today_date)
    
    if news_list:
        # 오늘 날짜의 모든 파일 확인하여 중복 체크
        pattern = os.path.join(data_dir, f"{today_date}_*.json")
        existing_files = sorted(glob.glob(pattern), reverse=True)
        
        # 가장 최근 파일과 중복 체크
        existing_data = None
        if existing_files:
            existing_data = load_existing_data(existing_files[0])
        
        # 중복 체크
        if existing_data and is_data_duplicate(news_list, existing_data):
            print(f"ℹ️ 기존 데이터와 동일합니다. 다시 로드하지 않습니다.")
            print(f"📊 기존 데이터: {len(existing_data.get('news', []))}개 뉴스")
            return
        
        # 새 파일명 생성 (날짜_번호 형식)
        filepath = generate_filename(data_dir, today_date)
        print(f"📝 파일명: {os.path.basename(filepath)}")
        
        # 데이터 저장
        if save_data_to_json(news_list, filepath):
            print(f"✅ {len(news_list)}개의 뉴스 데이터를 저장했습니다.")
        else:
            print(f"❌ 데이터 저장에 실패했습니다.")
    else:
        print("⚠️ 뉴스 데이터를 가져올 수 없습니다.")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
