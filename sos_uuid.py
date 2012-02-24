import string
import random

__author__ = 'bresnaha'

# temp work around for aitrplane

def uuid1():
    x = [random.choice(string.ascii_letters) for i in range(0, 10)]
    return x