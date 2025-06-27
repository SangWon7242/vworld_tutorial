import requests
import time
from dotenv import load_dotenv
import os
import json

try:
    import folium
    from folium import plugins
    FOLIUM_AVAILABLE = True
    print("✅ folium 라이브러리 사용 가능")
except ImportError:
    FOLIUM_AVAILABLE = False
    print("⚠️  folium 라이브러리가 없습니다.")

load_dotenv()

# API URL 설정
url = "https://api.vworld.kr/req/data"
base_params = {
    'service': 'data',
    'request': 'GetFeature', 
    'data': 'LT_C_AISPRHC',  # 비행금지구역 데이터
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

def classify_restriction_type(props):
    """속성 정보를 기반으로 제한 구역 분류"""
    
    # 속성에서 제한 유형 정보 추출
    prh_typ = props.get('prh_typ', '')
    prh_lbl_1 = props.get('prh_lbl_1', '')
    prh_lbl_2 = props.get('prh_lbl_2', '')
    prh_lbl_3 = props.get('prh_lbl_3', '')
    prh_lbl_4 = props.get('prh_lbl_4', '')
    prohibited = props.get('prohibited', '')
    
    # VWorld API 파라미터에 따른 구역 유형 분류
    zone_type = props.get('type', '')  # API에서 제공하는 구역 유형
    
    # 제한 구역 분류
    restriction_info = {
        'type': '비행금지구역',  # 기본값
        'severity': 'high',     # 위험도: high, medium, low
        'color': '#d32f2f',     # 표시 색상 (빨간색)
        'icon': '🚫',          # 아이콘
        'labels': [],          # 라벨 정보
        'reason': '국가 안보 및 안전상의 이유로 비행이 금지된 구역입니다. 허가 없이 비행할 경우 법적 처벌을 받을 수 있습니다.',  # 기본 이유
        'border': '2px solid #d32f2f'  # 테두리 스타일
    }
    
    # 라벨 정보 수집
    labels = []
    if prh_lbl_1: labels.append(prh_lbl_1)
    if prh_lbl_2: labels.append(prh_lbl_2)
    if prh_lbl_3: labels.append(prh_lbl_3)
    if prh_lbl_4: labels.append(prh_lbl_4)
    
    restriction_info['labels'] = labels
    
    # VWorld API 파라미터 기반 구역 유형 분류
    if 'UA)초경량비행장치공역' in zone_type or 'UA)' in prh_lbl_1:
        restriction_info.update({
            'type': 'UA)초경량비행장치공역',
            'severity': 'medium',
            'color': '#ffcdd2',
            'icon': '🛩️',
            'reason': '초경량 비행장치(드론 등)의 비행이 제한되는 특별 공역입니다. 비행 전 관련 규정을 확인하세요.',
            'border': '2px solid #d32f2f'
        })
    elif '관제권' in zone_type or '관제' in prh_lbl_1 or '관제' in prh_typ:
        restriction_info.update({
            'type': '관제권',
            'severity': 'medium',
            'color': '#bbdefb',
            'icon': '🗼',
            'reason': '공항 주변 항공기 이착륙 안전을 위한 관제 구역입니다. 관제탑의 허가 없이 비행할 수 없습니다.',
            'border': '2px solid #1976d2'
        })
    elif '경계구역' in zone_type or '경계' in prh_lbl_1 or '경계' in prh_typ:
        restriction_info.update({
            'type': '경계구역',
            'severity': 'low',
            'color': '#e1f5fe',
            'icon': '🔍',
            'reason': '특별한 주의가 필요한 경계 구역입니다. 비행 시 주변 환경에 주의하세요.',
            'border': '2px dashed #0288d1'
        })
    elif '비행금지구역' in zone_type or '금지' in prohibited or '금지' in prh_lbl_1 or '금지' in prh_typ:
        restriction_info.update({
            'type': '비행금지구역',
            'severity': 'high',
            'color': '#ff0000',  # 더 눈에 띄는 빨간색으로 변경
            'icon': '🚫',
            'reason': '국가 안보 및 안전상의 이유로 비행이 금지된 구역입니다. 허가 없이 비행할 경우 법적 처벌을 받을 수 있습니다.',
            'border': '2px solid #d32f2f'
        })
    elif '비행제한구역' in zone_type or '제한' in prohibited or '제한' in prh_lbl_4 or '제한' in prh_typ:
        restriction_info.update({
            'type': '비행제한구역',
            'severity': 'medium',
            'color': '#ffe0b2',
            'icon': '⚠️',
            'reason': '특정 조건(고도, 시간, 허가 등)에 따라 비행이 제한되는 구역입니다. 사전 허가를 받으면 비행이 가능할 수 있습니다.',
            'border': '2px solid #e65100'
        })
    elif '비행장교통구역' in zone_type or '교통' in prh_lbl_1 or '교통' in prh_typ:
        restriction_info.update({
            'type': '비행장교통구역',
            'severity': 'medium',
            'color': '#e8f5e9',
            'icon': '✈️',
            'reason': '비행장 주변 항공기 이착륙 안전을 위한 교통 구역입니다. 비행 시 특별한 주의가 필요합니다.',
            'border': '2px dashed #388e3c'
        })
    elif '경량항공기 이착륙장' in zone_type or '경량' in prh_lbl_1 or '경량' in prh_typ:
        restriction_info.update({
            'type': '경량항공기 이착륙장',
            'severity': 'medium',
            'color': '#f3e5f5',
            'icon': '🛬',
            'reason': '경량항공기의 이착륙이 이루어지는 구역입니다. 비행 시 주의가 필요합니다.',
            'border': '2px dashed #8e24aa'
        })
    elif '위험지역' in zone_type or '위험' in prh_lbl_1 or '위험' in prh_typ:
        restriction_info.update({
            'type': '위험지역',
            'severity': 'high',
            'color': '#ffecb3',
            'icon': '⚡',
            'reason': '비행 시 위험 요소가 있는 구역입니다. 특별한 주의가 필요합니다.',
            'border': '2px solid #ffa000'
        })
    elif '장애물공역' in zone_type or '장애물' in prh_lbl_1 or '장애물' in prh_typ:
        restriction_info.update({
            'type': '장애물공역',
            'severity': 'medium',
            'color': '#e0f2f1',
            'icon': '🏔️',
            'reason': '고층 건물, 송전탑 등 장애물이 있는 공역입니다. 비행 시 충돌 위험에 주의하세요.',
            'border': '2px dashed #00796b'
        })
    elif '사전협의구역' in zone_type or '협의' in prh_lbl_1 or '협의' in prh_typ:
        restriction_info.update({
            'type': '사전협의구역',
            'severity': 'low',
            'color': '#f8bbd0',
            'icon': '📝',
            'reason': '비행 전 관련 기관과의 사전 협의가 필요한 구역입니다. 비행 계획 전 해당 기관에 문의하세요.',
            'border': '2px dashed #c2185b'
        })
    elif '임시비행금지구역' in zone_type or '임시' in prh_lbl_1 or '임시' in prh_typ:
        restriction_info.update({
            'type': '임시비행금지구역',
            'severity': 'high',
            'color': '#ffcdd2',
            'icon': '⏱️',
            'reason': '특정 기간 동안 비행이 금지된 임시 구역입니다. 공지된 기간을 확인하고 비행을 삼가하세요.',
            'border': '2px solid #d32f2f'
        })
    elif '국립자연공원' in zone_type or '공원' in prh_lbl_1 or '공원' in prh_typ:
        restriction_info.update({
            'type': '국립자연공원',
            'severity': 'low',
            'color': '#c8e6c9',
            'icon': '🌳',
            'reason': '자연환경 보호를 위해 비행이 제한될 수 있는 국립공원 구역입니다. 비행 전 공원 관리사무소에 문의하세요.',
            'border': '2px solid #388e3c'
        })
    elif 'GND' in prh_lbl_3 or 'GND' in prh_typ:  # Ground
        restriction_info.update({
            'type': '지상제한구역',
            'severity': 'high',
            'color': '#c2185b',
            'icon': '🚫',
            'reason': '지상부터 특정 고도까지 비행이 제한된 구역입니다. 군사시설, 주요 인프라 보호 등의 이유로 설정되었습니다.',
            'border': '2px solid #c2185b'
        })
    elif 'P61A' in prh_lbl_1 or 'P61A' in prh_typ:  # 특정 코드
        restriction_info.update({
            'type': '특별관리구역',
            'severity': 'high',
            'color': '#7b1fa2',
            'icon': '🔒',
            'reason': '특별한 관리가 필요한 구역으로, 비행 전 관련 기관의 허가가 필요합니다.',
            'border': '2px solid #7b1fa2'
        })
    elif 'UNL' in prh_lbl_2 or 'UNL' in prh_typ:  # Unlimited - 이 조건을 마지막에 체크
        restriction_info.update({
            'type': '고도제한없음',
            'severity': 'low',
            'color': '#2e7d32',
            'icon': '📌',
            'reason': '고도 제한이 없는 구역이지만, 다른 비행 규정은 준수해야 합니다. 주변 환경과 기상 조건을 고려하여 안전하게 비행하세요.',
            'border': '2px solid #2e7d32'
        })
    
    return restriction_info

def fetch_flight_restriction_data():
    """비행 제한 구역 데이터 조회 및 분석"""
    
    print("🔍 비행 제한 구역 데이터 조회 중...")
    
    # 데이터 가져오기
    data = None
    for attempt in range(3):
        try:
            print(f"   시도 {attempt + 1}/3...")
            response = requests.get(url, params=base_params, headers=headers, timeout=15)
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
        return None
    
    result = data['response']['result']
    if 'featureCollection' not in result:
        print("❌ featureCollection이 없습니다")
        return None
    
    features = result['featureCollection']['features']
    print(f"🚁 총 {len(features)}개의 비행 제한 구역 발견")
    
    if len(features) == 0:
        print("⚠️  조회된 구역이 없습니다.")
        return []
    
    # 각 구역 분석
    zones_with_classification = []
    
    for i, feature in enumerate(features, 1):
        print(f"\n📍 구역 {i}/{len(features)} 분석 중...")
        
        try:
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            
            # 제한 구역 분류
            restriction_info = classify_restriction_type(props)
            
            zone_info = {
                'index': i,
                'name': props.get('fac_name', f'구역 {i}'),
                'restriction_info': restriction_info,
                'altitude_limit': props.get('alt_lmt', '정보 없음'),
                'description': props.get('rmk', '정보 없음'),
                'coordinates': None,
                'center_lat': None,
                'center_lng': None,
                'address_info': None,
                'properties': props,
                'labels': restriction_info['labels']
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
                    print(f"   유형: {restriction_info['type']} ({restriction_info['severity']})")
                    print(f"   라벨: {', '.join(restriction_info['labels'])}")
                    print(f"   좌표: 위도 {center_lat:.6f}, 경도 {center_lng:.6f}")
                    
                    # 주소 정보 가져오기
                    print(f"   주소 조회 중...")
                    address_info = get_detailed_address(center_lat, center_lng)
                    zone_info['address_info'] = address_info
                    
                    print(f"   위치: {address_info['simple_address']}")
                    
                    # API 호출 간격 조절
                    time.sleep(0.3)
                else:
                    print(f"   ⚠️  좌표 계산 실패")
            else:
                print(f"   ⚠️  좌표 정보 없음")
            
            zones_with_classification.append(zone_info)
            
        except Exception as e:
            print(f"   ❌ 구역 {i} 처리 오류: {e}")
            continue
        
        print("-" * 50)
    
    print(f"\n✅ 총 {len(zones_with_classification)}개 구역 분석 완료")
    
    # 구역 유형별 통계
    type_stats = {}
    for zone in zones_with_classification:
        zone_type = zone['restriction_info']['type']
        if zone_type not in type_stats:
            type_stats[zone_type] = 0
        type_stats[zone_type] += 1
    
    print(f"\n📊 구역 유형별 통계:")
    for zone_type, count in type_stats.items():
        print(f"   {zone_type}: {count}개")
    
    return zones_with_classification

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
                coords = coordinates[0][0]
                center_lng = sum(coord[0] for coord in coords) / len(coords)
                center_lat = sum(coord[1] for coord in coords) / len(coords)
                return center_lat, center_lng
        
        return None, None
    
    except Exception as e:
        print(f"중심점 계산 오류: {e}")
        return None, None

def create_classified_vworld_map(geojson_data, output_filename='classified_flight_restriction_zones.html'):
    """VWorld 데이터를 기반으로 분류된 비행 제한 구역 지도 생성 (범례 클릭 문제 해결)"""
    
    try:
        print("🗺️ 분류된 VWorld 비행 제한 구역 지도 생성 중...")
        
        # 지도 중심점 설정 (서울)
        center_lat, center_lon = 37.5665, 126.9780
        
        # 지도 생성
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=10,
            tiles=None
        )
        
        # 다양한 타일 레이어 추가
        folium.TileLayer('OpenStreetMap', name='기본 지도').add_to(m)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='위성 지도'
        ).add_to(m)
        
        # 유효한 구역 데이터 필터링
        valid_zones = []
        if 'features' in geojson_data:
            for feature in geojson_data['features']:
                if (feature.get('geometry') and 
                    feature.get('properties') and 
                    feature['properties'].get('ZONE_TYPE')):
                    valid_zones.append(feature)
        
        print(f"📍 처리할 구역 수: {len(valid_zones)}개")
        
        # 구역 유형별 분류 및 카운트
        type_counts = {}
        zone_groups = {}
        
        for feature in valid_zones:
            zone_type = feature['properties']['ZONE_TYPE']
            if zone_type not in type_counts:
                type_counts[zone_type] = 0
                zone_groups[zone_type] = []
            type_counts[zone_type] += 1
            zone_groups[zone_type].append(feature)
        
        # 색상 및 스타일 정의
        zone_styles = {
            'P-73A': {'color': '#e74c3c', 'icon': '🚁', 'severity': 'high', 'border': '3px solid #c0392b'},
            'P-73B': {'color': '#3498db', 'icon': '✈️', 'severity': 'medium', 'border': '3px solid #2980b9'},
            'R-75': {'color': '#f39c12', 'icon': '⚠️', 'severity': 'medium', 'border': '3px solid #e67e22'},
            'CTR': {'color': '#9b59b6', 'icon': '🏢', 'severity': 'high', 'border': '3px solid #8e44ad'},
            'TMA': {'color': '#1abc9c', 'icon': '📡', 'severity': 'medium', 'border': '3px solid #16a085'},
            'MOA': {'color': '#34495e', 'icon': '🎯', 'severity': 'high', 'border': '3px solid #2c3e50'},
            'ADIZ': {'color': '#e67e22', 'icon': '🛡️', 'severity': 'high', 'border': '3px solid #d35400'},
            'RESTRICTED': {'color': '#c0392b', 'icon': '🚫', 'severity': 'high', 'border': '3px solid #a93226'}
        }
        
        # 기본 스타일 (정의되지 않은 구역 유형용)
        default_style = {'color': '#95a5a6', 'icon': '📍', 'severity': 'low', 'border': '2px solid #7f8c8d'}
        
        # 구역별 레이어 그룹 생성
        layer_groups = {}
        for zone_type, features in zone_groups.items():
            layer_group = folium.FeatureGroup(name=f"{zone_type} ({len(features)}개)")
            
            style = zone_styles.get(zone_type, default_style)
            
            for feature in features:
                # 팝업 내용 생성
                props = feature['properties']
                popup_content = f"""
                <div style="width: 300px; font-family: 'Malgun Gothic', Arial, sans-serif; line-height: 1.4;">
                    <div style="background: linear-gradient(135deg, {style['color']} 0%, #2c3e50 100%); 
                                color: white; padding: 12px; margin: -10px -10px 12px -10px; border-radius: 8px 8px 0 0;">
                        <h4 style="margin: 0; font-size: 16px; display: flex; align-items: center;">
                            <span style="font-size: 20px; margin-right: 8px;">{style['icon']}</span>
                            {zone_type}
                        </h4>
                        <div style="font-size: 12px; opacity: 0.9; margin-top: 4px;">
                            비행 제한 구역 | 위험도: <span style="font-weight: bold;">{style['severity'].upper()}</span>
                        </div>
                    </div>
                    
                    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                        <strong>📍 구역 정보</strong>
                        <div style="font-size: 13px; margin-top: 4px; color: #495057;">
                            구역명: {props.get('ZONE_NAME', 'N/A')}<br>
                            고도: {props.get('ALTITUDE', 'N/A')}<br>
                            운영시간: {props.get('OPERATION_TIME', 'N/A')}
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 10px; background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid {style['color']};">
                        <strong>⚠️ 제한 사항</strong>
                        <div style="font-size: 13px; margin-top: 4px; color: #333;">
                            {props.get('RESTRICTION', '해당 구역에서의 비행이 제한됩니다.')}
                        </div>
                    </div>
                    
                    <div style="font-size: 11px; color: #6c757d; text-align: right; margin-top: 8px; border-top: 1px solid #dee2e6; padding-top: 8px;">
                        VWorld 데이터 기반
                    </div>
                </div>
                """
                
                # GeoJSON을 지도에 추가
                folium.GeoJson(
                    feature,
                    style_function=lambda x, color=style['color']: {
                        'fillColor': color,
                        'color': color,
                        'weight': 3,
                        'fillOpacity': 0.3,
                        'opacity': 0.8
                    },
                    popup=folium.Popup(popup_content, max_width=320),
                    tooltip=f"{zone_type}: {props.get('ZONE_NAME', 'N/A')}"
                ).add_to(layer_group)
            
            layer_groups[zone_type] = layer_group
            layer_group.add_to(m)
        
        # 추가 API 기반 구역 유형 정의
        additional_zone_types = {
            'P-73A(김포)': {
                'color': '#e74c3c', 'icon': '🚁', 'severity': 'high', 
                'border': '3px solid #c0392b',
                'reason': '김포공항 관제권 내 비행 제한'
            },
            'P-73B(인천)': {
                'color': '#3498db', 'icon': '✈️', 'severity': 'high', 
                'border': '3px solid #2980b9',
                'reason': '인천국제공항 관제권 내 비행 제한'
            },
            'R-75(수원)': {
                'color': '#f39c12', 'icon': '⚠️', 'severity': 'medium', 
                'border': '3px solid #e67e22',
                'reason': '수원 비행장 주변 제한구역'
            },
            'CTR(관제권)': {
                'color': '#9b59b6', 'icon': '🏢', 'severity': 'high', 
                'border': '3px solid #8e44ad',
                'reason': '공항 관제권 내 비행 제한'
            }
        }
        
        # 범례 HTML 생성 (수정된 버전)
        legend_html = f'''
        <div id="legend-container" style="
            position: fixed; 
            top: 20px; 
            left: 20px; 
            width: 380px; 
            background: rgba(255, 255, 255, 0.95); 
            border: 2px solid #34495e; 
            border-radius: 12px; 
            padding: 20px; 
            z-index: 9999; 
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            backdrop-filter: blur(10px);
            font-family: 'Malgun Gothic', Arial, sans-serif;
            max-height: 80vh;
            overflow-y: auto;
            display: none;">
            
            <div style="text-align: center; margin-bottom: 20px; border-bottom: 2px solid #ecf0f1; padding-bottom: 15px;">
                <h3 style="margin: 0; color: #2c3e50; font-size: 18px; font-weight: bold;">
                    🗺️ 비행 제한 구역 범례
                </h3>
                <p style="margin: 5px 0 0 0; font-size: 12px; color: #7f8c8d;">
                    구역을 선택하여 지도에서 표시/숨김
                </p>
            </div>
            
            <!-- 전체 제어 버튼 -->
            <div style="margin-bottom: 20px; text-align: center;">
                <button onclick="toggleAllZones(true)" 
                        style="background: linear-gradient(135deg, #27ae60, #2ecc71); 
                               color: white; border: none; padding: 8px 16px; 
                               border-radius: 20px; margin: 0 5px; cursor: pointer; 
                               font-size: 12px; font-weight: bold;
                               transition: all 0.3s ease;">
                    전체 표시
                </button>
                <button onclick="toggleAllZones(false)" 
                        style="background: linear-gradient(135deg, #e74c3c, #c0392b); 
                               color: white; border: none; padding: 8px 16px; 
                               border-radius: 20px; margin: 0 5px; cursor: pointer; 
                               font-size: 12px; font-weight: bold;
                               transition: all 0.3s ease;">
                    전체 숨김
                </button>
            </div>
            
            <!-- 실제 데이터 구역 -->
            <div style="background: linear-gradient(135deg, #3498db, #2980b9); 
                        color: white; padding: 12px; margin-bottom: 15px; 
                        border-radius: 8px; text-align: center;">
                <h4 style="margin: 0; font-size: 14px;">📊 실제 데이터 구역</h4>
                <div style="font-size: 11px; opacity: 0.9; margin-top: 4px;">
                    VWorld에서 수집된 실제 비행 제한 구역 데이터
                </div>
            </div>
            
            <div style="margin-bottom: 20px;">
        '''
        
        # 실제 데이터 구역 체크박스 추가
        for zone_type in sorted(type_counts.keys()):
            style = zone_styles.get(zone_type, default_style)
            safe_id = zone_type.replace("[^a-zA-Z0-9]/g", '_')
            
            legend_html += f'''
                <div style="display: flex; align-items: center; margin-bottom: 12px; 
                            padding: 8px; border-radius: 6px; 
                            background: rgba({style['color'][1:3]}, {style['color'][3:5]}, {style['color'][5:7]}, 0.1);
                            border-left: 4px solid {style['color']};">
                    <input type="checkbox" 
                           id="toggle_{safe_id}" 
                           class="zone-toggle"
                           onchange="toggleZoneType('{zone_type}')"
                           checked
                           style="margin-right: 10px; transform: scale(1.2); cursor: pointer;">
                    <div style="display: flex; align-items: center; flex: 1;">
                        <span style="font-size: 16px; margin-right: 8px;">{style['icon']}</span>
                        <div>
                            <div style="font-weight: bold; color: #2c3e50; font-size: 13px;">
                                {zone_type}
                            </div>
                            <div style="font-size: 11px; color: #7f8c8d;">
                                {type_counts[zone_type]}개 구역 | 위험도: {style['severity'].upper()}
                            </div>
                        </div>
                    </div>
                </div>
            '''
        
        # API 기반 구역 섹션
        legend_html += '''
            </div>
            
            <!-- API 기반 시뮬레이션 구역 -->
            <div style="background: linear-gradient(135deg, #e67e22, #d35400); 
                        color: white; padding: 12px; margin-bottom: 15px; 
                        border-radius: 8px; text-align: center;">
                <h4 style="margin: 0; font-size: 14px;">🔬 시뮬레이션 구역</h4>
                <div style="font-size: 11px; opacity: 0.9; margin-top: 4px;">
                    VWorld API 파라미터 기반 시뮬레이션 구역
                </div>
            </div>
            
            <div>
        '''
        
        # API 기반 구역 체크박스 추가
        for zone_type, style in additional_zone_types.items():
            safe_id = zone_type.replace("[^a-zA-Z0-9]", '_')
            
            legend_html += f'''
                <div style="display: flex; align-items: center; margin-bottom: 12px; 
                            padding: 8px; border-radius: 6px; 
                            background: rgba(230, 126, 34, 0.1);
                            border-left: 4px solid {style['color']};">
                    <input type="checkbox" 
                           id="toggle_api_{safe_id}" 
                           class="api-zone-toggle"
                           onchange="toggleAPIZoneType('{zone_type}')"
                           style="margin-right: 10px; transform: scale(1.2); cursor: pointer;">
                    <div style="display: flex; align-items: center; flex: 1;">
                        <span style="font-size: 16px; margin-right: 8px;">{style['icon']}</span>
                        <div>
                            <div style="font-weight: bold; color: #2c3e50; font-size: 13px;">
                                {zone_type}
                            </div>
                            <div style="font-size: 11px; color: #7f8c8d;">
                                시뮬레이션 | 위험도: {style['severity'].upper()}
                            </div>
                        </div>
                    </div>
                </div>
            '''
        
        legend_html += '''
            </div>
            
            <!-- 상태 표시 영역 -->
            <div id="toggle-status" 
                 style="display: none; 
                        position: fixed; 
                        top: 50%; 
                        left: 50%; 
                        transform: translate(-50%, -50%); 
                        background: #3498db; 
                        color: white; 
                        padding: 12px 24px; 
                        border-radius: 25px; 
                        font-weight: bold; 
                        z-index: 10000; 
                        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                        transition: all 0.3s ease;">
            </div>
        </div>
        '''
        
        # 수정된 JavaScript 코드
        javascript_code = f'''
        <script>
        // 전역 변수
        var mapInstance = null;
        var mapLayers = {{}};
        var apiZoneLayers = {{}};
        var zoneTypes = {list(type_counts.keys())};
        var additionalZoneTypes = {list(additional_zone_types.keys())};
        
        // DOM이 완전히 로드된 후 초기화
        document.addEventListener('DOMContentLoaded', function() {{
            console.log('DOM 로드 완료, 지도 초기화 시작');
            setTimeout(initializeMapControl, 1000);
        }});
        
        // 지도 인스턴스가 준비될 때까지 대기
        function waitForMap() {{
            return new Promise((resolve) => {{
                function checkMap() {{
                    if (window[Object.keys(window).find(key => key.startsWith('map_'))] !== undefined) {{
                        mapInstance = window[Object.keys(window).find(key => key.startsWith('map_'))];
                        resolve(mapInstance);
                    }} else {{
                        setTimeout(checkMap, 100);
                    }}
                }}
                checkMap();
            }});
        }}
        
        async function initializeMapControl() {{
            try {{
                console.log('지도 컨트롤 초기화 중...');
                
                // 지도 인스턴스 대기
                await waitForMap();
                console.log('지도 인스턴스 확인됨:', mapInstance);
                
                // 기존 레이어 매핑
                mapInstance.eachLayer(function(layer) {{
                    if (layer.feature && layer.feature.properties) {{
                        var zoneType = layer.feature.properties.ZONE_TYPE;
                        if (zoneType && zoneTypes.includes(zoneType)) {{
                            if (!mapLayers[zoneType]) {{
                                mapLayers[zoneType] = L.featureGroup();
                                mapLayers[zoneType].addTo(mapInstance);
                            }}
                            mapLayers[zoneType].addLayer(layer);
                            console.log('레이어 매핑:', zoneType);
                        }}
                    }}
                }});
                
                console.log('레이어 매핑 완료:', Object.keys(mapLayers));
                
                // API 기반 구역 레이어 초기화
                initializeAPIZoneLayers();
                
                // 범례 표시
                showLegend();
                
            }} catch (error) {{
                console.error('지도 컨트롤 초기화 오류:', error);
                setTimeout(initializeMapControl, 2000);
            }}
        }}
        
        function initializeAPIZoneLayers() {{
            console.log('API 구역 레이어 초기화 중...');
            var apiZoneData = {json.dumps(additional_zone_types, ensure_ascii=False)};
            
            for (var zoneType in apiZoneData) {{
                var zoneInfo = apiZoneData[zoneType];
                var layerGroup = L.featureGroup();
                
                createSampleAPIZone(layerGroup, zoneType, zoneInfo);
                apiZoneLayers[zoneType] = layerGroup;
                console.log('API 구역 레이어 생성:', zoneType);
            }}
        }}
        
        function createSampleAPIZone(layerGroup, zoneType, zoneInfo) {{
            var baseCoords = getBaseCoordinates(zoneType);
            var lat = baseCoords.lat;
            var lng = baseCoords.lng;
            
            // 마커 생성
            var iconHtml = `
                <div style="display: flex; justify-content: center; align-items: center; 
                            width: 30px; height: 30px; 
                            background-color: white; 
                            border: ${{zoneInfo.border}}; 
                            border-radius: 50%; 
                            box-shadow: 0 3px 6px rgba(0,0,0,0.2); 
                            font-size: 15px;">
                    ${{zoneInfo.icon}}
                </div>
            `;
            
            var marker = L.marker([lat, lng], {{
                icon: L.divIcon({{
                    html: iconHtml,
                    iconSize: [30, 30],
                    iconAnchor: [15, 15],
                    className: 'custom-api-marker'
                }})
            }});
            
            var popupContent = `
                <div style="width: 300px; font-family: 'Malgun Gothic', Arial, sans-serif;">
                    <h4>${{zoneType}} (시뮬레이션)</h4>
                    <p>위치: ${{lat.toFixed(6)}}, ${{lng.toFixed(6)}}</p>
                    <p>제한 이유: ${{zoneInfo.reason}}</p>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            marker.addTo(layerGroup);
            
            // 원형 영역
            var circle = L.circle([lat, lng], {{
                color: zoneInfo.color,
                fillColor: zoneInfo.color,
                fillOpacity: 0.2,
                opacity: 0.6,
                radius: 2000,
                weight: 3
            }});
            
            circle.bindPopup(popupContent);
            circle.addTo(layerGroup);
        }}
        
        function getBaseCoordinates(zoneType) {{
            var coordinates = {{
                'P-73A(김포)': {{lat: 37.5583, lng: 126.7906}},
                'P-73B(인천)': {{lat: 37.4602, lng: 126.4407}},
                'R-75(수원)': {{lat: 37.2636, lng: 127.0286}},
                'CTR(관제권)': {{lat: 37.5665, lng: 126.9780}}
            }};
            
            return coordinates[zoneType] || {{lat: 37.5665, lng: 126.9780}};
        }}
        
        // 수정된 토글 함수들
        function toggleZoneType(zoneType) {{
            try {{
                console.log('구역 토글 시도:', zoneType);
                var checkboxId = 'toggle_' + zoneType.replace("[^a-zA-Z0-9]", '_');
                var checkbox = document.getElementById(checkboxId);
                
                if (!checkbox) {{
                    console.error('체크박스를 찾을 수 없습니다:', checkboxId);
                    return;
                }}
                
                var layer = mapLayers[zoneType];
                if (layer && mapInstance) {{
                    if (checkbox.checked) {{
                        if (!mapInstance.hasLayer(layer)) {{
                            mapInstance.addLayer(layer);
                        }}
                        console.log('레이어 표시:', zoneType);
                        showStatus(zoneType + ' 표시됨', '#27ae60');
                    }} else {{
                        if (mapInstance.hasLayer(layer)) {{
                            mapInstance.removeLayer(layer);
                        }}
                        console.log('레이어 숨김:', zoneType);
                        showStatus(zoneType + ' 숨김', '#e74c3c');
                    }}
                }} else {{
                    console.error('레이어 또는 지도를 찾을 수 없습니다:', zoneType);
                }}
                
            }} catch (error) {{
                console.error('구역 토글 오류:', error);
            }}
        }}
        
        function toggleAPIZoneType(zoneType) {{
            try {{
                console.log('API 구역 토글 시도:', zoneType);
                var checkboxId = 'toggle_api_' + zoneType.replace("[^a-zA-Z0-9]", '_');
                var checkbox = document.getElementById(checkboxId);
                
                if (!checkbox) {{
                    console.error('API 구역 체크박스를 찾을 수 없습니다:', checkboxId);
                    return;
                }}
                
                var layer = apiZoneLayers[zoneType];
                if (layer && mapInstance) {{
                    if (checkbox.checked) {{
                        if (!mapInstance.hasLayer(layer)) {{
                            mapInstance.addLayer(layer);
                        }}
                        console.log('API 구역 레이어 표시:', zoneType);
                        showStatus(zoneType + ' 시뮬레이션 표시됨', '#e67e22');
                    }} else {{
                        if (mapInstance.hasLayer(layer)) {{
                            mapInstance.removeLayer(layer);
                        }}
                        console.log('API 구역 레이어 숨김:', zoneType);
                        showStatus(zoneType + ' 시뮬레이션 숨김', '#95a5a6');
                    }}
                }} else {{
                    console.error('API 구역 레이어를 찾을 수 없습니다:', zoneType);
                }}
                
            }} catch (error) {{
                console.error('API 구역 토글 오류:', error);
            }}
        }}
        
        function toggleAllZones(show) {{
            try {{
                console.log('전체 토글:', show);
                
                // 실제 데이터 구역
                zoneTypes.forEach(function(zoneType) {{
                    var checkboxId = 'toggle_' + zoneType.replace("[^a-zA-Z0-9]", '_');
                    var checkbox = document.getElementById(checkboxId);
                    
                    if (checkbox) {{
                        checkbox.checked = show;
                        var layer = mapLayers[zoneType];
                        if (layer && mapInstance) {{
                            if (show) {{
                                if (!mapInstance.hasLayer(layer)) {{
                                    mapInstance.addLayer(layer);
                                }}
                            }} else {{
                                if (mapInstance.hasLayer(layer)) {{
                                    mapInstance.removeLayer(layer);
                                }}
                            }}
                        }}
                    }}
                }});
                
                // API 기반 구역
                additionalZoneTypes.forEach(function(zoneType) {{
                    var checkboxId = 'toggle_api_' + zoneType.replace("[^a-zA-Z0-9]", '_');
                    var checkbox = document.getElementById(checkboxId);
                    
                    if (checkbox) {{
                        checkbox.checked = show;
                        var layer = apiZoneLayers[zoneType];
                        if (layer && mapInstance) {{
                            if (show) {{
                                if (!mapInstance.hasLayer(layer)) {{
                                    mapInstance.addLayer(layer);
                                }}
                            }} else {{
                                if (mapInstance.hasLayer(layer)) {{
                                    mapInstance.removeLayer(layer);
                                }}
                            }}
                        }}
                    }}
                }});
                
                var message = show ? '모든 구역이 표시됩니다' : '모든 구역이 숨겨졌습니다';
                var color = show ? '#27ae60' : '#95a5a6';
                showStatus(message, color);
                
            }} catch (error) {{
                console.error('전체 토글 오류:', error);
            }}
        }}
        
        function showStatus(message, color = '#3498db') {{
            var statusDiv = document.getElementById('toggle-status');
            if (statusDiv) {{
                statusDiv.textContent = message;
                statusDiv.style.background = color;
                statusDiv.style.display = 'block';
                statusDiv.style.opacity = '1';
                
                setTimeout(function() {{
                    statusDiv.style.opacity = '0';
                    setTimeout(function() {{
                        statusDiv.style.display = 'none';
                    }}, 300);
                }}, 2500);
            }}
        }}
        
        function showLegend() {{
            var legend = document.getElementById('legend-container');
            if (legend) {{
                legend.style.display = 'block';
                legend.style.animation = 'fadeIn 0.3s ease';
            }}
        }}
        
        function toggleLegend() {{
            var legend = document.getElementById('legend-container');
            if (legend) {{
                if (legend.style.display === 'none' || legend.style.display === '') {{
                    legend.style.display = 'block';
                    legend.style.animation = 'fadeIn 0.3s ease';
                }} else {{
                    legend.style.display = 'none';
                }}
            }}
        }}
        
        // 범례 토글 버튼 추가 (키보드 단축키)
        document.addEventListener('keydown', function(event) {{
            if (event.key === 'L' || event.key === 'l') {{
                toggleLegend();
            }}
        }});
        
        // CSS 애니메이션 추가
        var style = document.createElement('style');
        style.textContent = `
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(-20px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            
            
            .zone-toggle:hover, .api-zone-toggle:hover {{
                transform: scale(1.3) !important;
                transition: transform 0.2s ease;
            }}
            
            button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            }}
            
            #legend-container::-webkit-scrollbar {{
                width: 8px;
            }}
            
            #legend-container::-webkit-scrollbar-track {{
                background: #f1f1f1;
                border-radius: 4px;
            }}
            
            #legend-container::-webkit-scrollbar-thumb {{
                background: #888;
                border-radius: 4px;
            }}
            
            #legend-container::-webkit-scrollbar-thumb:hover {{
                background: #555;
            }}
        `;
        document.head.appendChild(style);
        
        </script>
        '''
        
        # 범례와 JavaScript를 지도에 추가
        m.get_root().html.add_child(folium.Element(legend_html))
        m.get_root().html.add_child(folium.Element(javascript_code))
        
        # 레이어 컨트롤 추가
        folium.LayerControl(position='topright').add_to(m)
        
        # 범례 토글 버튼 추가
        toggle_button_html = '''
        <div style="position: fixed; top: 20px; right: 20px; z-index: 9998;">
            <button onclick="toggleLegend()" 
                    style="background: linear-gradient(135deg, #3498db, #2980b9); 
                           color: white; border: none; padding: 12px 16px; 
                           border-radius: 25px; cursor: pointer; 
                           font-weight: bold; font-size: 14px;
                           box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                           transition: all 0.3s ease;"
                    onmouseover="this.style.transform='translateY(-2px)'"
                    onmouseout="this.style.transform='translateY(0)'">
                📋 범례 (L)
            </button>
        </div>
        '''
        
        m.get_root().html.add_child(folium.Element(toggle_button_html))
        
        # 지도 저장
        m.save(output_filename)
        
        # 통계 정보 출력
        print("\n" + "="*60)
        print("🎯 VWorld 비행 제한 구역 지도 생성 완료!")
        print("="*60)
        print(f"📁 파일명: {output_filename}")
        print(f"📊 총 구역 수: {len(valid_zones)}개")
        print("\n📈 구역별 통계:")
        
        for zone_type, count in sorted(type_counts.items()):
            style = zone_styles.get(zone_type, default_style)
            print(f"  {style['icon']} {zone_type}: {count}개 (위험도: {style['severity'].upper()})")
        
        print(f"\n🔬 시뮬레이션 구역: {len(additional_zone_types)}개")
        for zone_type in additional_zone_types:
            print(f"  {additional_zone_types[zone_type]['icon']} {zone_type}")
        
        print("\n💡 사용법:")
        print("  • 범례에서 체크박스를 클릭하여 구역 표시/숨김")
        print("  • '전체 표시/숨김' 버튼으로 일괄 제어")
        print("  • 'L' 키를 눌러 범례 토글")
        print("  • 구역을 클릭하면 상세 정보 팝업")
        print("  • 우측 상단에서 지도 레이어 변경 가능")
        print("="*60)
        
        return m
        
    except Exception as e:
        print(f"❌ 지도 생성 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return None



def save_classified_data(zones):
    """분류된 데이터를 JSON 파일로 저장"""
    
    try:
        # 구역 유형별 통계
        type_stats = {}
        severity_stats = {'high': 0, 'medium': 0, 'low': 0}
        district_stats = {}
        
        for zone in zones:
            # 유형별 통계
            zone_type = zone['restriction_info']['type']
            if zone_type not in type_stats:
                type_stats[zone_type] = []
            type_stats[zone_type].append({
                'name': zone['name'],
                'location': zone['address_info'].get('simple_address', '위치 정보 없음') if zone['address_info'] else '위치 정보 없음',
                'severity': zone['restriction_info']['severity'],
                'altitude_limit': zone['altitude_limit'],
                'labels': zone['labels']
            })
            
            # 위험도별 통계
            severity = zone['restriction_info']['severity']
            if severity in severity_stats:
                severity_stats[severity] += 1
            
            # 지역별 통계
            if zone.get('address_info') and zone['address_info'].get('sigungu'):
                district = zone['address_info']['sigungu']
                if district not in district_stats:
                    district_stats[district] = {'total': 0, 'types': {}}
                district_stats[district]['total'] += 1
                if zone_type not in district_stats[district]['types']:
                    district_stats[district]['types'][zone_type] = 0
                district_stats[district]['types'][zone_type] += 1
        
        summary = {
            'metadata': {
                'total_zones': len(zones),
                'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': '국토교통부 VWorld API',
                'api_endpoint': 'LT_C_AISPRHC'
            },
            'statistics': {
                'by_type': {zone_type: len(zones_list) for zone_type, zones_list in type_stats.items()},
                'by_severity': severity_stats,
                'by_district': district_stats
            },
            'zones_by_type': type_stats,
            'detailed_zones': zones
        }
        
        # 결과 디렉토리 생성
        os.makedirs('result_data', exist_ok=True)
        
        # JSON 저장
        filename = 'result_data/classified_flight_restriction_zones.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 분류된 데이터가 '{filename}' 파일로 저장되었습니다.")
        
        # 통계 요약 출력
        print(f"\n📊 비행 제한 구역 분석 결과:")
        print(f"   총 구역 수: {len(zones)}개")
        
        print(f"\n🏷️  구역 유형별 분포:")
        for zone_type, count in summary['statistics']['by_type'].items():
            print(f"   {zone_type}: {count}개")
        
        print(f"\n⚠️  위험도별 분포:")
        for severity, count in severity_stats.items():
            severity_kr = {'high': '높음', 'medium': '보통', 'low': '낮음'}
            print(f"   {severity_kr[severity]} ({severity}): {count}개")
        
        if district_stats:
            print(f"\n🌍 지역별 분포 (상위 5개):")
            sorted_districts = sorted(district_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:5]
            for district, stats in sorted_districts:
                print(f"   {district}: {stats['total']}개")
                for zone_type, count in stats['types'].items():
                    print(f"     - {zone_type}: {count}개")
        
        return summary
        
    except Exception as e:
        print(f"❌ 분류된 데이터 저장 오류: {e}")
        return None

def create_summary_report(zones):
    """분석 결과 요약 리포트 생성"""
    
    try:
        report_content = f"""
# 비행 제한 구역 분석 리포트

## 📋 분석 개요
- **분석 일시**: {time.strftime('%Y년 %m월 %d일 %H시 %M분')}
- **데이터 출처**: 국토교통부 VWorld API (LT_C_AISPRHC)
- **총 구역 수**: {len(zones)}개
- **분석 범위**: 서울시 일대

## 🏷️ 구역 유형별 분석

"""
        
        # 구역 유형별 통계
        type_stats = {}
        for zone in zones:
            zone_type = zone['restriction_info']['type']
            if zone_type not in type_stats:
                type_stats[zone_type] = []
            type_stats[zone_type].append(zone)
        
        for zone_type, zone_list in type_stats.items():
            report_content += f"### {zone_list[0]['restriction_info']['icon']} {zone_type}\n"
            report_content += f"- **구역 수**: {len(zone_list)}개\n"
            report_content += f"- **위험도**: {zone_list[0]['restriction_info']['severity']}\n"
            report_content += f"- **표시 색상**: {zone_list[0]['restriction_info']['color']}\n\n"
            
            report_content += "**주요 구역:**\n"
            for zone in zone_list[:3]:  # 상위 3개만 표시
                location = zone['address_info'].get('simple_address', '위치 정보 없음') if zone['address_info'] else '위치 정보 없음'
                report_content += f"- {zone['name']} ({location})\n"
            
            if len(zone_list) > 3:
                report_content += f"- ... 외 {len(zone_list) - 3}개 구역\n"
            
            report_content += "\n"
        
        # 위험도별 통계
        severity_stats = {'high': 0, 'medium': 0, 'low': 0}
        for zone in zones:
            severity = zone['restriction_info']['severity']
            if severity in severity_stats:
                severity_stats[severity] += 1
        
        report_content += "## ⚠️ 위험도별 분포\n\n"
        severity_kr = {'high': '🔴 높음 (High)', 'medium': '🟡 보통 (Medium)', 'low': '🟢 낮음 (Low)'}
        for severity, count in severity_stats.items():
            percentage = (count / len(zones)) * 100
            report_content += f"- **{severity_kr[severity]}**: {count}개 ({percentage:.1f}%)\n"
        
        # 지역별 통계
        district_stats = {}
        for zone in zones:
            if zone.get('address_info') and zone['address_info'].get('sigungu'):
                district = zone['address_info']['sigungu']
                if district not in district_stats:
                    district_stats[district] = []
                district_stats[district].append(zone)
        
        if district_stats:
            report_content += "\n## 🌍 지역별 분포\n\n"
            sorted_districts = sorted(district_stats.items(), key=lambda x: len(x[1]), reverse=True)
            
            for district, zone_list in sorted_districts:
                report_content += f"### {district}\n"
                report_content += f"- **총 구역 수**: {len(zone_list)}개\n"
                
                # 지역 내 유형별 분포
                local_type_stats = {}
                for zone in zone_list:
                    zone_type = zone['restriction_info']['type']
                    if zone_type not in local_type_stats:
                        local_type_stats[zone_type] = 0
                    local_type_stats[zone_type] += 1
                
                report_content += "- **유형별 분포**:\n"
                for zone_type, count in local_type_stats.items():
                    report_content += f"  - {zone_type}: {count}개\n"
                
                report_content += "\n"
        
        # 주요 제한 사항
        report_content += f"""
## 📝 주요 제한 사항 및 주의사항

### 🚫 비행금지구역
- **완전 비행 금지**: 드론 비행 절대 불가
- **법적 처벌**: 위반 시 항공안전법에 따른 처벌 가능
- **주요 대상**: 공항, 군사시설, 정부청사 주변

### ⚠️ 비행제한구역
- **조건부 비행 허용**: 특정 조건 하에서만 비행 가능
- **사전 승인 필요**: 관련 기관 승인 후 비행
- **고도 제한**: 지정된 고도 이하에서만 비행

### 📏 고도제한구역
- **고도 제한**: 특정 고도 이하에서만 비행 허용
- **UNL (Unlimited)**: 고도 제한 없음
- **GND (Ground)**: 지상에서의 제한

## 🔍 데이터 활용 방법

1. **지도 파일**: `classified_flight_restriction_zones.html` 브라우저로 열기
2. **상세 데이터**: `classified_flight_restriction_zones.json` 파일 참조
3. **레이어 컨트롤**: 지도에서 구역 유형별 표시/숨김 가능
4. **마커 클릭**: 각 구역의 상세 정보 확인

## ⚖️ 법적 고지사항

- 본 데이터는 참고용이며, 실제 드론 비행 전 관련 법규 확인 필수
- 항공안전법, 드론 활용 촉진 및 기반조성에 관한 법률 준수 필요
- 비행 전 국토교통부 드론원스톱민원서비스(drone.go.kr) 확인 권장

---
*리포트 생성 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}*
*데이터 출처: 국토교통부 VWorld API*
"""
        
        # 리포트 저장
        report_filename = 'result_data/flight_restriction_analysis_report.md'
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"✅ 분석 리포트가 '{report_filename}' 파일로 저장되었습니다.")
        
        return report_filename
        
    except Exception as e:
        print(f"❌ 리포트 생성 오류: {e}")
        return None

def main():
    """메인 실행 함수"""
    
    print("🚀 비행 제한 구역 분류 및 지도 생성 시작")
    print("=" * 70)
    
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
    
    # 1. 비행 제한 구역 데이터 분석
    zones = fetch_flight_restriction_data()
    
    if not zones:
        print("❌ 분석할 데이터가 없습니다.")
        return
    
    # 2. 분류된 데이터 저장
    print(f"\n💾 분류된 데이터 저장 중...")
    save_classified_data(zones)
    
    # 3. 분류된 VWorld 지도 생성
    print(f"\n🗺️  분류된 VWorld 지도 생성 중...")
    create_classified_vworld_map(zones)
    
    # 4. 분석 리포트 생성
    print(f"\n📄 분석 리포트 생성 중...")
    create_summary_report(zones)
    
    print("\n🎉 모든 작업이 완료되었습니다!")
    print("=" * 70)
    print("생성된 파일:")
    
    # 생성된 파일 확인
    files_to_check = [
        'result_data/classified_flight_restriction_zones.html',
        'result_data/classified_flight_restriction_zones.json',
        'result_data/flight_restriction_analysis_report.md'
    ]
    
    for filename in files_to_check:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"   ✅ {filename} ({size:,} bytes)")
        else:
            print(f"   ❌ {filename} (생성 실패)")
    
    print(f"\n📖 사용 가이드:")
    print(f"   1. 🗺️  지도 확인: result_data/classified_flight_restriction_zones.html")
    print(f"   2. 📊 데이터 분석: result_data/classified_flight_restriction_zones.json")
    print(f"   3. 📄 리포트 읽기: result_data/flight_restriction_analysis_report.md")
    print(f"   4. 🎛️  레이어 컨트롤로 구역 유형별 필터링")
    print(f"   5. 🖱️  마커 클릭으로 상세 정보 확인")
    
    print(f"\n⚖️  법적 주의사항:")
    print(f"   • 실제 드론 비행 전 최신 법규 및 승인 사항 확인 필수")
    print(f"   • 국토교통부 드론원스톱민원서비스(drone.go.kr) 활용 권장")
    print(f"   • 본 데이터는 참고용이며 법적 책임은 사용자에게 있음")

if __name__ == "__main__":
    main()
