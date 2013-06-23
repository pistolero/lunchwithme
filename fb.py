import requests


def notify_user(user_id, template):
    from app import app

    params = {
        'access_token': app.config['FACEBOOK_APP_TOKEN'],
        'template': template
    }

    requests.post('https://graph.facebook.com/%s/notifications' % user_id, params=params)
