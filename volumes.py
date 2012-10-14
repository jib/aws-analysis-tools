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
parser.add_option(  "-i", "--instance-name",default=None, action="store_true",
                    help="Show instance names in attachment info (SLOW!)" )
parser.add_option(  "-r", "--region",       default='us-east-1',
                    help="ec2 region to connect to" )
parser.add_option(  "-n", "--name",         default=None,
                    help="Include volumes with these names only (regex)" )
parser.add_option(  "-N", "--exclude-name", default=None,
                    help="Exclude volumes with these names (regex)" )
parser.add_option(  "-z", "--zone",         default=None,
                    help="Include volumes with these zones only (regex)" )
parser.add_option(  "-Z", "--exclude-zone", default=None,
                    help="Exclude volumes with these zones (regex)" )
parser.add_option(  "-d", "--device",         default=None,
                    help="Include volumes attached to these devices only (regex)" )
parser.add_option(  "-D", "--exclude-device", default=None,
                    help="Exclude volumes attached to these devices (regex)" )


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
for opt in [ 'name', 'exclude_name', 'zone', 'exclude_zone',
             'device', 'exclude_device' ]:

    ### we have a regex we should build
    if options.__dict__.get( opt, None ):
        regexes[ opt ] = re.compile( options.__dict__.get( opt ), re.IGNORECASE )

#PP.pprint( regexes )

def get_volumes():
    volumes = conn.get_all_volumes()
    rv      = [];

    for v in volumes:

        ### we will assume this node is one of the nodes we want
        ### to operate on, and we will unset this flag if any of
        ### the criteria fail
        wanted_node = True

        for re_name, regex in regexes.iteritems():

            ### What's the value we will be testing against?
            if re.search( 'name', re_name ):
                value = v.tags.get( 'Name', '' )
            elif re.search( 'zone', re_name ):
                ### i.region is an object. i._placement is a string.
                value = v.zone
            elif re.search( 'device', re_name ):
                value = v.attach_data.device or ''
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
            rv.append( v )

    return rv

def list_volumes():
    table       = Texttable( max_width=0 )

    table.set_deco( Texttable.HEADER )
    table.set_cols_dtype( [ 't', 't', 't', 't', 't', 't', 't' ] )
    table.set_cols_align( [ 'l', 'l', 'l', 'l', 'l', 'l', 'l' ] )

    if not options.no_header:
        ### using add_row, so the headers aren't being centered, for easier grepping
        table.add_row([ '# id', 'Name', 'Zone', 'Status', 'Size', 'Instance', 'Device' ])

    volumes = get_volumes()
    for v in volumes:
        ad = v.attach_data

        if ad.instance_id:
            if options.instance_name:
                i       = conn.get_all_instances(
                            instance_ids=[ ad.instance_id ] )[0].instances[ 0 ]
                name    = i.tags.get('Name', i.id )
            else:
                name    = ad.instance_id
        else:
            name    = '-'

        table.add_row( [ v.id, v.tags.get( 'Name', ' ' ), v.zone , v.status,
                         v.size, name or '-' , ad.device or '-' ] )

        #PP.pprint(  )


        """
        ### XXX there's a bug where you can't get the size of the volumes, it's
        ### always reported as None :(
        volumes = ", ".join( [ ebs.volume_id for ebs in i.block_device_mapping.values()
                                if ebs.delete_on_termination == False ] )

        ### you can use i.region instead of i._placement, but it pretty
        ### prints to RegionInfo:us-east-1. For now, use the private version
        ### XXX EVERY column in this output had better have a non-zero length
        ### or texttable blows up with 'width must be greater than 0' error
        table.add_row( [ i.id, i.tags.get( 'Name', ' ' ), i.instance_type,
                         i._placement , i.groups[0].name, volumes or ' ' ] )

        #PP.pprint( i.__dict__ )
        """

    ### table.draw() blows up if there is nothing to print
    if volumes or not options.no_header:
        print table.draw()

if __name__ == '__main__':
    list_volumes()
