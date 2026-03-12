"""
Database backup management command.

Creates a JSON/XML dump of application data using Django's dumpdata.
Excludes ephemeral data (sessions, permissions, content types, admin log).

Usage:
    python manage.py dbbackup                          # backup_20260312_143000.json
    python manage.py dbbackup -o my_backup.json        # custom filename
    python manage.py dbbackup --format xml             # XML format
    python manage.py dbbackup --latest 5               # keep only 5 most recent backups
"""

import os
import glob
import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create a database backup (JSON/XML dump of application data)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', '-o',
            type=str,
            default=None,
            help='Output file path (default: backup_YYYYMMDD_HHMMSS.<format>)',
        )
        parser.add_argument(
            '--format', '-f',
            type=str,
            choices=['json', 'xml'],
            default='json',
            help='Serialization format (default: json)',
        )
        parser.add_argument(
            '--latest',
            type=int,
            default=None,
            help='Keep only the N most recent backup files in the output directory',
        )

    def handle(self, *args, **options):
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        fmt = options['format']
        output = options['output'] or f'backup_{timestamp}.{fmt}'

        self.stdout.write(f'Creating {fmt.upper()} backup …')

        try:
            with open(output, 'w', encoding='utf-8') as f:
                call_command(
                    'dumpdata',
                    '--natural-foreign',
                    '--natural-primary',
                    '--indent', '2',
                    '--format', fmt,
                    # Exclude ephemeral / auto-generated data
                    '--exclude', 'contenttypes',
                    '--exclude', 'auth.permission',
                    '--exclude', 'sessions.session',
                    '--exclude', 'admin.logentry',
                    stdout=f,
                )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Backup failed: {e}'))
            # Clean up partial file
            if os.path.exists(output):
                os.remove(output)
            return

        file_size = os.path.getsize(output)
        self.stdout.write(
            self.style.SUCCESS(f'Backup saved to {output} ({file_size:,} bytes)')
        )

        # Prune old backups if --latest is set
        keep = options['latest']
        if keep and keep > 0:
            output_dir = os.path.dirname(os.path.abspath(output))
            pattern = os.path.join(output_dir, f'backup_*.{fmt}')
            existing = sorted(glob.glob(pattern), reverse=True)
            pruned = 0
            for old_file in existing[keep:]:
                os.remove(old_file)
                pruned += 1
            if pruned:
                self.stdout.write(f'Pruned {pruned} old backup(s), kept {keep}.')
