import json
import requests

def get_places(pos):
    params = {
        'll': ','.join(str(x) for x in pos),
        'client_id': 'MCFO0VPVGBVD0VBEY3DER2SWXLO1XJMEMGLNCIKHXWH1ZRW5',
        'client_secret': 'BXCL4IJSIGW1NABGZAWZKG3GXSVXBNEBQJE31QBBZHTQSIV3',
        'v': '20130623',
        'intent': 'browse',
        'radius': '1000',
        'categoryId': '4d4b7105d754a06374d81259',
        'limit': '50'
    }
    resp = requests.get('https://api.foursquare.com/v2/venues/search', params=params)
    return resp.json()['response']['venues']



_category_by_id = {}


def category_by_id(category_id):
    return _category_by_id[category_id]


def init_categories():
    response = json.load(open('categories.json', 'r'))
    # params = {
    #     'client_id': 'MCFO0VPVGBVD0VBEY3DER2SWXLO1XJMEMGLNCIKHXWH1ZRW5',
    #     'client_secret': 'BXCL4IJSIGW1NABGZAWZKG3GXSVXBNEBQJE31QBBZHTQSIV3',
    #     'v': '20130623',
    # }
    # resp = requests.get('https://api.foursquare.com/v2/venues/categories', params=params)

    def process_cat(obj):
        _category_by_id[obj['id']] = {'id': obj['id'], 'name': obj['name']}

        for c in obj.get('categories', []):
            process_cat(c)

    # resp.json()
    for c in response['response']['categories']:
        process_cat(c)
