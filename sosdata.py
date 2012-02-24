import os
from google.appengine.ext.webapp import template
import datetime
import time
from datetime import date
from datetime import datetime, date, time, timedelta
import cgi
from google.appengine.api import users
from google.appengine.api import datastore_errors
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import mail

def sos_get_tax_rate():
    return 0.0416

class Harvest(db.Model):
    date = db.DateTimeProperty(auto_now_add=False)

class UsersData(db.Model):
    email = db.StringProperty(multiline=False, required=True)
    address = db.StringProperty(multiline=False)
    phone = db.StringProperty(multiline=False)
    zip = db.StringProperty(multiline=False)
    firstname = db.StringProperty(multiline=False)
    lastname = db.StringProperty(multiline=False)
    city = db.StringProperty(multiline=False)
    date = db.DateTimeProperty(auto_now_add=True)
    id = db.StringProperty(multiline=False, required=True)

class UsersWaitingList2(db.Model):
    email = db.StringProperty(multiline=False)
    address = db.StringProperty(multiline=False)
    phone = db.StringProperty(multiline=False)
    zip = db.StringProperty(multiline=False)
    firstname = db.StringProperty(multiline=False)
    lastname = db.StringProperty(multiline=False)
    date = db.DateTimeProperty(auto_now_add=True)
    id = db.StringProperty(multiline=False, required=True)

class InventoryList(db.Model):
    date = db.DateTimeProperty()
    item_count = db.IntegerProperty()
    locked = db.IntegerProperty()
    id = db.StringProperty(multiline=False)

class Item(db.Model):
    name = db.StringProperty(multiline=False)
    anotation = db.StringProperty(multiline=False)
    date = db.DateTimeProperty(auto_now_add=False)
    quantity_int = db.IntegerProperty()
    quantity = db.StringProperty()
    remaining = db.StringProperty()
    remaining_int = db.IntegerProperty()
    cost = db.StringProperty()
    cost_float = db.FloatProperty()
    id = db.StringProperty(multiline=False, required=True)

class UserChoices(db.Model):
    item = db.ReferenceProperty(Item)
    user = db.ReferenceProperty(UsersData, required=True)

    date = db.DateTimeProperty(auto_now_add=False)
    quantity_int = db.IntegerProperty()
    quantity = db.StringProperty(indexed=True)
    charge_float = db.FloatProperty()
    charge = db.StringProperty(indexed=True)

    purchased = db.IntegerProperty()
    id = db.StringProperty(multiline=False)

class UserPO:

    def __init__(self, user, harvest_date, items):
        self.user_info = user
        self.harvest_date = harvest_date

        choice_query = UserChoices.all()
        choice_query.filter('date = ', self.harvest_date)
        choice_query.filter('user = ', self.user_info)
        choice_query.filter('quantity_int > ', 0)
        choice_query.filter('purchased = ', 1)
#        choice_query.order('quantity_int')
#        choice_query.order('item')
        self.user_choices = choice_query.fetch(5000)

        self.quat_list = self.get_quant_lists(items)

        self.sub_total_charge = self.get_total()
        self.tax = sos_get_tax_rate() * self.sub_total_charge
        self.total_charge = self.sub_total_charge + self.tax

        self.sub_total_charge_str = "%6.2f" % (round(self.sub_total_charge, 2))
        self.tax_str = "%6.2f" % (round(self.tax, 2))
        self.total_charge_str = "%6.2f" % (round(self.total_charge, 2))


    def get_total(self):
        total = 0.0
        for uc in self.user_choices:
            if uc.item != None:
                total = total + float(uc.charge)
        return total

    def get_choices(self):
        return self.user_choices

    def get_quant_lists(self, items):
        quant_list = []

        for item in items:
            found = False
            for c in self.user_choices:

                try:
                    if c.item != None:
                        id = c.item.id
                except datastore_errors.Error, e:
                    if e.args[0] == "ReferenceProperty failed to be resolved":
                        c.item = None
                        c.put()
                    else:
                        raise

                if c.item == None:
                    pass
                else:
                    if c.item.id == item.id and found == False:
                        quant_list.append(int(c.quantity))
                        found = True

            if found == False:
                quant_list.append(0)

        return quant_list

    def add_quants(self, total_quant_list):
        for i in range(0, len(total_quant_list)):
            total_quant_list[i] = total_quant_list[i] + self.quat_list[i]



