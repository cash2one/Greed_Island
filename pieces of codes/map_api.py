# coding:utf-8

import json
import requests
import traceback
import time
from requests.exceptions import Timeout
from random import randint
from core_gedis import Redis
from ast import literal_eval

URL = "http://api.map.baidu.com/place/v2/search"

AK = "EkWrRKGGyYTHavtTxGsFXy3p"
NEW_AK = "VQ6ZByDZ5EHSzQ6GIoQQGadx"

AK_BUFFER = [
    "sUiLz1vjhG212GBTnd5lZ8qw",
    "fudo2FQT2a57BlYmG8TNtWR5",
    "MlCrreOLOENQ8g4diEcVYpnh",
    "BCxvz1Cj51ilaf76ULAF5Iva",
    "MIp3BbV0YmtGX2VDqYVu12II",
    "SyXl5mIxG1ZOrCaNDTdCDIfn",
    "GpPGxVwFP1eEH0UOQpk9Xgsu",
    "xkZDTrLXGioD2ajPrKTBdHon",
    "TiNWpHzFPO25W7a94dEwS0yX",
    "6r6w6wFKiao9626G09UNKS8O"
]


def __get_ak():
    return AK_BUFFER[randint(0, len(AK_BUFFER) - 1)]


def get_location_coordinates(location):
    """
    通过百度地图的API接口，将某个地址转换成经纬度坐标
    详情见：http://developer.baidu.com/map/webservice-placeapi.htm
    中的“5.2 Place检索示例”小节
    """
    address = "{city} {district} {street}".format(**location)
    precise, confidence, lng, lat = _get_coord(address)
    if not lat:
        address = "{city} {district}".format(**location)
        precise, confidence, lng, lat = _get_coord(address)

    return precise, confidence, lng, lat


def _get_coord(address):
    # 优先从redis取
    redis = Redis()
    ret = redis.get(address)
    if ret:
        ret = literal_eval(ret)
        # print ("[%s] [%s] [%s] [%s,%s]" % (address, ret[0], ret[1], ret[2], ret[3]))
        return ret[0], ret[1], ret[2], ret[3]

    # 没有,再从baidu取
    url = r"http://api.map.baidu.com/geocoder/v2/"
    params = {
        "ak": __get_ak(),
        "output": "json",
        "address": address,
    }
    response = requests.get(url, params=params)
    baidu_data = json.loads(response.content)

    # 百度地图返回status为0时才正确
    latitude, longitude = (None, None)
    if baidu_data.get("status", -1) == 0:
        location = baidu_data.get("result").get("location")
        latitude = location.get("lat")
        longitude = location.get("lng")
        result = baidu_data.get("result")
        print ("[%s] [%s] [%s] [%s,%s] [%s]" % (
        address, result['precise'], result['confidence'], longitude, latitude, result['level'].encode('utf-8')))
        redis.setex(address, [result['precise'], result['confidence'], longitude, latitude], 60 * 60 * 24)
        return result['precise'], result['confidence'], longitude, latitude
    else:
        return None, None, longitude, latitude


def reverse_location_parse(lat=0, lng=0):
    """
    逆地理编码服务, 将经纬度解析成中文地址
    文档地址: http://developer.baidu.com/map/index.php?title=webapi/guide/webservice-geocoding
    :return:
    """
    assert lat > 0 and lng > 0
    url = r"http://api.map.baidu.com/geocoder/v2/"
    params = {
        "ak": __get_ak(),
        "output": "json",
        "location": "%s,%s" % (lat, lng),
        "pois": 0,  # 是否现实指定位置周彪的poi,0为不显示
    }
    response = requests.get(url, params=params)
    result = json.loads(response.content)
    location = {
        "return_status": -1,
        "address": "",
        "province": "",
        "city": "",
        "district": "",
        "street": "",
    }
    # pprint(result)
    # 返回status为0时才正确
    if result.get("status", -1) == 0:
        location['return_status'] = 0
        address_component = result['result']['addressComponent']
        location['address'] = result['result'].get('formatted_address', '')
        location['province'] = address_component.get('province', '')
        location['city'] = address_component.get('city', '')
        location['district'] = address_component.get('district', '')
        location['street'] = address_component.get('street', '') + address_component.get('street_number', '')
    return location


def get_distance(from_latitude, from_longitude, to_latitude, to_longitude, region, origin_region, destination_region,
                 mode='walking'):
    """
    调用百度API获取不同模式下的距离
    百度API文档地址: http://developer.baidu.com/map/index.php?title=webapi/direction-api
    :param from_latitude:
    :param from_longitude:
    :param to_latitude:
    :param to_longitude:
    :param region:
    :param origin_region:
    :param destination_region:
    :param mode: 支持 walking(步行) / driving(驾车) / transit(公交)
    :return:
    """
    url = "http://api.map.baidu.com/direction/v1"
    params = {
        "mode": mode,
        "origin": ",".join([str(from_latitude), str(from_longitude)]),
        "destination": ",".join([str(to_latitude), str(to_longitude)]),
        "region": region,
        "origin_region": origin_region,
        "destination_region": destination_region,
        "output": "json",
        "ak": __get_ak()
    }
    try:
        time.sleep(0.1)
        r = requests.get(url, params=params, timeout=0.5)
        response = json.loads(r.content)
        if response['status'] == 0:
            return response['result']['routes'][0]['distance']
        else:
            return 0
    except Timeout:
        return 0
    except Exception:
        print traceback.format_exc()
        return 0


def get_address(longitude, latitude):
    """
    根据经纬度，返回省、市、区、街道地址
    :param longitude:
    :param latitude:
    :return:
            {
                "city": "北京市",
                "country": "中国",
                "direction": "附近",
                "distance": "7",
                "district": "海淀区",
                "province": "北京市",
                "street": "中关村大街",
                "street_number": "27号1101-08室",
                "country_code": 0
            }


    """
    url = r'http://api.map.baidu.com/geocoder/v2/'
    params = {
        "ak": __get_ak(),
        "location": ",".join([str(latitude), str(longitude)]),
        "output": "json"
    }
    try:
        time.sleep(0.1)
        r = requests.get(url, params=params, timeout=0.5)
        response = json.loads(r.content)
        if response['status'] == 0:
            return response['result']['addressComponent']
        else:
            return None
    except Timeout:
        return None
    except Exception:
        return None


if __name__ == '__main__':
    lat, lng = get_location_coordinates(dict(city="杭州市", district="", street="万塘路258号杭州师范大学"))
    print ("%s, %s" % (lng, lat))
    lat, lng = get_location_coordinates(dict(city="杭州市", district="西湖区", street="万塘路258号杭州师范大学"))
    print ("%s, %s" % (lng, lat))
    lat, lng = get_location_coordinates(dict(city="杭州市", district="西湖区", street="万塘路258号"))
    print ("%s, %s" % (lng, lat))
