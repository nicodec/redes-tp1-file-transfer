import argparse
from utils.misc import CustomHelpFormatter

parser = argparse.ArgumentParser(description="START SERVER Description", formatter_class=CustomHelpFormatter)
verbosity_group = parser.add_mutually_exclusive_group()
verbosity_group.add_argument("-v", "--verbose", action="store_true",    help="increase output verbosity")
verbosity_group.add_argument("-q", "--quiet", action="store_true",      help="decrease output verbosity")
parser.add_argument("-H", "--host", metavar="ADDR", type=str,           help="service IP address")
parser.add_argument("-p", "--port", type=int,                           help="service port")
parser.add_argument("-s", "--storage", metavar="DIRPATH", type=str,     help="storage dir path")
parser.add_argument("-r", "--protocol", metavar="protocol", type=str,   help="error recovery protocol")

parser.usage = parser.format_usage()
for a in parser._actions:
    a.metavar='\b'

args = parser.parse_args()

# debug
print(args)