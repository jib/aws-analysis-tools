#!python

import re
import sys
import logging

import boto.ec2

from texttable  import Texttable
from pprint     import PrettyPrinter
from optparse   import OptionParser

PP = PrettyPrinter( indent=2 )

###################
### Arg parsing
###################

parser = OptionParser("usage: %prog [options]" )
parser.add_option(  "-v", "--verbose",      default=None, action="store_true",
                    help="enable debug output" )
parser.add_option(  "-H", "--no-header",    default=None, action="store_true",
                    help="suppress table header" )
parser.add_option(  "-r", "--region",       default='us-east-1',
                    help="ec2 region to connect to" )
parser.add_option(  "-g", "--group",        default=None,
                    help="Include instances from these groups only (regex)" )
parser.add_option(  "-G", "--exclude-group",default=None,
                    help="Exclude instances from these groups (regex)" )
parser.add_option(  "-n", "--name",         default=None,
                    help="Include instances with these names only (regex)" )
parser.add_option(  "-N", "--exclude-name", default=None,
                    help="Exclude instances with these names (regex)" )
parser.add_option(  "-t", "--type",         default=None,
                    help="Include instances with these types only (regex)" )
parser.add_option(  "-T", "--exclude-type", default=None,
                    help="Exclude instances with these types (regex)" )
parser.add_option(  "-z", "--zone",         default=None,
                    help="Include instances with these zones only (regex)" )
parser.add_option(  "-Z", "--exclude-zone", default=None,
                    help="Exclude instances with these zones (regex)" )
parser.add_option(  "-s", "--state",        default=None,
                    help="Include instances with these states only (regex)" )
parser.add_option(  "-S", "--exclude-state",default=None,
                    help="Exclude instances with these states (regex)" )


(options, args) = parser.parse_args()

###################
### Logging
###################

if options.verbose: log_level = logging.DEBUG
else:               log_level = logging.INFO

logging.basicConfig(stream=sys.stdout, level=log_level)
logging.basicConfig(stream=sys.stderr, level=(logging.ERROR,logging.CRITICAL))


###################
### Connection
###################

conn = boto.ec2.connect_to_region( options.region )

###################
### Regexes
###################

regexes = {}
for opt in [ 'group', 'exclude_group', 'name', 'exclude_name',
             'type',  'exclude_type',  'zone', 'exclude_zone',
             'state', 'exclude_state' ]:

    ### we have a regex we should build
    if options.__dict__.get( opt, None ):
        regexes[ opt ] = re.compile( options.__dict__.get( opt ), re.IGNORECASE )

#PP.pprint( regexes )

def get_instances():
    instances   = [ i for r in conn.get_all_instances()
                        for i in r.instances ]

    rv          = [];
    for i in instances:

        ### we will assume this node is one of the nodes we want
        ### to operate on, and we will unset this flag if any of
        ### the criteria fail
        wanted_node = True

        for re_name, regex in regexes.iteritems():

            ### What's the value we will be testing against?
            if re.search( 'group', re_name ):
                value = i.groups[0].name
            elif re.search( 'name', re_name ):
                value = i.tags.get( 'Name', '' )
            elif re.search( 'type', re_name ):
                value = i.instance_type
            elif re.search( 'state', re_name ):
                value = i.state
            elif re.search( 'zone', re_name ):
                ### i.region is an object. i._placement is a string.
                value = str(i._placement)

            else:
                logging.error( "Don't know what to do with: %s" % re_name )
                continue

            #PP.pprint( "name = %s value = %s pattern = %s" % ( re_name, value, regex.pattern ) )

            ### Should the regex match or not match?
            if re.search( 'exclude', re_name ):
                rv_value = None
            else:
                rv_value = True

            ### if the match is not what we expect, then clearly we
            ### don't care about the node
            result = regex.search( value )

            ### we expected to get no results, excellent
            if result == None and rv_value == None:
                pass

            ### we expected to get some match, excellent
            elif result is not None and rv_value is not None:
                pass

            ### we don't care about this node
            else:
                wanted_node = False
                break

        if wanted_node:
            rv.append( i )

    return rv

def list_instances():
    table       = Texttable( max_width=0 )

    table.set_deco( Texttable.HEADER )
    table.set_cols_dtype( [ 't', 't', 't', 't', 't', 't', 't', 't' ] )
    table.set_cols_align( [ 'l', 'l', 'l', 'l', 'l', 'l', 'l', 't' ] )

    if not options.no_header:
        ### using add_row, so the headers aren't being centered, for easier grepping
        table.add_row(
            [ '# id', 'Name', 'Type', 'Zone', 'Group', 'State', 'Root', 'Volumes' ] )

    instances = get_instances()
    for i in instances:

        ### XXX there's a bug where you can't get the size of the volumes, it's
        ### always reported as None :(
        volumes = ", ".join( [ ebs.volume_id for ebs in i.block_device_mapping.values()
                                if ebs.delete_on_termination == False ] )

        ### you can use i.region instead of i._placement, but it pretty
        ### prints to RegionInfo:us-east-1. For now, use the private version
        ### XXX EVERY column in this output had better have a non-zero length
        ### or texttable blows up with 'width must be greater than 0' error
        table.add_row( [ i.id, i.tags.get( 'Name', ' ' ), i.instance_type,
                         i._placement , i.groups[0].name, i.state,
                         i.root_device_type, volumes or '-' ] )

        #PP.pprint( i.__dict__ )

    ### table.draw() blows up if there is nothing to print
    if instances or not options.no_header:
        print table.draw()

if __name__ == '__main__':
    list_instances()

