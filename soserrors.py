import os
from google.appengine.ext.webapp import template
import datetime
import time
from datetime import date
from datetime import datetime, date, time, timedelta
import cgi
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import mail

class SOSException(Exception):

    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return self.parameter
    

class SOSLoginException(Exception):

    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return self.parameter


