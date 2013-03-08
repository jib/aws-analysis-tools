#!/usr/bin/env python
#
# Returns all hostnames that have the specified ec2 tag
#
# Takes one or more filters, of the type:
# either the string to search for in the Value of all tags, or Tag:Value.
#
# To search for multiple things, use multiple filters as the args.
#
# This *is* case sensitive.
#
# Will check every ec2 region, unless, e.g. --regions='us-east-1,eu-west-1'
#
# Examples:
#   ./search-ec2-tags.py s_classes:s_puppetmaster
#   ./search-ec2-tags.py s_puppetmaster environment:production
#
# CAVEAT: if you specify multiple of the same key, (tag:Name, or just a plain
# string to search for in the value, e.g. 'puppetmaster'),
# those are OR'd. If you specify 1) tag-value and 1) tag:value, the result is
# AND'd. Sorry, that's a limitation of the API, and I only want to make one
# API call to each region.
#
# Examples:
#    Return all nodes with tag s_class:s_puppetmaster AND nodes with either
#    'production' or 'development' in the value of any tag.
#   ./search-ec2-tags.py s_classes:s_puppetmaster production development
#
#   Return all nodes with tag=Name matching 'foo' OR 'bar'
#   ./search-ec2-tags.py Name:foo Name:bar
#
#   Return all nodes w/ tag=Name matching 'foo' and tag environment:production
#   ./search-ec2-tags.py Name:foo environment:production
#
import boto.ec2
import sys
from optparse import OptionParser


if __name__ == '__main__':

    parser = OptionParser(usage=__doc__)
    parser.add_option("--regions",
                      help='ec2 regions to check, comman-sep string',
                      default=False)
    (options, args) = parser.parse_args()

    ec2_regions = boto.ec2.regions()

    if not options.regions:
        regions = ec2_regions
    else:
        regions = [reg for reg in ec2_regions
                   if reg.name in options.regions]

    query = {}
    for arg in args:
        string = arg.split(':', 1)
        if len(string) == 2:
            tag, val = string
            # not in the dict yet? good! Add it.
            if "tag:%s" % tag not in query:
                query.update({"tag:%s" % tag: ['*' + val + '*']})
            else:
            # already there? extend the val (array) with another item:
                query['tag:%s' % tag] = query.get('tag:%s' % tag) + ['*' + val + '*']
        else:
            if 'tag-value' not in query:
                query.update({'tag-value': ['*' + string[0] + '*']})
            else:
                query['tag-value'] = query.get('tag-value') + ['*' + string[0] + '*']

    for region in regions:
        ec2 = region.connect()

        for res in ec2.get_all_instances(filters=query):
            instance = res.instances[0]
            print instance.tags.get('Name')
