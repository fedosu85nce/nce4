#
# IMPORTS
#
import re
import locale
import sys
# path for find partition_interface module
sys.path.insert(0, "../../src/viewer/newt/partitioncfg/")

from partition_util import *

#
# CONSTANTS
#

#
# CODE
#
if __name__ == "__main__":

    print strToSize("512")
    print strToSize("512M")
    print strToSize("0.5G")

    print strToSize("0.5M")
    print strToSize("512B")
    print strToSize("512k")