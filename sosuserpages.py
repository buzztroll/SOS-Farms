import os
from google.appengine.ext.webapp import template
from datetime import datetime, date, time, timedelta
from google.appengine.api import users
from google.appengine.api import mail
from sosdata import UsersWaitingList2
from sosdata import UserChoices
from sosdata import UsersData
from sosdata import InventoryList
from sosdata import Item
from soserrors import SOSException
import sosdata
import sos_uuid as  uuid
import logging
import traceback
import pprint
from soscommon import AdminRootPage

# user code
class UserRootPage(AdminRootPage):

    def verify_user(self):
        if users.get_current_user():
            self.url = users.create_logout_url("/")
            self.url_linktext = 'Logout'
        else:
            self.url = users.create_login_url("/")
            self.url_linktext = 'Login'
            raise SOSException("You must login")

        user = users.get_current_user()
        email = user.email() 
        self.email = email
        users_query = UsersData.all()
        users_query.filter('email = ', email)
        g_us = users_query.fetch(1)

        if len(g_us) < 1:
            logging.error("trying lower case %s" % (email))
            email = email.lower()
            users_query.filter('email = ', email)
            g_us = users_query.fetch(1)

        if len(g_us) < 1:
            error_msg = "You are not authorized to use this service.  You are currently logged into google as: |%s|.  Please verify that this is the user name known to SOS farms" % (email)
            logging.error(error_msg)
            raise SOSException(error_msg)

        self.sos_user = g_us[0]
        self.google_user = user


    def get_next_inv(self):
        now = date.today()
        inv_query = InventoryList.all()
        inv_query.filter('date >= ', now)
        inv = inv_query.fetch(1)
        if inv == None or len(inv) < 1:
            msg = "The inventory for this week is not yet ready.  Please try back later"
            return (None,None,msg)

        item_query = Item.all()
        item_query.filter('date = ', inv[0].date)
        items = item_query.fetch(1000)
        item_dict = {}

        for i in items:
            item_dict[i.name] = i

        return (inv[0], item_dict, None)

    def new_choice(self, inv, i):
        # validate that a choice doesnt already exist this this 
        # item
        uc = UserChoices(item=i, user=self.sos_user)
        uc.date = inv.date
        uc.quantity = "0"
        uc.quantity_int = 0
        uc.charge = "0.00"
        uc.charge_float = 0.0
        uc.purchased = 0
        uc.id = str(uuid.uuid1())
        choice_query = UserChoices.all()
        choice_query.filter('item = ', i)
        choice_query.filter('user = ', self.sos_user)
        why_exist = choice_query.fetch(1)
        if why_exist != None and len(why_exist) > 0:
            logging.error("The item %s has already been selected by user %s: stack %s" % (i.name, str(self.email), pprint.pformat(traceback.extract_stack())))
        #    raise SOSException("The item %s has already been selected" % (i.name))
            # could return the found choice here, but i don't think any
            # should be found so i want to know when this happens
            return why_exist[0]

        uc.put()
        return uc
    
    def get_user_choice(self, inv, items):
        choice_query = UserChoices.all()
        choice_query.filter('date = ', inv.date)
        choice_query.filter('user = ', self.sos_user)
        choice_query.order('item')
        user_choices = choice_query.fetch(1000)

        # set them all up
        kys = sorted(items.keys())
        if user_choices == None or len(user_choices) < 1:
            user_choices = []
            for k in kys:
                i = items[k]
                uc = self.new_choice(inv, i)
                user_choices.append(uc)
        # update tmp_remaining
        else:
            for k in kys:
                i = items[k]
                found = False
                for uc in user_choices:
                    #try:
                    #    if uc.item != None:
                    #        id = uc.item.id
                    #except datastore_errors.Error, e:
                    #    if e.args[0] == "ReferenceProperty failed to be resolved":
                    #        uc.item = None
                    #        uc.put()
                    #    else:
                    #        raise

                    # why is uc.item ever allowed to be None?
                    #if uc.item != None and i.id == uc.item.id:
                    if uc.item != None and i.id == uc.item.id:
                        found = True
                if found == False:
                    logging.info("the item %s was not found.  user must have ordered, then the item was added, then they re-ordered %s." % (str(i), str(self.sos_user)))
                    uc = self.new_choice(inv, i)
                    user_choices.append(uc)

        user_choices = sorted(user_choices, key=lambda u: u.item.name)
        return user_choices

    def do_page(self, inv, user_choices, printable=False):

        if inv == None:
            harvest_date_str = self.get_harvest_date(None)
        else:
            harvest_date_str = inv.date.strftime("%Y-%m-%d")

        # add up costs
        purch = "Not yet purchased!"
        sub_total = 0.0
        f_ucs = []
        for uc in user_choices:
            if uc.item != None:
                sub_total = sub_total + float(uc.charge)
                if int(uc.item.remaining) > 0 or int(uc.quantity) > 0:
                    f_ucs.append(uc)
            if uc.purchased == 1:
                purch = "You have placed your order, but you may still alter it"

        tax = sub_total * sosdata.sos_get_tax_rate()
        final_total = sub_total + tax        

        if inv.locked == 1:
            fname = 'invlocked.html'
            purch = "The inventory is all set"
        else:
            fname = 'choices.html'

        if printable:
            fname = "choicesprintable.htm"
            len_a = len(f_ucs)
            for j in range(0, len_a):
                i = len_a - 1 - j
                uc = f_ucs[i]


        tax_str = "%6.2f" % (round(tax, 2))
        sub_total_str = "%6.2f" % (round(sub_total, 2))
        final_total_str = "%6.2f" % (round(final_total, 2))
        template_values = {
            'purch_msg': purch,
            'username': self.sos_user.firstname,
            'sub_total_charge': sub_total_str,
            'final_total_charge': final_total_str,
            'tax': tax_str,
            'harvest_date': harvest_date_str,
            'choices': f_ucs,
            'logout_url': self.url,
            'url_linktext': self.url_linktext,
          }
    
        path = os.path.join(os.path.dirname(__file__), fname)
        self.response.out.write(template.render(path, template_values))


    def post(self):
        try:
            self.verify_user()

            (inv, items, msg) = self.get_next_inv()
            if inv == None:
                self.not_ready(msg)
            else:
                button_type = self.request.get('button')
                logging.info("post for user |%s| button %s" % (self.email, button_type))

                choices = self.get_user_choice(inv, items)
                # validate we are safe
                for c in choices:
                    q = self.request.get(c.item.id)
                    if q != None and q != "":
                        if int(q) < 0:
                            raise SOSException("now now now, you know you can't have less than 0")
                        it = c.item
                        rest = int(it.remaining) + int(c.quantity) - int(q)
                        if rest < 0:
                            raise SOSException("There are only %s %s remaining.  You request %s, which is more than we have." 
                               % (it.remaining, it.name, q))

                check_choices = []
                for c in choices:
                    q = self.request.get(c.item.id)
                    if q != None and q != "":
                        it = c.item
                        rest = int(it.remaining) + int(c.quantity) - int(q)
                        it.remaining = str(rest)
                        it.remaining_int = rest
                        it.put()
                        c.quantity = q
                        cost = int(q) * float(it.cost)
                        c.charge = "%6.2f" % (round(cost, 2))

                        c.charge_float = float(c.charge)
                        c.quantity_int = int(q)
                        if button_type == "Purchase":
                            c.purchased = 1
                            logging.info("user |%s| %d %s" % (self.email, c.quantity_int, it.name))
                        if c.item.name in check_choices:
                            logging.info("why is this choice already there?! ")
                        else:
                            check_choices.append(c.item.name)
                        c.put()
                choices = self.get_user_choice(inv, items)
                if button_type == "Printable":
                    self.do_page(inv, choices, True)
                else: 
                    self.do_page(inv, choices)
        except Exception, ex:
            self.error_write(ex)
            raise

    def get(self):
        try:
            self.verify_user()
            (inv, items, msg) = self.get_next_inv()
            if inv == None:
                self.not_ready(msg)
            else:
                choices = self.get_user_choice(inv, items)
                self.do_page(inv, choices)
        except Exception, ex:
            self.error_write(ex)
            raise


    def not_ready(self, msg):
        self.url = users.create_logout_url("/")

        template_values = {
            'username': self.sos_user.firstname,
            'logout_url': self.url,
            'not_ready_msg': msg,
            'url_linktext': self.url_linktext,
          }

        path = os.path.join(os.path.dirname(__file__), 'notready.html')
        self.response.out.write(template.render(path, template_values))


class WaitingList(AdminRootPage):

    def do_page(self, fname="waiting.html"):
        try:
            users = self.get_all_waiting()

            template_values = {
                'users': users,
                'logout_url': self.url,
                'url_linktext': self.url_linktext,
              }

            path = os.path.join(os.path.dirname(__file__), fname)
            self.response.out.write(template.render(path, template_values))
        except Exception, ex:
            self.error_write(ex)


    def get(self):
        try:
            self.verify_admin()
            self.do_page()
        except Exception, ex:   
            self.error_write(ex)

    def get_all_waiting(self):
        users_query = UsersWaitingList2.all()
        g_us = users_query.fetch(1000)
        return g_us


    def post(self):
        try:
            self.verify_admin()

            button_type = self.request.get('button')

            fname = "waiting.html"
            if button_type == "Remove":
                users = self.get_all_waiting()
                for i in users:
                    v = self.request.get(i.id)
                    if v == "on":
                        i.delete()
            elif button_type == "Printable":
                fname = "waitingprintable.html"
            elif button_type == "CSV":
                fname = "waitingcsv.html"

            self.do_page(fname)
        except Exception, ex:   
            self.error_write(ex)

class Register(AdminRootPage):

    def write_out_reg(self):

        template_values = {
            'logout_url': self.url,
            'url_linktext': self.url_linktext,
          }
        path = os.path.join(os.path.dirname(__file__), 'register.html')
        self.response.out.write(template.render(path, template_values))


    def get(self):
        self.url = ""
        self.url_linktext = ""
        try:
            self.write_out_reg()
        except Exception, ex:
            self.error_write(ex)

    def post(self):
        self.url = ""
        self.url_linktext = ""
   
        try:
            button_type = self.request.get('button')

            if button_type == "Register":
                fn = self.request.get('firstname')
                ln = self.request.get('lastname')
                e = self.request.get('email')
                a = self.request.get('address')
                c = self.request.get('city')
                z = self.request.get('zip')
                p = self.request.get('phone')

                user = UsersWaitingList2(id=str(uuid.uuid1()))
                user.email = e
                user.firstname = fn
                user.lastname = ln
                user.address = a
                user.phone = p
                user.zip = z
                user.put()

                # email to kelly
                message = mail.EmailMessage(sender="sosfarmskauai@gmail.com",
                            subject="A new user has registered")

                message.body = "%s %s\n%s\n%s\n%s\n%s %s\n%s" % (fn, ln, e, p, a, c, z, p)
                message.to = "sosfarminfo@yahoo.com"
                message.cc = "buzztroll@gmail.com"
                message.send()

                template_values = {
                    'firstname': fn,
                    'lastname': ln,
                    'email': e,
                    'address': a,
                    'city': c,
                    'phone': p,
                    'zip': z
                  }
                path = os.path.join(os.path.dirname(__file__), 'thanks.html')
                self.response.out.write(template.render(path, template_values))

        except Exception, ex:
            self.error_write(ex)