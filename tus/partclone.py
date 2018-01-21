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

import fnmatch
import logging
import os
import signal
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


def _setup_logging(log_file=None):
    """Set up logging.

    If ``log_file`` is given, configure logging to the given file.

    """
    global logger

    logger.setLevel(logging.DEBUG)

    # Create a custom log messages formatter.
    formatter = logging.Formatter(
        fmt='{asctime} {levelname:8} {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )

    # Configure logging to a file if log file is given
    if log_file:
        # Define a Handler which writes DEBUG messages or higher to log_file.
        log_file = logging.FileHandler(log_file, mode='w')
        log_file.setLevel(logging.DEBUG)
        # Tell the handler to use this format.
        log_file.setFormatter(formatter)
        # Add the handler to the root logger.
        logger.addHandler(log_file)

    # Use str.format() syntax for logging messages.
    logger = _StyleAdapter(logger)


def _backup_partition(source_device, backup_dir, archive_size):
    """Backup the given partition using Partclone."""
    logger.info("Backing up {0}...", source_device)
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
        '--logfile', f'{backup_dir}/partclone-{source_device_name}.log',
        '--buffer_size', '10485670',
        '--clone',
        '--source', source_device,
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

    logger.info("Successfully finished backing up {0}...", source_device)


@click.group()
def cli():
    pass


@cli.command()
@click.option('--backup-dir', '-b',
              type=click.Path(file_okay=False, writable=True),
              required=True,
              help="Directory where to store the backup.")
@click.option('--archive-size', '-s', type=int, default=4096,
              help="Size (in MiBs) of the gzipped partition backup parts.",
              show_default=True)
@click.argument('source-devices', type=click.Path(exists=True), nargs=-1)
def backup(backup_dir, archive_size, source_devices):
    """Backup the given partition(s) using Partclone."""
    command_name = '{} backup'.format(os.path.basename(sys.argv[0]))

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

    log_file = os.path.join(backup_dir,
                            command_name.replace(' ', '-') + '.log')
    _setup_logging(log_file)
    logger.info("Starting {0}...", command_name)

    for source_device in source_devices:
        _backup_partition(source_device, backup_dir, archive_size)

    logger.info("Successfully finished running {0} command.", command_name)


@cli.command()
@click.option('--log-file', '-l', type=click.Path(exists=False),
              help="Path to log file.")
@click.argument('backup-file', type=click.Path(exists=True))
@click.argument('destination-device', type=click.Path(exists=False))
def restore(log_file, backup_file, destination_device):
    """Restore the given Partclone backup to the given partition."""
    command_name = '{} restore'.format(os.path.basename(sys.argv[0]))

    # Check if running as root.
    # TODO: Convert this to a decorator.
    if not os.geteuid() == 0:
        raise click.ClickException(
            "The {} script should be run as root!".format(command_name)
        )

    # TODO: Check if all commands are installed.

    _setup_logging(log_file)
    logger.info("Starting {0}...", command_name)

    # Get all backup files.
    backup_dir = os.path.dirname(backup_file)
    backup_name, _ = os.path.splitext(os.path.basename(backup_file))
    backup_files = sorted(
        [os.path.join(backup_dir, bf) for bf in os.listdir(backup_dir)
         if fnmatch.fnmatch(bf, backup_name + '.*')]
    )
    logger.info("Discovered the following backup files:")
    for backup_file in backup_files:
        logger.info("- {0}", backup_file)

    # TODO: Guess the filesystem type of the backed up partition.
    fs_type = 'ext4'

    if not destination_device.startswith('/dev/'):
        error_msg = (
            "Destination device does not start with '/dev/'.\n"
            "You should provice a destination device that starts with '/dev/'!"
        )
        logger.error(error_msg)
        raise click.ClickException(error_msg)

    click.confirm(
        f"{command_name} is about to restore the contents of a Partclone "
        f"backup to {destination_device}.\nThis will ERASE the contents of "
        f"{destination_device}!!!\nAre you sure you want to proceed?",
        abort=True,
    )

    cat_command = [
        'cat',
        *backup_files,
    ]
    gzip_command = [
        'gzip',
        '--decompress',
        '--to-stdout',
    ]
    partclone_command = [
        f'partclone.{fs_type}',
        '--restore',
        '--source', '-',
        '--output', destination_device,
    ]

    logger.info("Running restore command as a series of the following piped "
                "commands:")

    processes = []

    logger.info("- {0}", cat_command)
    process_cat = subprocess.Popen(
        cat_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    processes.append(process_cat)

    logger.info("- {0}", gzip_command)
    process_gzip = subprocess.Popen(
        gzip_command,
        stdin=process_cat.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    processes.append(process_gzip)

    logger.info("- {0}", partclone_command)
    # TODO: Capture Partclone's stderr and display it asynchrously at the same
    # time.
    process_partclone = subprocess.Popen(
        partclone_command,
        stdin=process_gzip.stdout,
        stdout=subprocess.PIPE,
    )
    processes.append(process_partclone)

    try:
        # Allow cat process to receive a SIGPIPE if gzip exits before cat.
        process_cat.stdout.close()
        # Allow gzip process to receive a SIGPIPE if Partclone exits before
        # gzip.
        process_gzip.stdout.close()
        # Interact with the Partclone process (send data to stdin, read data
        # from stdout/stderr, wait for process to terminate).
        partclone_stdout, _ = process_partclone.communicate()
    except:
        for p in processes:
            p.kill()
            p.wait()
        raise
    for p in processes:
        # Wait for the process to finish.
        retcode = p.poll()
        # Get process' stderr.
        stderr = None
        if p.stderr is not None:
            stderr = p.stderr.read().decode('utf-8')

        if retcode and retcode != 0:
            if retcode < 0:
                # Negative return code means command was terminated by a
                # signal.
                signame = signal.Signals(-retcode).name
                exception_msg = (
                    f"Command {p.args} was terminated by {signame} signal."
                )
            else:
                exception_msg = (
                    f"Command {p.args} returned non-zero exit status "
                    f"{retcode}."
                )
            if stderr:
                exception_msg += f"\nCommand's stderr:\n{stderr}"
            logger.error(exception_msg)
            # If the command was terminated by SIGPIPE signal, we want to
            # continue and report the error message of the subsequent command
            # that stopped reading from the pipe.
            if retcode != -13:
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
    logger.info("Successfully finished running restore command.")


@cli.command()
def extract():
    """Extract the given Partclone backup to the given location."""
    pass
