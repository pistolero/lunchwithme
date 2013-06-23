import math
import datetime
from flask_mongoengine import MongoEngine
db = MongoEngine()

from haversine import haversine


class Friend(db.EmbeddedDocument):
    first_name = db.StringField()
    last_name = db.StringField()    
    picture_url = db.StringField()
    link = db.StringField()

    def __eq__(self, other):
        return self.first_name == other.first_name and self.last_name == other.last_name

    def __hash__(self):
        return hash(self.first_name)


class Interest(db.EmbeddedDocument):
    name = db.StringField()
    typ = db.StringField()
    picture_url = db.StringField()

    def __eq__(self, other):
        return self.typ == other.typ and self.name == other.name

    def __hash__(self):
        return hash(self.name)


class Venue(db.Document):
    fs_id = db.StringField()
    location = db.GeoPointField()
    name = db.StringField()
    category = db.StringField()


class User(db.Document):
    fb_id = db.StringField()
    fb_token = db.StringField()
    first_name = db.StringField()
    last_name = db.StringField()    
    email = db.StringField()
    gender = db.StringField()
    picture_url = db.StringField()
    location = db.GeoPointField()
    interests = db.ListField(db.EmbeddedDocumentField(Interest))
    activities = db.ListField(db.StringField())
    friends = db.ListField(db.EmbeddedDocumentField(Friend))
    lunch_days = db.ListField(db.IntField())
    lunch_start = db.IntField()
    lunch_end = db.IntField()    
    venues = db.ListField(db.ReferenceField(Venue))

    @property
    def full_name(self):
        return '%s %s' % (self.first_name, self.last_name)


class Offer(db.Document):
    initiator = db.ReferenceField(User)
    party = db.ReferenceField(User)
    venue = db.ReferenceField(Venue)
    time = db.StringField()
    accepted = db.BooleanField(default=False)
    expired = db.BooleanField(default=False)
    created_at = db.DateTimeField(default=datetime.datetime.now)


def find_match(user):
    max_distance = 1000  # 100000 km
    #proposed = User.objects(point__geo_within_center=user.location, 1000)
    users_nearby = User.objects(location__near=user.location, location__max_distance=max_distance)

    def score(proposed):
        # friends intersection
        common_friends = set(user.friends).intersection(proposed.friends)

        # interests intersection
        common_interests = set(user.interests).intersection(proposed.interests)

        # distance
        distance = haversine((user.location[0], user.location[1]), (proposed.location[0], proposed.location[1]))

        score = -(distance/max_distance)
        if common_friends:
            score += math.log(len(common_friends))

        if common_interests:
            score += math.log10(len(common_interests))

        return {
            'user': proposed,
            'common_friends': list(common_friends),
            'common_interests': list(common_interests),
            'distance': int(round(distance*1000)),
            'score': score
        }

    users_nearby = [score(x) for x in users_nearby if x != user]
    users_nearby.sort(key=lambda x: x['score'], reverse=True)

    return users_nearby[:20]
