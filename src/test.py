import requests
import time
from dotenv import load_dotenv
import os

load_dotenv()

# API URL 설정
url = "https://api.vworld.kr/req/data"

# 파라미터 설정
params = {
    'service': 'data',
    'request': 'GetFeature', 
    'data': 'LT_C_AISPRHC',
    'key': os.getenv('VWORLD_API_KEY'),
    'domain': os.getenv('VWORLD_DOMAIN'),
    'geomFilter': 'BOX(126.734086,37.715133,127.269311,37.413294)',
    'crs': 'EPSG:4326',
    'format': 'json'
}

# 헤더 설정
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 요청 함수
def fetch_data():
    for _ in range(3):  # 최대 3번 재시도
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)  # 10초 타임아웃
            if response.status_code == 200:
                return response.json()
            else:
                print(f"요청 실패: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"요청 실패: {e}")
            time.sleep(5)  # 5초 대기 후 재시도
    return None

# 데이터 가져오기
data = fetch_data()
if data:
    print(data)
else:
    print("데이터 조회 실패")
