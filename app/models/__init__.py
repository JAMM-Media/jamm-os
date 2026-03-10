# app/models/__init__.py
# Import order matters here: Firm must come first because every other
# model has a foreign key pointing to it. Python needs to see the Firm
# class definition before models that reference it.
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.contact import Contact