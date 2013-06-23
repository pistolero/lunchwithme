# -*- coding: utf-8 -*-

import cgi
import logging
import base64
import os
import os.path
import urllib
import hmac
import json
import hashlib
from base64 import urlsafe_b64decode, urlsafe_b64encode

import requests
from flask import Flask, request, redirect, render_template, url_for, session, Response, g, jsonify

from bson.objectid import ObjectId

FB_APP_ID = os.environ.get('FACEBOOK_APP_ID')
requests = requests.session()

app_url = 'https://graph.facebook.com/{0}'.format(FB_APP_ID)
FB_APP_NAME = json.loads(requests.get(app_url).content).get('name')
FB_APP_SECRET = os.environ.get('FACEBOOK_SECRET')


def oauth_login_url(preserve_path=True, next_url=None):
    fb_login_uri = ("https://www.facebook.com/dialog/oauth"
                    "?client_id=%s&redirect_uri=%s" %
                    (app.config['FB_APP_ID'], get_home()))

    if app.config['FBAPI_SCOPE']:
        fb_login_uri += "&scope=%s" % ",".join(app.config['FBAPI_SCOPE'])
    return fb_login_uri


def simple_dict_serialisation(params):
    return "&".join(map(lambda k: "%s=%s" % (k, params[k]), params.keys()))


def base64_url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip('=')


def fbapi_get_string(
                path,
                domain=u'graph', 
                params=None, 
                access_token=None,
                encode_func=urllib.urlencode):
    """Make an API call"""

    if not params:
        params = {}
    params[u'method'] = u'GET'
    if access_token:
        params[u'access_token'] = access_token

    for k, v in params.iteritems():
        if hasattr(v, 'encode'):
            params[k] = v.encode('utf-8')

    url = u'https://' + domain + u'.facebook.com' + path
    params_encoded = encode_func(params)
    url = url + params_encoded
    result = requests.get(url).content

    return result


def fbapi_auth(code):
    params = {'client_id': app.config['FB_APP_ID'],
              'redirect_uri': get_home(),
              'client_secret': app.config['FB_APP_SECRET'],
              'code': code}

    result = fbapi_get_string(path=u"/oauth/access_token?", params=params,
                              encode_func=simple_dict_serialisation)
    pairs = result.split("&", 1)
    result_dict = {}
    for pair in pairs:
        (key, value) = pair.split("=")
        result_dict[key] = value
    return (result_dict["access_token"], result_dict["expires"])


def fbapi_get_application_access_token(id):
    token = fbapi_get_string(
        path=u"/oauth/access_token",
        params=dict(grant_type=u'client_credentials', client_id=id,
                    client_secret=app.config['FB_APP_SECRET']),
        domain=u'graph')

    token = token.split('=')[-1]
    if not str(id) in token:
        print 'Token mismatch: %s not in %s' % (id, token)
    return token


def fql(fql, token, args=None):
    if not args:
        args = {}

    args["query"], args["format"], args["access_token"] = fql, "json", token

    url = "https://api.facebook.com/method/fql.query"

    r = requests.get(url, params=args)
    return json.loads(r.content)


def fb_call(call, args=None, as_json=True):
    url = "https://graph.facebook.com/{0}".format(call)
    r = requests.get(url, params=args)
    if as_json:
        return json.loads(r.content)
    else:
        return cgi.parse_qs(r.content)



app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_object('conf.Config')

from flask_heroku import Heroku
heroku = Heroku(app)

from db import *

app.config['MONGODB_USERNAME'] = app.config['MONGODB_USER']
db.init_app(app)

def get_home():
    return 'https://' + request.host + '/'


def get_token():
    if request.args.get('code', None):
        return fbapi_auth(request.args.get('code'))[0]

    cookie_key = 'fbsr_{0}'.format(FB_APP_ID)

    if cookie_key in request.cookies:

        c = request.cookies.get(cookie_key)
        encoded_data = c.split('.', 2)

        sig = encoded_data[0]
        data = json.loads(urlsafe_b64decode(str(encoded_data[1]) +
            (64-len(encoded_data[1])%64)*"="))

        if not data['algorithm'].upper() == 'HMAC-SHA256':
            raise ValueError('unknown algorithm {0}'.format(data['algorithm']))

        h = hmac.new(FB_APP_SECRET, digestmod=hashlib.sha256)
        h.update(encoded_data[1])
        expected_sig = urlsafe_b64encode(h.digest()).replace('=', '')

        if sig != expected_sig:
            raise ValueError('bad signature')

        code =  data['code']

        params = {
            'client_id': FB_APP_ID,
            'client_secret': FB_APP_SECRET,
            'redirect_uri': '',
            'code': data['code']
        }

        from urlparse import parse_qs
        r = requests.get('https://graph.facebook.com/oauth/access_token', params=params)
        token = parse_qs(r.content).get('access_token')

        return token


def exchange_token(access_token):
    tok = fb_call('oauth/access_token', {'client_id': FB_APP_ID, 'client_secret': FB_APP_SECRET, 'grant_type': 'fb_exchange_token', 'fb_exchange_token': access_token}, as_json=False)
    if tok:
        return tok['access_token'], tok['expires']
    raise RuntimeError('invalid token')


@app.route('/api/saveSessionData/', methods=['POST'])
def me():
    session['session_data'] = request.json

    return ''


@app.route('/api/venues/<pos>', methods=['GET'])
def venues(pos):
    from places import get_places

    places = get_places(pos.split(','))

    for place in places:
        venue = Venue.objects(fs_id=place['id']).first()
        if venue is None:
            venue = Venue(fs_id=place['id'])
        venue.name = place['name']
        venue.category = place['categories'][0]['name']

        venue.save()

    return jsonify(venues=places)


@app.route('/api/offer/', methods=['POST'])
def create_offer():
    user_id = request.form['user_id']
    venue_id = request.form['venue_id']
    time = request.form['time']

    user = User.objects.get(fb_id=user_id)
    venue = Venue.objects.get(fs_id=venue_id)

    offer = Offer(initiator=g.user, party=user, venue=venue, time=time).save()

    # send notification here
    from notifications import send_notification
    send_notification(user.full_name, user.email, 'lunch-offer', {
                      'FNAME': user.first_name, 
                      'PARTYNAME': '%s %s.' % (g.user.first_name, g.user.last_name[0]), 
                      'VENUENAME': venue.name, 
                      'TIME': time, 
                      'ANSWERURL': get_home()})

    return jsonify(offer_id=str(offer.id))


@app.route('/api/offer/<offer_id>/accept/', methods=['POST'])
def accept_offer(offer_id):
    offer = Offer.objects.get(id=ObjectId(offer_id))

    offer.accepted = True
    offer.save()

    # # expire other offers
    # for eoffer in Offer.objects(party=offer.initiator):
    #     eoffer.expired = True
    #     # send expired notification here
    # for eoffer in Offer.objects()

    # send notification here
    from notifications import send_notification
    send_notification(offer.party.full_name, g.user.email, 'offer-accepted', {
                      'FNAME': offer.party.first_name, 
                      'PARTYNAME': '%s %s.' % (g.user.first_name, g.user.last_name[0]), 
                      'VENUENAME': offer.venue.name, 
                      'TIME': offer.time, 
                      'ANSWERURL': get_home()})    

    return jsonify()


def read_all(access_token, data_list, fields):
    if not data_list:
        return

    while True:
        for f in data_list['data']:
            yield f
        paging = data_list.get('paging')
        if paging and 'next' in paging:
            next = paging['next'][len('https://graph.facebook.com/'):]
            data_list = fb_call(next, args={'access_token': access_token, 'fields': fields})
        else:
            break


# if user in session:
## logged in
# else
## if token:
# get user info, save


@app.before_request
def do_auth():
    logging.error(session)
    user_id = session.get('uid')
    if user_id:
        g.user = User.objects(fb_id=user_id).first()
    else:
        g.user = None

    g.access_token = request.cookies.get('tok')

    if request.headers.get('X-Forwarded-Proto', 'http') == 'http' and app.config.get('HTTPS_ONLY') == '1':
        return redirect(request.url.replace('http://', 'https://'))


@app.route('/logout/', methods=['GET'])
def logout():
    session.pop('uid', None)
    session.pop('tok', None)

    return redirect('/')


@app.route('/login/', methods=['GET'])
def login():
    access_token = get_token()
    if not access_token:
        return redirect('/')

    logging.info('Short access token %s' % access_token)

    try:
        access_token, expires = exchange_token(access_token)
    except RuntimeError:
        return redirect('/')


    fields = [
        'picture',
        'first_name',
        'last_name',
        'gender',
        'email',
        'friends.fields(first_name, last_name,gender,email,picture)',
        'books.fields(id,name,picture)',
        'movies.fields(id,name,picture)',
        'games.fields(id,name,picture)',
        'music.fields(id,name,picture)',
        'television.fields(id,name,picture)',
    ]

    me = fb_call('me', args={'access_token': access_token, 'fields': ','.join(fields)})

    error = me.get('error')
    if error:
        logging.warn("Got error from Facebook. Clearing auth and refreshing page. %r" % error)
        resp = redirect('/') 
        resp.set_cookie('tok', '', expires=0)
        return resp


    user = User.objects.filter(fb_id=me['id']).first()
    if user is None:
        user = User(fb_id=me['id'])

    user.first_name = me.get('first_name')
    user.last_name = me.get('last_name')
    user.gender = me.get('gender')
    user.email = me.get('email')

    user.picture_url = me['picture']['data']['url']

    user.friends = []
    for f in read_all(access_token, me.get('friends'), 'first_name,last_name,gender,email,picture'):
        user.friends.append(Friend(
                            first_name=f.get('first_name', ''),
                            last_name=f.get('last_name', ''),
                            picture_url=f['picture']['data']['url']
                            ))

    user.interests = []
    for interest_type in ['books', 'movies', 'games', 'music', 'television']:
        for i in read_all(access_token, me.get(interest_type), fields='name,picture'):
            user.interests.append(Interest(
                                  name=i['name'],
                                  typ=interest_type,
                                  picture_url=i['picture']['data']['url']
                                ))

    pos = session['session_data']['position']
    venues = session['session_data']['venues']
    user.location = pos
    user.venues = [Venue.objects.get(fs_id=vid) for vid in venues]
    logging.error('Venues: %r', user.venues)

    user.save()

    session['uid'] = str(user.fb_id)

    resp = redirect('/')
    resp.set_cookie('tok', access_token[0], max_age=int(expires[0]))

    return resp


#?ids=496448887050192,134692046590865&fields=name,picture

@app.route('/', methods=['GET', 'POST'])
def index():
    # print get_home()

    logging.error('user:%r' % g.user)


    # expires = None
    # if request.cookies.get('tok'):
    #     logging.info('Returned long token')
    #     access_token = request.cookies.get('tok')
    # else:
    #     access_token = get_token()
    #     logging.info('Short access token %s' % access_token)
    #     try:
    #         access_token, expires = exchange_token(access_token)
    #     except RuntimeError:
    #         access_token = None

    channel_url = url_for('get_channel', _external=True)
    channel_url = channel_url.replace('http:', '').replace('https:', '')

    if g.user:
        match = find_match(g.user)

        offers = Offer.objects(party=g.user, expired=False)  #, created_at__gte=datetime.datetime.now().replace(hour=0,minute=0, second=0))

        resp = Response(render_template(
            'index.html', 
            app_id=FB_APP_ID, 
            token=g.access_token, 
            # likes=likes,
            # friends=friends, 
            # photos=photos, 
            # app_friends=app_friends, 
            #app=fb_app,
            me=me, 
            matched_users=match,
            offers=offers,
            # POST_TO_WALL=POST_TO_WALL, 
            # SEND_TO=SEND_TO, url=url,
            channel_url=channel_url, 
            name=FB_APP_NAME))

        return resp
    else:
        return render_template('login.html', app_id=FB_APP_ID, token=g.access_token, url=request.url, channel_url=channel_url, name=FB_APP_NAME)

@app.route('/channel.html', methods=['GET', 'POST'])
def get_channel():
    return render_template('channel.html')


@app.route('/close/', methods=['GET', 'POST'])
def close():
    return render_template('close.html')

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    port = int(os.environ.get("PORT", 5000))
    app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

    from places import init_categories
    init_categories()

    if app.config.get('FB_APP_ID') and app.config.get('FB_APP_SECRET'):
        app.run(host='0.0.0.0', port=port)
    else:
        print 'Cannot start application without Facebook App Id and Secret set'
