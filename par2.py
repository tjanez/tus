# A script for handling PAR2 recovery files for backup directories.

# Copyright 2017 Tadej Janež.
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

import os
import subprocess
import shlex

import click


@click.group()
def cli():
    pass


@cli.command()
@click.argument('backup-dir', type=click.Path(exists=True))
def compute(backup_dir):
    """Compute PAR2 recovery files for the given backup directory."""
    recovery_dir = os.path.join(backup_dir, 'recovery')
    _, _, backup_name = backup_dir.rpartition(os.sep)
    if not os.path.exists(recovery_dir):
        os.makedirs(recovery_dir)
    subprocess.run(
        shlex.split(f'par2 create -B{backup_dir} -r5 -u {backup_name} '
                    f'{backup_dir}/*'),
        cwd=recovery_dir
    )


@cli.command()
@click.argument('backup-dir', type=click.Path(exists=True))
def verify(backup_dir):
    """Verify PAR2 recovery files for the given backup directory."""
    recovery_dir = os.path.join(backup_dir, 'recovery')
    _, _, backup_name = backup_dir.rpartition(os.sep)
    if not os.path.exists(recovery_dir):
        raise click.ClickException(
            f"Recovery directory '{recovery_dir}' does not exist. You should "
            "run 'tus-par2 compute' first!"
        )
    subprocess.run(
        shlex.split(f'par2 verify -B{backup_dir} '
                    f'{recovery_dir}/{backup_name}.par2'),
    )
