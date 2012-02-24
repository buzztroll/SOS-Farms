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
from sosdata import UserChoices
from sosdata import UsersData
from sosdata import InventoryList
from sosdata import Item
from sosdata import UserPO
from soserrors import SOSException
import sosdata
import soscommon
from soscommon import AdminRootPage
from sosuserpages import UserRootPage
from sosuserpages import WaitingList
from sosuserpages import Register
import sos_uuid as uuid
from google.appengine.api import datastore_errors
import logging
import traceback

class MainPage(webapp.RequestHandler):

    def get(self):

        url = None
        url_linktext = None
        try:
            if users.get_current_user():
                url = users.create_logout_url("/")
                url_linktext = 'Logout'

                if users.is_current_user_admin():
                    self.redirect('/admin')
                else:
                    user = users.get_current_user()
                    email = user.email()
                    users_query = UsersData.all()
                    users_query.filter('email = ', email)
                    g_us = users_query.fetch(1)

                    if len(g_us) < 1:
                        error_msg = "You are not authorized to use this service.  You are currently logged into google as: |%s|.  Please verify that this is the user name known to SOS farms" % (email)
                        logging.error("user |%s| attempted to login and failed" % (email))
                        raise SOSException(error_msg)
                    self.redirect('/choices')
            else:
                url = users.create_login_url("/")
                url_linktext = 'Login'
                raise SOSException("Please login")


        except Exception, ex:
            template_values = {
              'error_msg': str(ex),
              'logout_url': url,
              'url_linktext': url_linktext,
             }

            path = os.path.join(os.path.dirname(__file__), 'error.html')
            self.response.out.write(template.render(path, template_values))

#
#
#
class Harvest(AdminRootPage):

    def get(self):
        try:
            self.verify_admin()
            self.do_page()
        except Exception, ex:
            #self.error_write(ex)
            raise

    def post(self):
        try:
            self.verify_admin()

            button_type = self.request.get('button')

            if button_type == "Lock":
                harvest_date = self.request.get('weekof')
                harvest_date = self.get_harvest_date(harvest_date)

                inv_query = InventoryList.all()
                inv_query.filter('date = ', harvest_date)
                inv = inv_query.fetch(1)
                if inv != None and len(inv) > 0:
                    inv[0].locked = 1
                    inv[0].put()
            elif button_type == "Unlock":
                harvest_date = self.request.get('weekof')
                harvest_date = self.get_harvest_date(harvest_date)

                inv_query = InventoryList.all()
                inv_query.filter('date = ', harvest_date)
                inv = inv_query.fetch(1)
                if inv != None and len(inv) > 0:
                    inv[0].locked = 0
                    inv[0].put()
            elif button_type == "Printable":
                self.do_page(fname="harvestprintable.html")
                return
            elif button_type == "CSV":
                self.do_page(fname="harvestcsv.html")
                return

            self.do_page()
        except Exception, ex:
            #self.error_write(ex)
            raise

    def get_all_users(self):
        users_query = UsersData.all()
        g_us = users_query.fetch(1000)
        return g_us


    def do_page(self, fname='harvest.html'):
        harvest_date = self.request.get('weekof')
        harvest_date = self.get_harvest_date(harvest_date)

        inv_query = InventoryList.all()
        inv_query.filter('date = ', harvest_date)
        inv = inv_query.fetch(1000)
        locked_or_not = "unlocked"
        if inv != None and len(inv) > 0 and inv[0].locked == 1:
            locked_or_not = "locked"

        item_query = Item.all()
        item_query.filter('date = ', harvest_date)
        item_query.order('name')
        items = item_query.fetch(1000)
        totals = []
        for i in items:
            totals.append(0)

        total_collect = 0.0
        user_purchase_orders = []
        users = self.get_all_users()
        for user in users:
            user_po = UserPO(user, harvest_date, items)
            if user_po.sub_total_charge > 0:
                user_purchase_orders.append(user_po)
                user_po.add_quants(totals)
                total_collect = total_collect + user_po.total_charge

        # trim out items that no one wanted
        # ---- find all the 0 index
        zero_ndxs = []
        for j in range(0, len(items)):
            i = len(items) - j - 1
            total = 0
            for po in user_purchase_orders:
                if len(items) != len(po.quat_list):
                    raise Exception("trouble")
                total = total + po.quat_list[i]
            if total == 0:
                logging.info("removing index %d" %(i))
                zero_ndxs.append(i)
        # ---- remove all of the xero indexs
        for i in zero_ndxs:
            items.pop(i)
            totals.pop(i)
            for po in user_purchase_orders:
                po.quat_list.pop(i)

        harvest_date_str = harvest_date.strftime("%Y-%m-%d")
        template_values = {
            'harvest_date': harvest_date_str,
            'list_header': items,
            'locked_or_not': locked_or_not,
            'user_pos': user_purchase_orders,
            'logout_url': self.url,
            'totals': totals,
            'total_collect':total_collect,
            'url_linktext': self.url_linktext,
          }
        path = os.path.join(os.path.dirname(__file__), fname)
        self.response.out.write(template.render(path, template_values))

class Invoice(AdminRootPage):

    def get(self):
        try:
            self.verify_admin()
            self.do_page()
        except Exception, ex:
            #self.error_write(ex)
            raise

    def post(self):
        try:
            self.verify_admin()

            harvest_date = self.request.get('weekof')
            harvest_date = self.get_harvest_date(harvest_date)
            button_type = self.request.get('button')

            if button_type == "Printable":
                fname="invoiceprintable.html"
            elif button_type == "CSV":
                fname="invoicecsv.html"
            else:
                fname='invoice.html'

            self.do_page(fname=fname)
        except Exception, ex:
            #self.error_write(ex)
            raise

    def get_all_users(self):
        users_query = UsersData.all()
        g_us = users_query.fetch(1000)
        return g_us


    def do_page(self, fname="invoice.html"):
        harvest_date = self.request.get('weekof')
        harvest_date = self.get_harvest_date(harvest_date)

        inv_query = InventoryList.all()
        inv_query.filter('date = ', harvest_date)
        inv = inv_query.fetch(1000)
        locked_or_not = "unlocked"
        if inv != None and len(inv) > 0 and inv[0].locked == 1:
            locked_or_not = "locked"

        item_query = Item.all()
        item_query.filter('date = ', harvest_date)
        item_query.order('name')
        items = item_query.fetch(1000)
        totals = []
        for i in items:
            totals.append(0)

        user_purchase_orders = []
        users = self.get_all_users()
        for user in users:
            user_po = UserPO(user, harvest_date, items)
            if user_po.sub_total_charge > 0:
                user_purchase_orders.append(user_po)
                user_po.add_quants(totals)

        harvest_date_str = harvest_date.strftime("%Y-%m-%d")
        template_values = {
            'harvest_date': harvest_date_str,
            'user_pos': user_purchase_orders,
            'logout_url': self.url,
            'url_linktext': self.url_linktext,
          }
        path = os.path.join(os.path.dirname(__file__), fname)
        self.response.out.write(template.render(path, template_values))



class Admin(AdminRootPage):

    def get(self):
        self.do_page()
    def post(self):
        self.do_page()

    def do_page(self):
        try:
            self.verify_admin()

            template_values = {
                'logout_url': self.url,
                'url_linktext': self.url_linktext,
              }

            path = os.path.join(os.path.dirname(__file__), 'admin.html')
            self.response.out.write(template.render(path, template_values))
        except Exception, ex:   
            self.error_write(ex)


class Sure(AdminRootPage):

    def get(self):
        self.do_page()

    def nuke_query(self, query):
        items = query.fetch(1000)
        for i in items:
            i.id = str(uuid.uuid1())
            i.put()

    def convert_wait(self):
        query = UsersWaitingList.all()
        items = query.fetch(1000)

        for w in items:
            user = UsersWaitingList2(id=str(uuid.uuid1()))
            user.email = w.email
            user.firstname = w.firstname
            user.lastname = w.lastname
            user.address = w.address
            user.phone = w.phone
            user.zip = w.zip
            user.put()

            w.delete()

            print user



    def post(self):
        try:
            self.verify_admin()

            button_type = self.request.get('button')

            all = False
            if button_type == "Nuke":
                all = True

            if button_type == "UserChoices" or all == True:
                query = UserChoices.all()
                self.nuke_query(query)
            if button_type == "UserData" or all == True:
                query = UsersData.all()
                self.nuke_query(query)
            if button_type == "UserWaitingList" or all == True:
#                query = UsersWaitingList.all()
#                self.nuke_query(query)
                self.convert_wait()
            if button_type == "InventoryList" or all == True:
                query = InventoryList.all()
                self.nuke_query(query)
            if button_type == "Item" or all == True:
                query = Item.all()
                self.nuke_query(query)
            self.do_page()
        except Exception, ex:
            self.error_write(ex)


    def do_page(self):
        try:
            self.verify_admin()

            template_values = {
                'logout_url': self.url,
                'url_linktext': self.url_linktext,
              }

            path = os.path.join(os.path.dirname(__file__), 'nuke.html')
            self.response.out.write(template.render(path, template_values))
        except Exception, ex:
            self.error_write(ex)


class Users(AdminRootPage):

    def write_out(self, fname="users.html"):
        users = self.get_all_users()

        template_values = {
            'users': users,
            'logout_url': self.url,
            'url_linktext': self.url_linktext,
          }
        path = os.path.join(os.path.dirname(__file__), fname)
        self.response.out.write(template.render(path, template_values))


    def get_all_users(self):
        users_query = UsersData.all()
        users_query.order('lastname')
        users = users_query.fetch(1000)
        return users

    def get(self):
        try:
            self.verify_admin()
            self.write_out()
        except Exception, ex:
            self.error_write(ex)

    def post(self):
   
        try:
            self.verify_admin()
            button_type = self.request.get('button')

            if button_type == "Save":
                e = self.request.get('email').strip()
                a = self.request.get('address')
                p = self.request.get('phone')
                f = self.request.get('firstname')
                l = self.request.get('lastname')
                z = self.request.get('zip')
                c = self.request.get('city')
                id = self.request.get('id')

                users_query = UsersData.all()
                users_query.filter('email = ', e)
                g_us = users_query.fetch(1)

                if g_us != None and len(g_us) > 0 and g_us[0].id != id:
                    raise Exception("The email address: %s is already in use" % (e))

                users_query = UsersData.all()
                users_query.filter('id = ', id)
                g_us = users_query.fetch(1)
                if g_us == None or len(g_us) < 1:
                    user = UsersData(id=str(uuid.uuid1()), email=e)
                else:
                    user = g_us[0] 

                user.email = e
                user.address = a
                user.phone = p
                user.firstname = f
                user.lastname = l
                user.zip = z
                user.city = c
                user.put()
                self.write_out()

            elif button_type == "Edit":
                found = False
                users = self.get_all_users()
                for i in users:
                    v = self.request.get(i.id)
                    if v == "on":
                        found = True
                        ui = i

                if found:
                    template_values = {
                        'user': ui,
                        'logout_url': self.url,
                        'url_linktext': self.url_linktext,
                      }
                    path = os.path.join(os.path.dirname(__file__), 'useredit.html')
                    self.response.out.write(template.render(path, template_values))
                else:
                    self.write_out()

            elif button_type == "New":
                template_values = {
                    'logout_url': self.url,
                    'url_linktext': self.url_linktext,
                  }
                path = os.path.join(os.path.dirname(__file__), 'useredit.html')
                self.response.out.write(template.render(path, template_values))

            elif button_type == "Yes":
                v = self.request.get('id')
                q = UsersData.all()
                q.filter('id = ', v)
                u = q.fetch(1)
                if u != None and len(u) == 1:
                    q = UserChoices.all()
                    q.filter('user =', u[0])
                    ucs = q.fetch(1000)
                    for uc in ucs:
                        uc.delete()
                    u[0].delete()
                else:
                    raise Exception("User %s not found" % v)
                self.write_out()

            elif button_type == "Remove":
                users = self.get_all_users()
                for i in users:
                    v = self.request.get(i.id)
                    if v == "on":
                        q = UserChoices.all()
                        q.filter('user =', i)
                        ucs = q.fetch(1000)

                        # if this user hasn't done anything just delete it
                        if ucs == None or len(ucs) == 0:
                            i.delete()
                            self.write_out()
                        else:
                        # if it has write out the right page
                            sure_msg = "Are you sure you want to delete this user and all of its purchase order history?"
                            template_values = {
                              'sos_sure_action': '/users',
                              'logout_url': self.url,
                              'ARE_YOU_SURE': sure_msg,
                              'id': i.id,
                              'url_linktext': self.url_linktext,
                             }
                            path = os.path.join(os.path.dirname(__file__), 'sure.html')
                            self.response.out.write(template.render(path, template_values))

                        return


            elif button_type == "Printable":
                self.write_out(fname="userprintable.html")
            elif button_type == "CSV":
                self.write_out(fname="usercsv.html")

        except Exception, ex:
            self.error_write(ex)
            raise


class Inventory(AdminRootPage):

    def get(self):
        try:
            self.verify_admin()
            self.write_out()

        except Exception, ex:
            self.error_write(ex)
            #raise

    def get_all_items(self):
        harvest_date = self.request.get('weekof')
        harvest_date = self.get_harvest_date(harvest_date)
        item_query = Item.all()
        item_query.filter('date = ', harvest_date)
        item_query.order('name')
        items = item_query.fetch(100)

        return items

    def is_published(self, harvest_date):
        inv_query = InventoryList.all()
        inv_query.filter('date = ', harvest_date)
        inv = inv_query.fetch(1)
        if inv != None and len(inv) > 0:
            return True
        else:
            return False

    def write_out(self, fname="inventory.html"):

        items = self.get_all_items()
        harvest_date = self.request.get('weekof')
        harvest_date = self.get_harvest_date(harvest_date)

        harvest_date_str = harvest_date.strftime("%Y-%m-%d")
        inv_query = InventoryList.all()
        inv_query.filter('date = ', harvest_date)
        inv = inv_query.fetch(1)
        if self.is_published(harvest_date):
            published_msg = "This page was already published. You can still alter quantities."
        else:
            published_msg = "Not yet published"

        if inv != None and len(inv) > 0 and inv[0].locked == 1:
            published_msg = "You already locked out this inventory."

        template_values = {
            'items': items,
            'published_msg': published_msg,
            'logout_url': self.url,
            'url_linktext': self.url_linktext,
            'harvest_date': harvest_date_str,
          }

        path = os.path.join(os.path.dirname(__file__), fname)
        self.response.out.write(template.render(path, template_values))

    def post(self):

        try:
            self.verify_admin()
            button_type = self.request.get('button')
            items_all = self.get_all_items()
            harvest_date = self.request.get('weekof')
            harvest_date = self.get_harvest_date(harvest_date)
            harvest_date_str = harvest_date.strftime("%Y-%m-%d")
    
            if button_type == "Save":
                q = self.request.get('quantity')
                n = self.request.get('item')
                a = self.request.get('anotation')
                c = self.request.get('cost')
                id = self.request.get('id')


                if n == None or n == "":
                    raise Exception("You must name the items you add")
                # do error page
                if q == None:
                # do error page
                    raise Exception("The quantity must be an integer")
                try:
                    qInt = int(q)
                except:
                    raise Exception("Inventory must be an integer")
                try:
                    cFloat = float(c)
                except:
                    raise Exception("The cost must be a floating point")

                item_query = Item.all()
                item_query.filter('id = ', id)
                g_is = item_query.fetch(1)

                if g_is == None or len(g_is) < 1:
                    item = Item(id=str(uuid.uuid1()))
                    item.quantity = q
                    item.remaining = q
                else:
                    item = g_is[0] 
                    # make sure the new quantity is ok
                    init_q = int(item.quantity)
                    remaining_q = int(item.remaining)
                    purchased_q = init_q - remaining_q
                    new_qInt = int(q)
                    new_r = new_qInt - purchased_q
                    logging.info("admin is changing the quantity of |%s| from %d to %d" % (item.name, init_q, qInt))
                    if new_r < 0:

                        # here is where i can ask who gets screwed
                        logging.error("%d %s have already been sold.  The quantity for %s must be at least %d." % (new_qInt, item.name, item.name, purchased_q))

                        raise Exception("%d %s have already been sold.  The quantity for %s must be at least %d." % (new_qInt, item.name, item.name, purchased_q))
                    item.quantity = q
                    item.remaining = str(new_r)


                item.date = harvest_date
                item.name = n
                item.cost = c
                item.anotation = a
                item.put()

            elif button_type == "New":
                template_values = {
                    'logout_url': self.url,
                    'url_linktext': self.url_linktext,
                    'harvest_date': harvest_date_str,
                  }
                path = os.path.join(os.path.dirname(__file__), 'inventoryedit.html')
                self.response.out.write(template.render(path, template_values))
                return

            elif button_type == "Remove":
                for i in items_all:
                    v = self.request.get(i.id)
                    if v == "on":
                        if int(i.quantity) != 0:
                            raise Exception("The inventory for %s was already published.  You cannot delete items once it is published.  Try changing the quantity to 0")

                        else:
                            i.delete()

            elif button_type == "Edit":
                found = False
                for i in items_all:
                    v = self.request.get(i.id)
                    if v == "on":
                        found = True
                        fi = i

                if found:
                    template_values = {
                        'item': fi,
                        'logout_url': self.url,
                        'url_linktext': self.url_linktext,
                        'harvest_date': harvest_date_str,
                      }
                    path = os.path.join(os.path.dirname(__file__), 'inventoryedit.html')
                    self.response.out.write(template.render(path, template_values))
                    return

            elif button_type == "Publish":
                if self.is_published(harvest_date):
                        
                    query = InventoryList.all()
                    query.filter('date = ', harvest_date)
                    g_us = query.fetch(1)
                    if g_us == None or len(g_us) < 1:
                        il = InventoryList()
                    else:
                        il = g_us[0]

                else:
                    il = InventoryList()
                    il.date = harvest_date

                il.item_count = len(items_all)
                il.put()

            elif button_type == "Printable":
                self.write_out(fname="inventoryprintable.html")
                return
            elif button_type == "CSV":
                self.write_out(fname="inventorycsv.html")
                return
            elif button_type == "Copy":
                cd = self.request.get('copy_date')
                if cd != None:
                    self.copy_inv(items_all, cd)

            self.write_out()

        except Exception, ex:
            self.error_write(ex)

    def copy_inv(self, items, new_date):

        for old_item in items:
            item = Item(id=str(uuid.uuid1()))
            item.name = old_item.name
            item.anotation = old_item.anotation
            item.date = datetime.strptime(new_date, "%Y-%m-%d")
            item.quantity = old_item.quantity
            item.remaining = old_item.quantity
            item.cost = old_item.cost
            item.put()

class CleanChoices(AdminRootPage):

    def get(self):
        self.verify_admin()
        c = self.request.get('date')
        dt = datetime.strptime(c, "%Y-%M-%d")
        q = UserChoices.all()
        q.filter('date <', dt)
        ucs = q.fetch(1000)

        m  = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
<title>special</title>
</head>
<body>OK %s
        """ % (str(dt))
        self.response.out.write(m)
        db.delete(ucs)
        for uc in ucs:
            self.response.out.write(str(uc.date)  + " " + str(uc.id) + "<br>")
#            uc.delete()
        self.response.out.write("</body></html>")

application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/choices', UserRootPage),
                                      ('/inventory', Inventory),
                                      ('/users', Users),
                                      ('/harvest', Harvest),
                                      ('/invoice', Invoice),
                                      ('/admin', Admin),
                                      ('/waiting', WaitingList),
                                      ('/sure', Sure),
                                      ('/clean', CleanChoices),
                                      ('/register', Register)],
                                     debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
