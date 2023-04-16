import json
import pytz
from datetime import datetime

from db import DbEncoder

from settings import DEFAULT_TZ


def serialize(data: dict) -> str:
    return json.dumps(data, indent=2, cls=DbEncoder)


def now() -> datetime:
    return pytz.timezone(DEFAULT_TZ).localize(datetime.now())
