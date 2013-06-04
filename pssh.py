#!/usr/bin/env kpython
# Parallel SSH to a list of nodes, returned from search-ec2-tags.py
# (must be in your path).
#
# Waits for nodes to respond, then outputs their stdout,stderr color coded.
#
# ./pssh.py --query 'ec2_tag' 'command_to_run'
#
# Options:
#  -h, --help           show this help message and exit
#  --query=QUERY        the string to pass search-ec2-tags.py
#  --hosts=HOSTS        comma-sep list of hosts to ssh to
#  --no-color           disable or enable color
#  --keep-ssh-warnings  disable the removing of SSH warnings from stderr output
#  --connect-timeout    ssh ConnectTimeout option
#  --timeout            amount of time to wait, before killing the ssh
#
import sys
import time
import subprocess
import select
from optparse import OptionParser


def hilite(string, options, color='white', bold=False):
    if options.no_color:
        return string

    attr = []
    if color == 'green':
        attr.append('32')  # green
    elif color == 'red':
        attr.append('41')  # red
    else:
        attr.append('37')  # white
    if bold:
        attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), string)


def remove_ssh_warnings(stderr, options):
    if options.keep_ssh_warnings:
        return stderr

    output = str(stderr).splitlines()
    if len(output) == 0:
        return None
    if len(output) == 1:
        return output[0]

    if stderr[0].startswith('@'):
        # 8 lines for a DNS spoofing warning
        if 'POSSIBLE DNS SPOOFING' in output[1]:
            output = output[8:]
        # 13 lines for a remote host identification changed warning
        if 'REMOTE HOST IDENTIFICATION' in output[1]:
            output = output[13:]
    if len(output) == 0:
        return None
    if len(output) == 1:
        return output[0]

    return '\n'.join(output)


def query(string):
    stdout, stderr = subprocess.Popen(['kpython', '/usr/local/bin/search-ec2-tags.py'] + string.split(),
                                      stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()
    print "matched the following hosts: %s" % ', '.join(stdout.splitlines())
    if stderr:
        return None
    return stdout.splitlines()


if __name__ == '__main__':

    parser = OptionParser(usage=__doc__)
    parser.add_option("--query", help='the string to pass search-ec2-tags.py', default=False)
    parser.add_option("--host", help='comma-sep list of hosts to ssh to', default=False)
    parser.add_option("--timeout", help='amount of time to wait before killing the ssh',
                      default=240)
    parser.add_option("--connect-timeout", help='ssh ConnectTimeout option',
                      default=10)
    parser.add_option("--no-color", action="store_true", help="disable or enable color",
                      default=False)
    parser.add_option("--keep-ssh-warnings", action="store_true",
                      help="disable the removing of SSH warnings from stderr output",
                      default=False)
    (options, args) = parser.parse_args()

    procs = []
    command = args[0]

    hosts = ['ops-dev005.krxd.net', ]
    if options.query:
        hosts = query(options.query)
        if not hosts:
            print hilite("Sorry, search-ec2-tags.py returned an error:\n %s" % hosts, options, 'red')
            sys.exit(1)

    if options.host:
        hosts = [host.strip() for host in hosts.split(',')]

    for host in hosts:
        proc = subprocess.Popen("ssh -oStrictHostKeyChecking=no -oConnectTimeout=%s %s '%s'" %
                                (options.connect_timeout, host, command), shell=True,
                                stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        procs.append(proc)

    index = 0
    ticks = 0
    too_long = False
    while 1:
        # nothing has returned, the first few secs, I bet.
        if ticks < 2:
            time.sleep(1)
        if ticks > 60:
            too_long = True

        host = hosts[index]
        proc = procs[index]

        # has it finished? go ahead and print the host and results.
        if not too_long and proc.poll() is not None:
            stdout, stderr = proc.communicate()
            print "[%s]" % hilite(host, options, bold=True)
            if stdout:
                print "STDOUT: \n%s" % hilite(stdout, options, 'green', False)

            stderr = remove_ssh_warnings(stderr, options)
            if stderr and len(stderr) > 1:
                print "STDERR: \n%s" % hilite(stderr, options, 'red', False)
            del procs[index]
            del hosts[index]

        elif not too_long and (ticks > 1) and (ticks % 5 == 0):
            # only print "waiting still.." every 5 sec.
            print "waiting on these hosts, still: %s" % ', '.join(hosts)
            time.sleep(1)

        if too_long:
            # it has been too long. print stdout/stderr one line at a time, so people
            # know what's happening, and aren't left waiting for timeout (and
            # then they never see stdout/stderr).
            print "%s (responding slowly - here is the output so far)" % \
                hilite('[' + host + ']', options, bold=True)

            while 1:
                if proc.poll() is not None:
                    break

                if select.select([proc.stdout], [], [], 0)[0]:
                    print "STDOUT: \n"
                while select.select([proc.stdout], [], [], 0)[0]:
                    stdout = proc.stdout.readline()
                    sys.stdout.write(hilite(stdout, options, 'green', False))

                while select.select([proc.stderr], [], [], 0)[0]:
                    stderr = remove_ssh_warnings(proc.stderr.readline(), options)
                    if stderr is None:
                        break
                    print "STDERR: \n"
                    sys.stdout.write(hilite(stderr, options, 'red', False))

                if ticks > options.timeout:
                    break
                elif proc.poll() is not None:
                    break
                else:
                    time.sleep(1)

            # one final time, to flush buffers, if the call won't block (process has exited)
            if proc.poll() is not None:
                stdout = '\n'.join(proc.stdout.readlines())
                if stdout:
                    print "STDOUT: \n%s" % hilite(stdout, options,
                                                  'green', False)
                stderr = '\n'.join(proc.stderr.readlines())
                if stderr:
                    print "STDERR: \n%s" % hilite(stderr, options,
                                                  'red', False)

            # remove from queue
            if proc.poll() is not None:
                del procs[index]
                del hosts[index]

        ticks += 1

        if len(procs) > index + 1:
            index += 1
        elif len(procs) == 0:
            break
        else:
            index = 0

        if ticks > options.timeout:
            [bad.terminate() for bad in procs]
            print hilite("\nSorry, the following hosts took too long, and I gave up: %s\n" % ','.join(hosts), options, 'red')
            break
