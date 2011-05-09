#!/usr/bin/python


import os
import sys
import datetime
import time
from datetime import date
from datetime import datetime, date, time, timedelta


def main():
    sed_out = sys.argv[1]
    html_file = sys.argv[2]
    form_file = sys.argv[3]
    out_file = sys.argv[4]

    print "subbing out %s in %s and subbing in %s to %s" % (sed_out, html_file, form_file, out_file)

    formfile = open(form_file, "r")
    form_lines = formfile.readlines()
    formfile.close()

    htmlin = open(html_file, "r")
    linein = htmlin.readline()

    outf = open(out_file, "w")
    while linein:

        ndx = linein.find(sed_out)
        if ndx >= 0:
            first_half = linein[0:ndx]
            outf.write(first_half)

            for l in form_lines:
                outf.write(l)
            
            last_half = linein[ndx:].replace(sed_out, "")
            outf.write(last_half)
        else:
            outf.write(linein)

        linein = htmlin.readline()


if __name__ == "__main__":
  main()
