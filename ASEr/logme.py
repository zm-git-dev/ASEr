"""
Logging with timestamps and optional log files.

===============================================================================

          FILE: logme
        AUTHOR: Michael D Dacre, mike.dacre@gmail.com
  ORGANIZATION: Stanford University
       CREATED: 2015-03-03 11:41
 Last modified: 2016-03-11 14:44

   DESCRIPTION: Print a timestamped message to a logfile, STDERR, or STDOUT.
                If STDERR or STDOUT are used, colored flags are added.
                Colored flags are INFO, WARNINING, ERROR, or CRITICAL.
                It is possible to write to both logfile and STDOUT/STDERR
                using the also_write argument.
                If level is 'error' or 'critical', error is written to
                STDERR unless also_write == -1
                MIN_LEVEL can also be provided, logs will only print if
                level > MIN_LEVEL. Level order: critical>error>warn>info>debug

         USAGE: import logme as lm
                lm.log("Screw up!", <outfile>,
                       level='debug'|'info'|'warn'|'error'|'normal',
                       also_write='stderr'|'stdout')

                All arguments are optional except for the initial message.
      EXAMPLES: lm.log('Hi')
                   Prints: 20160223 11:46:24.969 | INFO --> Hi
                lm.log('Hi', level='debug')
                   Prints nothing
                lm.MIN_LEVEL = 'debug'
                lm.log('Hi', level='debug')
                   Prints: 20160223 11:46:24.969 | DEBUG --> Hi


          NOTE: Uses terminal colors and STDERR, not compatible with non-unix
                systems

===============================================================================
"""
import sys
import gzip
import bz2
import logging
from datetime import datetime as dt

__all__ = ['log', 'MIN_LEVEL', 'LOGFILE']

###################################
#  Constants for printing colors  #
###################################

WHITE  = '\033[97m'
YELLOW = '\033[93m'
RED    = '\033[91m'
BOLD   = '\033[1m'
ENDC   = '\033[0m'

MIN_LEVEL = 'info'
LOGFILE   = sys.stderr


def log(message, level='info', logfile=None, also_write=None,
        min_level=None, kind=None):
    """Print a string to logfile.

    :message: The message to print.
    :logfile: Optional file to log to, defaults to STDERR. Can provide a
              logging object
    :level:    Prefix. Defaults to 'normal', options:
        'debug':    '<timestamp> DEBUG --> '
        'info':     '<timestamp> INFO --> '
        'warn':     '<timestamp> WARNING --> '
        'error':    '<timestamp> ERROR --> '
        'critical': '<timestamp> CRITICAL --> '
    :also_write: 'stdout': print to STDOUT also.
    :also_write: 'stderr': print to STDERR also.

    :min_level: Retained for backwards compatibility, min_level should be set
                using the logme.MIN_LEVEL constant.

    :kind: synonym for level, kept to retain backwards compatibility
    """
    stdout = False
    stderr = False
    message = str(message)

    if not logfile:
        logfile = LOGFILE

    if kind:
        level = kind

    min_level = min_level if min_level else MIN_LEVEL

    # Level checking, not used with logging objects
    level_map = {'debug': 0, 'info': 1, 'warn': 2, 'error': 3, 'critical': 4,
                 'd': 0, 'i': 1, 'w': 2, 'e': 3, 'c': 4,
                 0: 0, 1: 1, 2: 2, 3: 3, 4: 4}

    try:
        level = level_map[level]
    except KeyError:
        raise Exception('Invalid level {}'.format(level))

    try:
        min_level = level_map[min_level]
    except KeyError:
        raise Exception('Invalid min_level {}'.format(min_level))

    if level > 2:
        if also_write != -1 or also_write != 'stdout':
            also_write = 'stderr'

    # Attempt to handle all file type
    if isinstance(logfile, (logging.RootLogger, logging.Logger)):
        _logit(message, logfile, level, color=False, min_level=min_level)
    elif isinstance(logfile, str):
        with _open_zipped(logfile, 'a') as outfile:
            _logit(message, outfile, level, color=False, min_level=min_level)
    elif str(getattr(logfile, 'name')).strip('<>') == 'stdout':
        _logit(message, logfile, level, color=True, min_level=min_level)
        stdout = True
    elif str(getattr(logfile, 'name')).strip('<>') == 'stderr':
        _logit(message, logfile, level, color=True, min_level=min_level)
        stderr = True
    elif getattr(logfile, 'closed'):
        with _open_zipped(logfile.name, 'a') as outfile:
            _logit(message, outfile, level, color=False, min_level=min_level)
    else:
        _logit(message, logfile, level, color=False, min_level=min_level)

    # Also print to stdout or stderr if requested
    if also_write == 'stdout' and not stdout:
        _logit(message, sys.stdout, level, color=True, min_level=min_level)
    elif also_write == 'stderr' and not stderr:
        _logit(message, sys.stdout, level, color=True, min_level=min_level)


def clear(infile):
    """Truncate a file."""
    open(infile, 'w').close()


###############################################################################
#                             A Logging Exception                             #
###############################################################################


class LoggingException(Exception):

    """Log a critical message with logme and also raise."""

    def __init__(self, message, logfile=None):
        """Log message as critical, raise with first line."""
        args = {'kind': 'critical'}
        if logfile:
            args.update({'logfile': logfile})
        # Log with logme
        log(message, **args)
        # Raise with the first line of the log
        message = message.split('\n')[0]
        super(LoggingException, self).__init__(message)


###############################################################################
#                              Private Functions                              #
###############################################################################


def _logit(message, output, level, color=False, min_level=None):
    """Write message to file either with color or not.

    output must be filehandle or logging object.
    """
    now = dt.now()
    timestamp = "{0}.{1:<3}".format(now.strftime("%Y%m%d %H:%M:%S"),
                                    str(int(now.microsecond/1000)))

    flag_map  = {0: 'DEBUG', 1: 'INFO', 2: 'WARNING', 3: 'ERROR',
                 4: 'CRITICAL'}

    flag = flag_map[level]
    flag_len = len('{0} | {1} --> '.format(timestamp, flag)) - 2

    if color:
        flag = _color(flag)

    if isinstance(output, (logging.RootLogger, logging.Logger)):
        message = ' {} --> {}'.format(timestamp, message)
        if level == 0:
            output.debug(message)
        if level == 1:
            output.info(message)
        if level == 2:
            output.warning(message)
        if level == 3:
            output.error(message)
        if level == 4:
            output.critical(message)
    else:
        # Check min_level before proceeding
        if level < min_level:
            return

        # Format multiline message
        lines = message.split('\n')
        if len(lines) != 1:
            message = lines[0] + '\n'
            lines = lines[1:]
            for line in lines:
                message = message + (''.ljust(flag_len, '-') + '> ' +
                                     line + '\n')
        output.write('{0} | {1} --> {2}\n'.format(timestamp, flag,
                                                  str(message)))


def _color(flag):
    """Return the flag with correct color codes."""
    if flag == 'INFO':
        return BOLD + WHITE + flag + ENDC
    if flag == 'WARNING':
        return BOLD + YELLOW + flag + ENDC
    if flag == 'ERROR':
        return BOLD + RED + flag + ENDC
    if flag == 'CRITICAL':
        return BOLD + RED + flag + ENDC


def _open_zipped(infile, mode='r'):
    """Return file handle of file regardless of zipped or not.

    Text mode enforced for compatibility with python2
    """
    mode   = mode[0] + 't'
    p2mode = mode
    if hasattr(infile, 'write'):
        return infile
    if isinstance(infile, str):
        if infile.endswith('.gz'):
            return gzip.open(infile, mode)
        if infile.endswith('.bz2'):
            if hasattr(bz2, 'open'):
                return bz2.open(infile, mode)
            else:
                return bz2.BZ2File(infile, p2mode)
        return open(infile, p2mode)
