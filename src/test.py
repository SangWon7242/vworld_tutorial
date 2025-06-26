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
    
    # 제한 구역 분류
    restriction_info = {
        'type': '비행금지구역',  # 기본값
        'severity': 'high',     # 위험도: high, medium, low
        'color': 'red',         # 표시 색상
        'icon': '🚫',          # 아이콘
        'labels': [],          # 라벨 정보
        'reason': '국가 안보 및 안전상의 이유로 비행이 금지된 구역입니다. 허가 없이 비행할 경우 법적 처벌을 받을 수 있습니다.'  # 기본 이유
    }
    
    # 라벨 정보 수집
    labels = []
    if prh_lbl_1: labels.append(prh_lbl_1)
    if prh_lbl_2: labels.append(prh_lbl_2)
    if prh_lbl_3: labels.append(prh_lbl_3)
    if prh_lbl_4: labels.append(prh_lbl_4)
    
    restriction_info['labels'] = labels
    
    # 제한 구역 유형별 분류
    if '비행제한구역' in prh_lbl_4 or '제한' in prohibited:
        restriction_info.update({
            'type': '비행제한구역',
            'severity': 'medium',
            'color': 'orange',
            'icon': '⚠️',
            'reason': '특정 조건(고도, 시간, 허가 등)에 따라 비행이 제한되는 구역입니다. 사전 허가를 받으면 비행이 가능할 수 있습니다.'
        })
    elif 'UNL' in prh_lbl_2:  # Unlimited
        restriction_info.update({
            'type': '고도제한없음',
            'severity': 'low',
            'color': 'yellow',
            'icon': '📏',
            'reason': '고도 제한이 없는 구역이지만, 다른 비행 규정은 준수해야 합니다. 주변 환경과 기상 조건을 고려하여 안전하게 비행하세요.'
        })
    elif 'GND' in prh_lbl_3:  # Ground
        restriction_info.update({
            'type': '지상제한구역',
            'severity': 'high',
            'color': 'darkred',
            'icon': '🚫',
            'reason': '지상부터 특정 고도까지 비행이 제한된 구역입니다. 군사시설, 주요 인프라 보호 등의 이유로 설정되었습니다.'
        })
    elif 'P61A' in prh_lbl_1:  # 특정 코드
        restriction_info.update({
            'type': '특별관리구역',
            'severity': 'high',
            'color': 'purple',
            'icon': '🔒',
            'reason': '국가 중요시설 또는 특별 보안이 필요한 구역으로, 특별 허가 없이는 비행이 불가능합니다.'
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

def create_classified_vworld_map(zones):
    """분류된 비행 제한 구역을 VWorld 지도에 표시"""
    
    if not FOLIUM_AVAILABLE:
        print("⚠️  folium이 설치되지 않아 지도를 생성할 수 없습니다.")
        return None
    
    if not zones:
        print("❌ 표시할 구역이 없습니다.")
        return None
    
    # 유효한 좌표가 있는 구역만 필터링
    valid_zones = [z for z in zones if z['center_lat'] and z['center_lng']]
    
    if not valid_zones:
        print("❌ 유효한 좌표가 있는 구역이 없습니다.")
        return None
    
    print(f"🗺️  분류된 비행 제한 구역 {len(valid_zones)}개를 VWorld 지도에 표시 중...")
    
    try:
        # 지도 중심점 계산
        center_lat = sum(z['center_lat'] for z in valid_zones) / len(valid_zones)
        center_lng = sum(z['center_lng'] for z in valid_zones) / len(valid_zones)
        
        print(f"   지도 중심: 위도 {center_lat:.6f}, 경도 {center_lng:.6f}")
        
        # VWorld 지도 타일 URL 설정
        api_key = os.getenv('VWORLD_API_KEY')
        
        vworld_tiles = {
            'Base': f'http://api.vworld.kr/req/wmts/1.0.0/{api_key}/Base/{{z}}/{{y}}/{{x}}.png',
            'Satellite': f'http://api.vworld.kr/req/wmts/1.0.0/{api_key}/Satellite/{{z}}/{{y}}/{{x}}.jpeg',
            'Hybrid': f'http://api.vworld.kr/req/wmts/1.0.0/{api_key}/Hybrid/{{z}}/{{y}}/{{x}}.png'
        }
        
        # 기본 지도 생성
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=11
        )
        
        # VWorld 타일 레이어 추가
        for tile_name, tile_url in vworld_tiles.items():
            folium.raster_layers.TileLayer(
                tiles=tile_url,
                attr=f'VWorld {tile_name} | 국토교통부',
                name=f'VWorld {tile_name}',
                overlay=False,
                control=True
            ).add_to(m)
        
        # 구역 유형별 그룹 생성
        restriction_groups = {}
        
        # 각 구역을 지도에 표시
        for zone in valid_zones:
            try:
                restriction_info = zone['restriction_info']
                zone_type = restriction_info['type']
                color = restriction_info['color']
                icon_emoji = restriction_info['icon']
                severity = restriction_info['severity']
                
                # 그룹이 없으면 생성
                if zone_type not in restriction_groups:
                    restriction_groups[zone_type] = folium.FeatureGroup(name=f"{icon_emoji} {zone_type}")
                    restriction_groups[zone_type].add_to(m)
                
                address_info = zone['address_info'] or {}
                
                # 위험도별 스타일 설정
                severity_styles = {
                    'high': {'weight': 4, 'opacity': 0.9, 'fillOpacity': 0.4},
                    'medium': {'weight': 3, 'opacity': 0.7, 'fillOpacity': 0.3},
                    'low': {'weight': 2, 'opacity': 0.5, 'fillOpacity': 0.2}
                }
                
                style = severity_styles.get(severity, severity_styles['medium'])
                
                # 상세 팝업 내용 생성
                popup_html = f"""
                <div style="width: 350px; font-family: 'Malgun Gothic', Arial, sans-serif; line-height: 1.4;">
                    <div style="background: linear-gradient(135deg, {color} 0%, {'darkred' if severity == 'high' else 'orange' if severity == 'medium' else 'green'} 100%); 
                                color: white; padding: 12px; margin: -10px -10px 12px -10px; border-radius: 8px 8px 0 0;">
                        <h4 style="margin: 0; font-size: 16px; display: flex; align-items: center;">
                            <span style="font-size: 20px; margin-right: 8px;">{icon_emoji}</span>
                            {zone['name']}
                        </h4>
                        <div style="font-size: 12px; opacity: 0.9; margin-top: 4px;">
                            {restriction_info['type']} | 위험도: {severity.upper()}
                        </div>
                    </div>
                    
                    <div style="padding: 5px 0;">
                        <div style="background: #f8f9fa; padding: 10px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid {color};">
                            <strong style="color: #495057;">📍 위치 정보</strong><br>
                            <span style="color: #dc3545; font-weight: bold; font-size: 14px;">
                                {address_info.get('simple_address', '위치 정보 없음')}
                            </span><br>
                            <span style="font-size: 11px; color: #6c757d;">
                                {address_info.get('full_address', '상세 주소 없음')}
                            </span>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;">
                            <div style="background: #e9ecef; padding: 8px; border-radius: 4px;">
                                <strong style="font-size: 11px; color: #495057;">📏 고도제한</strong><br>
                                <span style="font-size: 12px; color: {'#d32f2f' if severity == 'high' else '#e65100' if severity == 'medium' else '#2e7d32'}; font-weight: bold;">{zone['altitude_limit']}</span>
                            </div>
                            <div style="background: #e9ecef; padding: 8px; border-radius: 4px;">
                                <strong style="font-size: 11px; color: #495057;">⚠️ 위험도</strong><br>
                                <span style="font-size: 12px; color: {'#d32f2f' if severity == 'high' else '#e65100' if severity == 'medium' else '#2e7d32'}; font-weight: bold;">{severity.upper()}</span>
                            </div>
                        </div>
                        
                        <div style="margin-bottom: 10px;">
                            <strong style="color: #495057;">🏷️ 제한 라벨</strong><br>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;">
                """
                
                # 라벨 태그 추가
                for label in zone['labels']:
                    if label and label.strip():
                        tag_bg_color = {
                            '비행금지구역': '#d32f2f',
                            '비행제한구역': '#e65100',
                            '고도제한없음': '#2e7d32',
                            '지상제한구역': '#c2185b',
                            '특별관리구역': '#7b1fa2'
                        }.get(zone_type, '#3949ab')
                        popup_html += f'<span style="background: {tag_bg_color}; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.2);">{label}</span>'
                
                popup_html += f"""
                            </div>
                        </div>
                        
                        <div style="margin-bottom: 10px;">
                            <strong style="color: #495057;">📝 상세설명</strong><br>
                            <div style="max-height: 60px; overflow-y: auto; font-size: 11px; color: #6c757d; 
                                        background: #f8f9fa; padding: 6px; border-radius: 4px; margin-top: 4px;">
                                {zone['description']}
                            </div>
                        </div>
                        
                        <div style="margin-bottom: 10px; background: {'#ffebee' if zone_type == '비행금지구역' else '#fff3e0'}; padding: 8px; border-radius: 4px; border-left: 4px solid {color};">
                            <strong style="color: #495057;">⚠️ 제한 이유</strong><br>
                            <div style="font-size: 11px; color: {'#d32f2f' if zone_type == '비행금지구역' else '#e65100'}; margin-top: 4px; font-weight: bold;">
                                {restriction_info.get('reason', '제한 이유 정보가 없습니다.')}
                            </div>
                        </div>
                        
                        <div style="border-top: 1px solid #dee2e6; padding-top: 8px; font-size: 10px; color: #868e96;">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                                <div><strong>좌표:</strong><br>{zone['center_lat']:.6f}<br>{zone['center_lng']:.6f}</div>
                                <div><strong>데이터 출처:</strong><br>국토교통부<br>VWorld API</div>
                            </div>
                        </div>
                    </div>
                </div>
                """
                
                # 커스텀 아이콘 생성
                icon_html = f"""
                <div style="
                    background: linear-gradient(135deg, {color} 0%, {'#8B0000' if severity == 'high' else '#FF8C00' if severity == 'medium' else '#32CD32'} 100%); 
                    border: {'3px solid red' if zone_type == '비행금지구역' else '3px solid white'}; 
                    border-radius: 50%; 
                    width: {28 if zone_type == '비행금지구역' else 24}px; 
                    height: {28 if zone_type == '비행금지구역' else 24}px; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center;
                    box-shadow: {('0 0 8px rgba(255,0,0,0.8)' if zone_type == '비행금지구역' else '0 2px 6px rgba(0,0,0,0.4)')};
                    font-size: {14 if zone_type == '비행금지구역' else 12}px;
                    color: white;
                    font-weight: bold;
                ">
                    {icon_emoji}
                </div>
                """
                
                # 마커 추가
                folium.Marker(
                    location=[zone['center_lat'], zone['center_lng']],
                    popup=folium.Popup(popup_html, max_width=380),
                    tooltip=f"{icon_emoji} {zone['name']} ({restriction_info['type']}) - {address_info.get('simple_address', '위치 정보 없음')}",
                    icon=folium.DivIcon(html=icon_html, icon_size=(28 if zone_type == '비행금지구역' else 24, 28 if zone_type == '비행금지구역' else 24), icon_anchor=(14 if zone_type == '비행금지구역' else 12, 14 if zone_type == '비행금지구역' else 12))
                ).add_to(restriction_groups[zone_type])
                
                # 구역 경계 표시
                if zone['coordinates'] and zone.get('geometry_type') in ['Polygon', 'MultiPolygon']:
                    if zone.get('geometry_type') == 'Polygon':
                        coords = zone['coordinates'][0]  # 외부 링
                        folium_coords = [[coord[1], coord[0]] for coord in coords]
                        
                        folium.Polygon(
                            locations=folium_coords,
                            color=color,
                            weight=style['weight'],
                            opacity=style['opacity'],
                            fillColor=color,
                            fillOpacity=style['fillOpacity'],
                            popup=f"{icon_emoji} {zone['name']} ({restriction_info['type']})",
                            tooltip=f"제한구역: {zone['name']}"
                        ).add_to(restriction_groups[zone_type])
                    
                    elif zone.get('geometry_type') == 'MultiPolygon':
                        for polygon in zone['coordinates']:
                            coords = polygon[0]  # 외부 링
                            folium_coords = [[coord[1], coord[0]] for coord in coords]
                            
                            folium.Polygon(
                                locations=folium_coords,
                                color=color,
                                weight=style['weight'],
                                opacity=style['opacity'],
                                fillColor=color,
                                fillOpacity=style['fillOpacity'],
                                popup=f"{icon_emoji} {zone['name']} ({restriction_info['type']})",
                                tooltip=f"제한구역: {zone['name']}"
                            ).add_to(restriction_groups[zone_type])
                
                print(f"   ✅ {zone['name']} ({restriction_info['type']}) 표시 완료")
                
            except Exception as e:
                print(f"   ❌ {zone['name']} 표시 실패: {e}")
                continue
        
        # 레이어 컨트롤 추가
        folium.LayerControl(collapsed=False).add_to(m)
        
        # 상세 범례 추가
        legend_html = f'''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 280px; height: auto; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white;
                    border: none; 
                    border-radius: 12px;
                    z-index: 9999; 
                    font-size: 13px; 
                    padding: 16px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                    font-family: 'Malgun Gothic', Arial, sans-serif;">
        <h4 style="margin-top: 0; margin-bottom: 12px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 8px;">
            🚁 비행 제한 구역 분류
        </h4>
        '''
        
        # 구역 유형별 범례 항목 추가
        type_counts = {}
        for zone in valid_zones:
            zone_type = zone['restriction_info']['type']
            if zone_type not in type_counts:
                type_counts[zone_type] = {'count': 0, 'info': zone['restriction_info']}
            type_counts[zone_type]['count'] += 1
        
        for zone_type, data in type_counts.items():
            info = data['info']
            count = data['count']
            legend_html += f'''
            <div style="margin-bottom: 8px; display: flex; align-items: center;">
                <span style="display: inline-block; width: 16px; height: 16px; background-color: {info['color']}; 
                            border-radius: 50%; margin-right: 8px; border: 2px solid white;"></span>
                <span style="font-size: 12px;">{info['icon']} {zone_type} ({count}개)</span>
            </div>
            '''
        
        legend_html += '''
        <div style="border-top: 1px solid rgba(255,255,255,0.3); padding-top: 8px; margin-top: 8px;">
            <div style="font-size: 11px; opacity: 0.9; line-height: 1.3;">
                • 마커 클릭: 상세 정보 확인<br>
                • 레이어 패널: 구역 유형별 표시/숨김<br>
                • 색칠된 영역: 실제 제한 구역 경계
            </div>
        </div>
        <div style="border-top: 1px solid rgba(255,255,255,0.3); padding-top: 8px; margin-top: 8px; 
                    font-size: 10px; text-align: center; opacity: 0.8;">
            데이터 출처: 국토교통부 VWorld API
        </div>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # 지도 저장
        map_filename = 'result_data/classified_flight_restriction_zones.html'
        m.save(map_filename)
        print(f"✅ 분류된 비행 제한 구역 지도가 '{map_filename}' 파일로 저장되었습니다.")
        
        # 파일 생성 확인
        if os.path.exists(map_filename):
            file_size = os.path.getsize(map_filename)
            print(f"   파일 크기: {file_size:,} bytes")
            print(f"   총 표시된 구역: {len(valid_zones)}개")
            print(f"   구역 유형: {len(type_counts)}가지")
        else:
            print("❌ 파일 저장 실패")
        
        return m
        
    except Exception as e:
        print(f"❌ 분류된 VWorld 지도 생성 오류: {e}")
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
        report_content += """
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
