#!/usr/bin/env python
#
# Returns all hostnames that have the specified ec2 tag
#
# Takes one argument. Either the string to search for in the Value of all tags,
# or Tag:Value. This *is* case sensitive.
#
# Will check every ec2 region, unless, e.g. --regions='us-east-1,eu-west-1'
#
# Examples:
#   ./search-ec2-tags.py s_classes:s_puppetmaster
#   ./search-ec2-tags.py s_puppetmaster
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

    for region in regions:
        ec2 = region.connect()

        string = args[0].split(':', 1)

        if len(string) == 2:
            tag, val = string
            query = {"tag:%s" % tag: '*' + val + '*'}
        else:
            query = {'tag-value': '*' + string[0] + '*'}

        for res in ec2.get_all_instances(filters=query):
            instance = res.instances[0]
            print instance.tags.get('Name')
