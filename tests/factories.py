import factory.fuzzy


from db import Message, Chat, Complaint
from constants import ChatType


class MessageFactory(factory.Factory):
    id = factory.Faker("uuid4")
    created = factory.Faker("date_time")
    author = factory.Faker("uuid4")
    text = factory.Faker("text")
    is_comment_on = factory.Faker("uuid4")

    class Meta:
        model = Message


class ChatFactory(factory.Factory):
    id = factory.Faker("uuid4")
    name = factory.Faker("word")

    class Meta:
        model = Chat


class ComplaintFactory(factory.Factory):
    id = factory.Faker("uuid4")
    author = factory.Faker("uuid4")
    created = factory.Faker("date_time")
    reported_user = factory.Faker("uuid4")
    reason = factory.Faker("word")
    reviewed: bool = False

    class Meta:
        model = Complaint
