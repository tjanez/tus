# A script for backing up and restoring partitions using Partclone.

# Copyright 2017, 2018 Tadej Janež.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import os
import shlex
import subprocess
import sys

import click


logger = logging.getLogger(__name__)


class _BraceString(str):
    def __mod__(self, other):
        return self.format(*other)
    def __str__(self):
        return self


class _StyleAdapter(logging.LoggerAdapter):

    def __init__(self, logger, extra=None):
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        return _BraceString(msg), kwargs


def _setup_logging(log_file):
    """Set up logging to the given file."""
    global logger

    logger.setLevel(logging.DEBUG)
    # Define a Handler which writes DEBUG messages or higher to log_file.
    log_file = logging.FileHandler(log_file, mode='w')
    log_file.setLevel(logging.DEBUG)
    # Set custom log messages formatter.
    formatter = logging.Formatter(
        fmt='{asctime} {levelname:8} {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    # Tell the handler to use this format.
    log_file.setFormatter(formatter)
    # Add the handler to the root logger.
    logger.addHandler(log_file)

    # Use str.format() syntax for logging messages.
    logger = _StyleAdapter(logger)


@click.group()
def cli():
    pass


@cli.command()
@click.option('--archive-size', '-s', type=int, default=4096,
              help="Size (in MiBs) of the gzipped partition backup parts.",
              show_default=True)
@click.argument('source-device', type=click.Path(exists=True))
@click.argument('backup-dir', type=click.Path(exists=False))
def backup(archive_size, source_device, backup_dir):
    """Backup the given partition using Partclone."""
    # Check if running as root.
    # TODO: Convert this to a decorator.
    if not os.geteuid() == 0:
        raise click.ClickException(
            "The {} script should be run as root!".format(sys.argv[0])
        )

    # TODO: Check if all commands are installed.

    # Create backup directory.
    try:
        os.makedirs(backup_dir)
    except OSError:
        raise click.ClickException(
            f"Backup directory '{backup_dir}' exists!\n"
            "You should provide a directory path that doesn't exist yet."
        )

    log_file = os.path.join(backup_dir, os.path.basename(sys.argv[0]) + '.log')
    _setup_logging(log_file)
    logger.info("Starting {0}...", os.path.basename(sys.argv[0]))

    # TODO: Guess the filesystem of the source device.
    fs_type = 'ext4'

    source_device_name = source_device.partition('/dev/')[-1].replace('/', '-')
    if not source_device_name:
        error_msg = (
            "Source device does not start with '/dev/'.\n"
            "You should provice a source device that starts with '/dev/'!"
        )
        logger.error(error_msg)
        raise click.ClickException(error_msg)

    partclone_command = [
        f'partclone.{fs_type}',
        '--logfile', f'{backup_dir}/partclone.log',
        '--buffer_size', '10485670',
        '--clone',
        '--source', f'{source_device}',
        '--output', '-',
    ]
    pigz_command = [
        'pigz',
        '--stdout',
        '--fast',
        '--blocksize', '1024',
        '--rsyncable',
    ]
    split_command = [
        'split',
        '--suffix-length=2',
        '--bytes', f'{archive_size}MB',
        '-', f'{backup_dir}/{source_device_name}.{fs_type}-ptcl-img.gz.',
    ]

    logger.info("Running backup command as a series of the following piped "
                "commands:")

    logger.info("- {0}", partclone_command)
    # TODO: Capture Partclone's stderr and display it asynchrously at the same
    # time.
    process_partclone = subprocess.Popen(
        partclone_command,
        stdout=subprocess.PIPE,
    )

    logger.info("- {0}", pigz_command)
    process_pigz = subprocess.Popen(
        pigz_command,
        stdin=process_partclone.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    logger.info("- {0}", split_command)
    process_split = subprocess.Popen(
        split_command,
        stdin=process_pigz.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Allow Partclone process to receive a SIGPIPE if pigz exits before
        # Partclone.
        process_partclone.stdout.close()
        # Allow pigz process to receive a SIGPIPE if split exits before pigz.
        process_pigz.stdout.close()
        # Interact with the split process (send data to stdin, read data from
        # stdout/stderr, wait for process to terminate).
        split_stdout, split_stderr = process_split.communicate()
    except:
        for p in [process_partclone, process_pigz, process_split]:
            p.kill()
            p.wait()
        raise
    for p in [process_partclone, process_pigz, process_split]:
        # Wait for the process to finish.
        retcode = p.poll()
        # Get process' stderr.
        stderr = None
        if p == process_split:
            # The split process' stderr was already read when
            # process_split.communicate() was called.
            stderr = split_stderr.decode('utf-8')
        elif p.stderr is not None:
            stderr = p.stderr.read().decode('utf-8')

        if retcode and retcode != 0:
            exception_msg = (
                f"Command {p.args} returned non-zero exit status {retcode}."
            )
            if stderr:
                exception_msg += f"\nCommand's stderr:\n{stderr}"
            logger.error(exception_msg)
            raise click.ClickException(exception_msg)
        # TODO: Handle Partclone's lack of proper setting of return code to
        # non-zero on some errors and manually detect unsuccessful runs.
        # However, we need to be able to asynchronously capture Partclone's
        # stderr first.
        # if p == process_partclone:
        #     if 'unset_name' in stderr:
        #         raise click.ClickException(
        #             f"Command {p.args} returned zero exit status, however, we "
        #             "believe it didn't finish successfully.\n"
        #             f"Command's stderr:\n{stderr}"
        #     )
    logger.info("Successfully finished running backup command.")


@cli.command()
def restore():
    """Restore the given Partclone backup to the given partition."""
    pass


@cli.command()
def extract():
    """Extract the given Partclone backup to the given location."""
    pass
