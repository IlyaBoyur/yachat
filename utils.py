import json
from datetime import datetime

import pytz

from db import DbEncoder
from settings import DEFAULT_TZ


def serialize(data: dict) -> str:
    return json.dumps(data, indent=2, cls=DbEncoder)


def now() -> datetime:
    return pytz.timezone(DEFAULT_TZ).localize(datetime.now())
