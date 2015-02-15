#
# IMPORTS
#
import re
import locale

from blivet.size import Size


#
# CONSTANTS
#
SIZE_UNITS_DEFAULT = "M"                 # Default units when the user do no input units
SIZE_MIN_GRANULARITY = Size(spec="1 M")  # The smallest granularity for storage size

#
# CODE
#


def strToSize(inputSize, lowerBound=SIZE_MIN_GRANULARITY, units=SIZE_UNITS_DEFAULT):
    '''format inputSize to Size from blivet.size

        :inputSize  - string
        :lowerBound
        :units
    '''
    if not inputSize:
        return None

    text = inputSize.decode("utf-8").strip()

    # A string ending with digit, dot or commoa without the unit information
    if re.search(r'[\d.%s]$' % locale.nl_langinfo(locale.RADIXCHAR), text):
        text += units

    try:
        size = Size(spec=text)
    except ValueError:
        return None

    # set as the smallest granularity
    if size is None:
        return None
    if lowerBound is not None and size < lowerBound:
        return lowerBound

    # print size
    return size
