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
from openai import OpenAI
from supabase import create_client, Client
from dotenv import load_dotenv

URL = "https://finance.naver.com/news/mainnews.naver"

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Supabase 클라이언트 초기화
supabase_client: Client = None
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if supabase_url and supabase_key:
    try:
        supabase_client = create_client(supabase_url, supabase_key)
        print(f"✅ Supabase 클라이언트 초기화 완료: {supabase_url[:30]}...")
    except Exception as e:
        print(f"⚠️ Supabase 클라이언트 초기화 실패: {e}")
else:
    if not supabase_url:
        print("⚠️ SUPABASE_URL 환경 변수가 설정되지 않았습니다.")
    if not supabase_key:
        print("⚠️ SUPABASE_KEY 환경 변수가 설정되지 않았습니다.")

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

# 5일 이상 지난 파일 삭제 (뉴스 파일만)
def delete_old_files(data_dir, days=5):
    """지정된 일수 이상 지난 뉴스 파일만 삭제 (다른 workflow의 파일은 보호)"""
    try:
        if not os.path.exists(data_dir):
            return
        
        # 현재 날짜
        today = datetime.now()
        today_str = today.strftime('%Y-%m-%d')
        cutoff_date = today - timedelta(days=days)
        
        # 뉴스 파일 패턴만 확인 (YYYY-MM-DD_NN.json 형식)
        pattern = os.path.join(data_dir, "????-??-??_??.json")
        files = glob.glob(pattern)
        
        deleted_count = 0
        for filepath in files:
            try:
                filename = os.path.basename(filepath)
                
                # 파일명 형식 확인 (YYYY-MM-DD_NN.json)
                if not filename.count('_') == 1:
                    continue
                
                parts = filename.replace('.json', '').split('_')
                if len(parts) != 2:
                    continue
                
                date_str = parts[0]
                num_str = parts[1]
                
                # 날짜 형식 확인
                if not num_str.isdigit():
                    continue
                
                # 오늘 날짜의 파일은 삭제하지 않음
                if date_str == today_str:
                    continue
                
                # 날짜 파싱
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                # 5일 이상 지난 파일만 삭제
                if file_date < cutoff_date:
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"🗑️ 오래된 뉴스 파일 삭제: {filename}")
            except (ValueError, IndexError) as e:
                # 날짜 파싱 실패 또는 형식 오류 시 스킵 (다른 workflow의 파일일 수 있음)
                continue
            except Exception as e:
                # 기타 오류 시 스킵
                continue
        
        if deleted_count > 0:
            print(f"✅ 총 {deleted_count}개의 오래된 뉴스 파일을 삭제했습니다.")
        else:
            print(f"ℹ️ 삭제할 오래된 뉴스 파일이 없습니다.")
            
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

# 캐시를 위한 전역 변수
_summary_and_stocks_cache = {}

# OpenAI를 사용한 뉴스 제목들 요약 및 추천 종목 추출 (하나의 API 요청)
def get_summary_and_stocks_with_openai(titles: list) -> tuple[str, str]:
    """OpenAI를 사용하여 뉴스 제목들을 요약하고 추천 종목 10개를 추출 (하나의 API 요청, 캐싱 적용)"""
    if not openai_client:
        print("⚠️ OpenAI API 키가 설정되지 않았습니다.")
        # 제목들을 간단히 결합 (500자 제한)
        combined = " | ".join(titles)
        summary = combined[:500] if len(combined) > 500 else combined
        return summary, ""
    
    if not titles:
        return "", ""
    
    # 캐시 키 생성 (제목들의 해시값)
    cache_key = hashlib.md5("|".join(titles[:10]).encode('utf-8')).hexdigest()
    
    # 캐시에 있으면 반환
    if cache_key in _summary_and_stocks_cache:
        print("📋 캐시에서 요약 및 추천 종목 데이터를 가져옵니다.")
        cached_result = _summary_and_stocks_cache[cache_key]
        return cached_result["summary"], cached_result["topstock"]
    
    try:
        # 모든 제목을 하나의 문자열로 결합
        titles_text = "\n".join([f"- {title}" for title in titles[:50]])  # 최대 50개까지만
        if len(titles) > 50:
            titles_text += f"\n... 외 {len(titles) - 50}개 뉴스"
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 뉴스 분석 및 주식 투자 전문가입니다. 주어진 뉴스 제목들을 분석하여 다음 두 가지를 수행해주세요:\n1. 뉴스 제목들을 종합하여 500자 이내로 요약\n2. 뉴스 내용을 바탕으로 투자 가치가 높은 한국 주식 종목 10개를 추천\n\n응답 형식:\n[요약]\n(여기에 500자 이내 요약)\n\n[추천종목]\n종목1, 종목2, 종목3, 종목4, 종목5, 종목6, 종목7, 종목8, 종목9, 종목10"
                },
                {
                    "role": "user",
                    "content": f"다음 뉴스 제목들을 분석해주세요:\n\n{titles_text}\n\n위 뉴스들을 바탕으로:\n1. 500자 이내로 요약\n2. 투자 가치가 높은 한국 주식 종목 10개 추천 (종목명 또는 종목코드 6자리, 쉼표로 구분)\n\n[요약]과 [추천종목] 형식으로 답변해주세요."
                }
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # 결과 파싱
        summary = ""
        topstock = ""
        
        # [요약] 섹션 추출
        if "[요약]" in result_text:
            summary_part = result_text.split("[요약]")[1]
            if "[추천종목]" in summary_part:
                summary = summary_part.split("[추천종목]")[0].strip()
            else:
                summary = summary_part.strip()
        else:
            # [요약] 태그가 없으면 첫 부분을 요약으로 간주
            if "[추천종목]" in result_text:
                summary = result_text.split("[추천종목]")[0].strip()
            else:
                summary = result_text[:500]
        
        # [추천종목] 섹션 추출
        if "[추천종목]" in result_text:
            topstock_part = result_text.split("[추천종목]")[1].strip()
            # 첫 줄만 가져오기 (추가 설명 제거)
            topstock = topstock_part.split("\n")[0].strip()
        else:
            # [추천종목] 태그가 없으면 마지막 부분을 추천 종목으로 간주
            lines = result_text.split("\n")
            for line in reversed(lines):
                if "," in line and len(line.strip()) > 10:
                    topstock = line.strip()
                    break
        
        # 500자 제한
        if len(summary) > 500:
            summary = summary[:500]
        
        # 255자 제한 (VARCHAR(255))
        if len(topstock) > 255:
            topstock = topstock[:255]
        
        # 캐시에 저장
        _summary_and_stocks_cache[cache_key] = {
            "summary": summary,
            "topstock": topstock
        }
        print("💾 요약 및 추천 종목 데이터를 캐시에 저장했습니다.")
        
        return summary, topstock
        
    except Exception as e:
        print(f"⚠️ OpenAI 요약 및 추천 종목 추출 실패: {e}")
        import traceback
        traceback.print_exc()
        
        # 실패 시 기본값 반환
        combined = " | ".join(titles[:10])  # 최대 10개만
        if len(titles) > 10:
            combined += f" ... 외 {len(titles) - 10}개"
        summary = combined[:500] if len(combined) > 500 else combined
        topstock = ""
        
        # 실패한 결과도 캐시에 저장 (재시도 방지)
        _summary_and_stocks_cache[cache_key] = {
            "summary": summary,
            "topstock": topstock
        }
        
        return summary, topstock

# Supabase에 뉴스 데이터 저장
def save_news_to_supabase(news_list: list, filename_without_ext: str) -> bool:
    """뉴스 데이터를 Supabase daily_new 테이블에 저장 (1개의 레코드로 저장)"""
    if not supabase_client:
        print("⚠️ Supabase 연결 정보가 설정되지 않았습니다.")
        return False
    
    if not news_list:
        print("⚠️ 저장할 뉴스 데이터가 없습니다.")
        return False
    
    try:
        print(f"\n💾 Supabase에 {len(news_list)}개의 뉴스 데이터를 1개 레코드로 저장 중...")
        
        # 모든 뉴스 제목 추출
        titles = [news.get("제목", "") for news in news_list if news.get("제목")]
        
        if not titles:
            print("⚠️ 제목이 있는 뉴스가 없습니다.")
            return False
        
        print(f"📝 총 {len(titles)}개의 뉴스 제목을 분석 중... (요약 + 추천 종목)")
        
        # OpenAI로 모든 제목들을 종합하여 요약 및 추천 종목 추출 (하나의 API 요청)
        summary, topstock = get_summary_and_stocks_with_openai(titles)
        
        print(f"✅ 요약 완료: {len(summary)}자")
        if topstock:
            print(f"✅ 추천 종목 추출 완료: {topstock}")
        else:
            print(f"⚠️ 추천 종목 추출 실패")
        
        # 저장할 데이터 준비
        insert_data = {
            "content": news_list,  # 전체 뉴스 리스트를 JSONB로 저장
            "summary": summary,  # 모든 제목을 요약한 결과 (500자)
            "cont_date": filename_without_ext,  # JSON 파일명 (예: "2026-01-28_01")
            "topstock": topstock  # 추천 종목 10개
        }
        
        print(f"📤 저장 데이터 준비 완료:")
        print(f"   - content: {len(news_list)}개 뉴스")
        print(f"   - summary: {len(summary)}자")
        print(f"   - cont_date: {filename_without_ext}")
        print(f"   - topstock: {topstock}")
        
        # Supabase에 데이터 삽입 (1개의 레코드)
        result = supabase_client.table("daily_new").insert(insert_data).execute()
        
        # 결과 확인
        if result.data:
            print(f"✅ Supabase 저장 완료: 1개 레코드 저장 성공")
            print(f"   저장된 ID: {result.data[0].get('id', 'N/A')}")
            return True
        else:
            print(f"⚠️ Supabase 저장 결과가 비어있습니다.")
            return False
        
    except Exception as e:
        print(f"❌ Supabase 저장 중 오류 발생: {e}")
        print(f"   오류 타입: {type(e).__name__}")
        import traceback
        print("\n상세 오류 정보:")
        traceback.print_exc()
        return False

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
        # 새 파일명 생성 (날짜_번호 형식)
        filepath = generate_filename(data_dir, today_date)
        filename_without_ext = os.path.basename(filepath).replace('.json', '')  # 확장자 제거
        print(f"📝 파일명: {os.path.basename(filepath)}")
        
        # JSON 파일로 데이터 저장
        if save_data_to_json(news_list, filepath):
            print(f"✅ {len(news_list)}개의 뉴스 데이터를 JSON 파일로 저장했습니다.")
        else:
            print(f"❌ JSON 파일 저장에 실패했습니다.")
        
        # Supabase에 데이터 저장 (파일명 형식으로 저장: 예: "2026-01-28_01")
        if save_news_to_supabase(news_list, filename_without_ext):
            print(f"✅ {len(news_list)}개의 뉴스 데이터를 Supabase에 저장했습니다.")
        else:
            print(f"⚠️ Supabase 저장을 건너뜁니다.")
    else:
        print("⚠️ 뉴스 데이터를 가져올 수 없습니다.")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
