import requests
import json
import logging

def send_notification(recipient_name, recipient_email, tpl_id, data):
    from lunchapp import app

    merge_vars = [{'name': key, 'content': val} for key, val in data.iteritems()]
    req = {
        "key": "LG0ZEwEEFHoJKckOy4BIbA",
        "template_name": tpl_id,
        "template_content": merge_vars,        
        "message": {
            "to": [
                {
                    "email": recipient_email,
                    "name": recipient_name
                }
            ],
            "important": True,
            "track_opens": True,
            "track_clicks": True,
            "auto_text": None,
            "inline_css": None,
            "bcc_address": "sergey.kirillov@gmail.com",
            "merge": True,
            "global_merge_vars": merge_vars
    #        "tracking_domain": null,
    #        "signing_domain": null,
        }
    }
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    r = requests.post('https://mandrillapp.com/api/1.0/messages/send-template.json', data=json.dumps(req), headers=headers)

    logging.error('Notifcation result: %r' % r.json())
