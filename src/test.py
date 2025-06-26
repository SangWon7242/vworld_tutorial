import requests
import time
from dotenv import load_dotenv
import os
import json

# folium 임포트 시 오류 처리
try:
    import folium
    from folium import plugins
    FOLIUM_AVAILABLE = True
    print("✅ folium 라이브러리 사용 가능")
except ImportError:
    FOLIUM_AVAILABLE = False
    print("⚠️  folium 라이브러리가 없습니다. 지도 생성을 건너뜁니다.")

load_dotenv()

# API URL 설정
url = "https://api.vworld.kr/req/data"
params = {
    'service': 'data',
    'request': 'GetFeature', 
    'data': 'LT_C_AISPRHC',
    'key': os.getenv('VWORLD_API_KEY'),
    'domain': os.getenv('VWORLD_DOMAIN'),
    'geomFilter': 'BOX(126.734086,37.413294,127.269311,37.715133)',
    'crs': 'EPSG:4326',
    'format': 'json'
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def get_detailed_address(lat, lng):
    """좌표를 상세 주소로 변환"""
    
    try:
        geocode_url = "https://api.vworld.kr/req/address"
        geocode_params = {
            'service': 'address',
            'request': 'getAddress',
            'key': os.getenv('VWORLD_API_KEY'),
            'point': f"{lng},{lat}",
            'format': 'json',
            'type': 'both',
            'zipcode': 'true'
        }
        
        response = requests.get(geocode_url, params=geocode_params, timeout=10)
        
        if response.status_code == 200:
            addr_data = response.json()
            
            if ('response' in addr_data and 
                'result' in addr_data['response'] and 
                addr_data['response']['result']):
                
                result = addr_data['response']['result'][0]
                
                address_info = {
                    'full_address': result.get('text', ''),
                    'sido': result.get('structure', {}).get('level1', ''),
                    'sigungu': result.get('structure', {}).get('level2', ''),
                    'dong': result.get('structure', {}).get('level3', ''),
                    'ri': result.get('structure', {}).get('level4L', ''),
                    'road_name': result.get('structure', {}).get('level4LC', ''),
                    'building_number': result.get('structure', {}).get('detail', ''),
                    'zipcode': result.get('zipcode', '')
                }
                
                simple_address = f"{address_info['sido']} {address_info['sigungu']}"
                if address_info['dong']:
                    simple_address += f" {address_info['dong']}"
                
                address_info['simple_address'] = simple_address.strip()
                return address_info
        
        return {
            'full_address': f"위도: {lat:.6f}, 경도: {lng:.6f}",
            'simple_address': f"위도: {lat:.6f}, 경도: {lng:.6f}",
            'sido': '', 'sigungu': '', 'dong': '', 'ri': '', 'road_name': '', 'building_number': '', 'zipcode': ''
        }
    
    except Exception as e:
        print(f"주소 변환 오류: {e}")
        return {
            'full_address': f"위도: {lat:.6f}, 경도: {lng:.6f}",
            'simple_address': f"위도: {lat:.6f}, 경도: {lng:.6f}",
            'sido': '', 'sigungu': '', 'dong': '', 'ri': '', 'road_name': '', 'building_number': '', 'zipcode': ''
        }

def fetch_and_analyze_with_address():
    """주소 정보가 포함된 데이터 분석"""
    
    print("🔍 비행금지구역 데이터 조회 중...")
    
    # 데이터 가져오기
    data = None
    for attempt in range(3):
        try:
            print(f"   시도 {attempt + 1}/3...")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                print("   ✅ 데이터 조회 성공")
                break
            else:
                print(f"   ❌ HTTP 오류: {response.status_code}")
        except Exception as e:
            print(f"   ❌ 요청 오류: {e}")
            if attempt < 2:
                time.sleep(3)
    
    if not data:
        print("❌ 데이터 조회 실패")
        return None
    
    # 데이터 구조 확인
    if not ('response' in data and 'result' in data['response']):
        print("❌ 유효하지 않은 데이터 구조")
        print(f"데이터 키: {list(data.keys())}")
        return None
    
    result = data['response']['result']
    if 'featureCollection' not in result:
        print("❌ featureCollection이 없습니다")
        print(f"result 키: {list(result.keys())}")
        return None
    
    features = result['featureCollection']['features']
    print(f"🚁 총 {len(features)}개의 비행금지구역 발견")
    
    if len(features) == 0:
        print("⚠️  조회된 구역이 없습니다.")
        return []
    
    # 각 구역 분석
    zones_with_address = []
    
    for i, feature in enumerate(features, 1):
        print(f"\n📍 구역 {i}/{len(features)} 분석 중...")
        
        try:
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            
            zone_info = {
                'index': i,
                'name': props.get('fac_name', f'구역 {i}'),
                'restriction_type': props.get('rstr_type', '정보 없음'),
                'altitude_limit': props.get('alt_lmt', '정보 없음'),
                'description': props.get('rmk', '정보 없음'),
                'coordinates': None,
                'center_lat': None,
                'center_lng': None,
                'address_info': None,
                'properties': props  # 전체 속성 보존
            }
            
            # 좌표 정보 처리
            if 'coordinates' in geom and geom['coordinates']:
                coords = geom['coordinates']
                zone_info['coordinates'] = coords
                zone_info['geometry_type'] = geom.get('type', 'Unknown')
                
                # 중심점 계산
                center_lat, center_lng = calculate_center_point(coords, geom.get('type'))
                
                if center_lat and center_lng:
                    zone_info['center_lat'] = center_lat
                    zone_info['center_lng'] = center_lng
                    
                    print(f"   이름: {zone_info['name']}")
                    print(f"   좌표: 위도 {center_lat:.6f}, 경도 {center_lng:.6f}")
                    
                    # 주소 정보 가져오기
                    print(f"   주소 조회 중...")
                    address_info = get_detailed_address(center_lat, center_lng)
                    zone_info['address_info'] = address_info
                    
                    print(f"   위치: {address_info['simple_address']}")
                    print(f"   제한유형: {zone_info['restriction_type']}")
                    
                    # API 호출 간격 조절
                    time.sleep(0.3)
                else:
                    print(f"   ⚠️  좌표 계산 실패")
            else:
                print(f"   ⚠️  좌표 정보 없음")
            
            zones_with_address.append(zone_info)
            
        except Exception as e:
            print(f"   ❌ 구역 {i} 처리 오류: {e}")
            continue
        
        print("-" * 50)
    
    print(f"\n✅ 총 {len(zones_with_address)}개 구역 분석 완료")
    return zones_with_address

def calculate_center_point(coordinates, geom_type):
    """좌표 중심점 계산"""
    
    try:
        if geom_type == 'Polygon':
            if coordinates and len(coordinates) > 0:
                coords = coordinates[0]  # 외부 링
                if len(coords) > 0:
                    center_lng = sum(coord[0] for coord in coords) / len(coords)
                    center_lat = sum(coord[1] for coord in coords) / len(coords)
                    return center_lat, center_lng
        elif geom_type == 'Point':
            if len(coordinates) >= 2:
                return coordinates[1], coordinates[0]  # lat, lng
        elif geom_type == 'MultiPolygon':
            if coordinates and len(coordinates) > 0:
                # 첫 번째 폴리곤의 외부 링 사용
                coords = coordinates[0][0]
                center_lng = sum(coord[0] for coord in coords) / len(coords)
                center_lat = sum(coord[1] for coord in coords) / len(coords)
                return center_lat, center_lng
        
        return None, None
    
    except Exception as e:
        print(f"중심점 계산 오류: {e}")
        return None, None

def create_detailed_map(zones):
    """상세 주소 정보가 포함된 지도 생성"""
    
    if not FOLIUM_AVAILABLE:
        print("⚠️  folium이 설치되지 않아 지도를 생성할 수 없습니다.")
        print("설치 명령어: pip install folium")
        return None
    
    if not zones:
        print("❌ 표시할 구역이 없습니다.")
        return None
    
    # 유효한 좌표가 있는 구역만 필터링
    valid_zones = [z for z in zones if z['center_lat'] and z['center_lng']]
    
    if not valid_zones:
        print("❌ 유효한 좌표가 있는 구역이 없습니다.")
        return None
    
    print(f"🗺️  {len(valid_zones)}개 구역으로 지도 생성 중...")
    
    try:
        # 지도 중심점 계산
        center_lat = sum(z['center_lat'] for z in valid_zones) / len(valid_zones)
        center_lng = sum(z['center_lng'] for z in valid_zones) / len(valid_zones)
        
        print(f"   지도 중심: 위도 {center_lat:.6f}, 경도 {center_lng:.6f}")
        
        # 지도 생성
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=11,
            tiles='OpenStreetMap'
        )
        
        # 색상 리스트
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen']
        
        # 각 구역을 지도에 표시
        for zone in valid_zones:
            try:
                color = colors[(zone['index'] - 1) % len(colors)]
                address_info = zone['address_info'] or {}
                
                # 팝업 내용 생성
                popup_html = f"""
                <div style="width: 300px; font-family: Arial, sans-serif;">
                    <h4 style="margin-bottom: 10px; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 5px;">
                        🚁 {zone['name']}
                    </h4>
                    
                    <div style="margin-bottom: 8px;">
                        <strong>📍 위치:</strong><br>
                        <span style="color: #d63031; font-weight: bold;">
                            {address_info.get('simple_address', '위치 정보 없음')}
                        </span>
                    </div>
                    
                    <div style="margin-bottom: 8px;">
                        <strong>🏠 상세주소:</strong><br>
                        <span style="font-size: 12px;">
                            {address_info.get('full_address', '상세 주소 없음')}
                        </span>
                    </div>
                    
                    <div style="margin-bottom: 8px;">
                        <strong>🚫 제한유형:</strong> {zone['restriction_type']}
                    </div>
                    
                    <div style="margin-bottom: 8px;">
                        <strong>📏 고도제한:</strong> {zone['altitude_limit']}
                    </div>
                    
                    <div style="margin-bottom: 8px;">
                        <strong>📝 설명:</strong><br>
                        <span style="font-size: 11px;">
                            {zone['description'][:100]}{'...' if len(zone['description']) > 100 else ''}
                        </span>
                    </div>
                    
                    <div style="margin-top: 10px; font-size: 10px; color: #666; border-top: 1px solid #eee; padding-top: 5px;">
                        좌표: {zone['center_lat']:.6f}, {zone['center_lng']:.6f}
                    </div>
                </div>
                """
                
                # 마커 추가
                folium.Marker(
                    location=[zone['center_lat'], zone['center_lng']],
                    popup=folium.Popup(popup_html, max_width=320),
                    tooltip=f"{zone['name']} - {address_info.get('simple_address', '위치 정보 없음')}",
                    icon=folium.Icon(color=color, icon='ban')
                ).add_to(m)
                
                # 구역 경계 표시
                if zone['coordinates'] and zone.get('geometry_type') == 'Polygon':
                    coords = zone['coordinates'][0]  # 외부 링
                    folium_coords = [[coord[1], coord[0]] for coord in coords]
                    
                    folium.Polygon(
                        locations=folium_coords,
                        color=color,
                        weight=2,
                        opacity=0.8,
                        fillColor=color,
                        fillOpacity=0.2,
                        popup=f"{zone['name']} - {address_info.get('simple_address', '')}"
                    ).add_to(m)
                
                print(f"   ✅ {zone['name']} 마커 추가 완료")
                
            except Exception as e:
                print(f"   ❌ {zone['name']} 마커 추가 실패: {e}")
                continue
        
        # 범례 추가
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 200px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        <h4 style="margin-top: 0;">🚁 비행금지구역</h4>
        <p style="margin: 5px 0;"><span style="color:red;">●</span> 비행금지구역 마커</p>
        <p style="margin: 5px 0; font-size: 12px;">클릭하면 상세 정보 확인</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # 지도 저장
        map_filename = 'result_data/flight_restriction_zones_detailed.html'
        
        # 디렉토리 존재 여부 확인 및 생성
        os.makedirs(os.path.dirname(map_filename), exist_ok=True)
        
        m.save(map_filename)
        print(f"✅ 상세 지도가 '{map_filename}' 파일로 저장되었습니다.")
        
        # 파일 생성 확인
        if os.path.exists(map_filename):
            file_size = os.path.getsize(map_filename)
            print(f"   파일 크기: {file_size:,} bytes")
        else:
            print("❌ 파일 저장 실패")
        
        return m
        
    except Exception as e:
        print(f"❌ 지도 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_detailed_data(zones):
    """상세 데이터를 JSON 파일로 저장"""
    
    try:
        # 요약 정보 생성
        summary = {
            'total_zones': len(zones),
            'zones_by_district': {},
            'zones_detail': zones,
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 구별 통계
        for zone in zones:
            if zone.get('address_info') and zone['address_info'].get('sigungu'):
                district = zone['address_info']['sigungu']
                if district not in summary['zones_by_district']:
                    summary['zones_by_district'][district] = []
                summary['zones_by_district'][district].append({
                    'name': zone['name'],
                    'location': zone['address_info'].get('simple_address', '위치 정보 없음')
                })
        
        # JSON 저장
        filename = 'result_data/flight_zones_with_address.json'
        
        # 디렉토리 존재 여부 확인 및 생성
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 상세 데이터가 '{filename}' 파일로 저장되었습니다.")
        
        # 파일 크기 확인
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"   파일 크기: {file_size:,} bytes")
        
        # 구별 요약 출력
        if summary['zones_by_district']:
            print(f"\n📊 구별 비행금지구역 분포:")
            for district, zone_list in summary['zones_by_district'].items():
                print(f"   {district}: {len(zone_list)}개 구역")
                for zone in zone_list[:3]:  # 최대 3개만 표시
                    print(f"     - {zone['name']} ({zone['location']})")
                if len(zone_list) > 3:
                    print(f"     ... 외 {len(zone_list) - 3}개")
        
        return summary
        
    except Exception as e:
        print(f"❌ 데이터 저장 오류: {e}")
        return None

def main():
    """메인 실행 함수"""
    
    print("🚀 비행금지구역 분석 시작")
    print("=" * 60)
    
    # 환경 변수 확인
    api_key = os.getenv('VWORLD_API_KEY')
    domain = os.getenv('VWORLD_DOMAIN')
    
    if not api_key:
        print("❌ VWORLD_API_KEY가 설정되지 않았습니다.")
        return
    if not domain:
        print("❌ VWORLD_DOMAIN이 설정되지 않았습니다.")
        return
    
    print(f"✅ API 키: {api_key[:10]}...")
    print(f"✅ 도메인: {domain}")
    
    # 1. 데이터 분석
    zones = fetch_and_analyze_with_address()
    
    if not zones:
        print("❌ 분석할 데이터가 없습니다.")
        return
    
    # 2. 데이터 저장
    print(f"\n💾 데이터 저장 중...")
    save_detailed_data(zones)
    
    # 3. 지도 생성
    print(f"\n🗺️  지도 생성 중...")
    create_detailed_map(zones)
    
    print("\n🎉 모든 작업이 완료되었습니다!")
    print("생성된 파일:")
    
    files_to_check = [
        'result_data/flight_restriction_zones_detailed.html',
        'result_data/flight_zones_with_address.json'
    ]
    
    for filename in files_to_check:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"   ✅ {filename} ({size:,} bytes)")
        else:
            print(f"   ❌ {filename} (생성 실패)")

if __name__ == "__main__":
    main()
