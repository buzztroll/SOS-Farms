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
from sosdata import UsersWaitingList2
from sosdata import UsersData
from sosdata import InventoryList
from sosdata import Item
from sosdata import UserPO
from soserrors import SOSException
import sosdata
from google.appengine.api import datastore_errors
import logging
import traceback

# admin code
class AdminRootPage(webapp.RequestHandler):

    def get_harvest_date(self, harvest_date):
        target_day = 3 # weds

        if harvest_date == None or harvest_date == "":
            now = date.today()
            wd = now.weekday()
            day_diff = target_day - wd
            if day_diff < 0:
                day_diff = day_diff + 6

            td = timedelta(day_diff)

            harvest_date = now + td
        else:
            harvest_date = datetime.strptime(harvest_date, "%Y-%m-%d")

        return harvest_date

    def verify_admin(self):
        if users.get_current_user():
            self.url = users.create_logout_url("/")
            self.url_linktext = 'Logout'
        else:
            self.url = users.create_login_url("/")
            self.url_linktext = 'Login'
            raise SOSException("You must login")
        if users.is_current_user_admin():
            pass
        else:
            user = users.get_current_user()
            msg = user.email() + " is not authorized for this"
            raise SOSException(msg)

    def error_write(self, ex, tb=None):
        template_values = {
            'error_msg': str(ex),
            'logout_url': self.url,
            'url_linktext': self.url_linktext,
          }
        if tb != None:
            msg = tb.format_exc()
            logging.error("Error TB %s", (msg))
        logging.error("and exception occurred %s", (str(ex)))
        path = os.path.join(os.path.dirname(__file__), 'error.html')
        self.response.out.write(template.render(path, template_values))

