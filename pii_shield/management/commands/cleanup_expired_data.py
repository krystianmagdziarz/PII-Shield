"""
Management command for cleaning up expired PII data.
"""

import logging
import time
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from django.utils import timezone

from pii_shield.models import PIIModel
from pii_shield.sync import get_registered_models

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up expired PII data from the frontend database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to delete in each batch',
        )
        
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.5,
            help='Sleep time between batches (seconds)',
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup, even for models not registered for synchronization',
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not delete any data, just print what would be deleted',
        )
    
    def handle(self, *args, **options):
        batch_size = options['batch_size']
        sleep_time = options['sleep']
        force = options['force']
        dry_run = options['dry_run']
        
        # Get models to clean up
        models = []
        
        if force:
            # Get all models inheriting from PIIModel
            for model in apps.get_models():
                if issubclass(model, PIIModel) and model != PIIModel:
                    models.append(model)
        else:
            # Get registered models
            models = get_registered_models()
        
        if not models:
            self.stdout.write(self.style.WARNING('No models to clean up'))
            return
        
        # Log what we're doing
        self.stdout.write(f'Cleaning up expired data for {len(models)} models')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: No data will be deleted'))
        
        total_deleted = 0
        
        # Clean up expired data for each model
        for model in models:
            self.stdout.write(f'Processing {model.__name__}')
            model_deleted = 0
            
            while True:
                # Get expired records
                expired = model.objects.filter(
                    data_expires_at__lt=timezone.now()
                ).order_by('data_expires_at')[:batch_size]
                
                # Get count before converting to list
                count = expired.count()
                
                if count == 0:
                    break
                
                # Delete records
                if not dry_run:
                    with transaction.atomic():
                        # Get IDs of expired records
                        expired_ids = list(expired.values_list('id', flat=True))
                        
                        # Delete records
                        deleted, _ = model.objects.filter(id__in=expired_ids).delete()
                        
                        model_deleted += deleted
                        total_deleted += deleted
                else:
                    # Just count records in dry run mode
                    model_deleted += count
                    total_deleted += count
                
                # Print progress
                self.stdout.write(f'  Deleted {model_deleted} records from {model.__name__}')
                
                # Sleep between batches
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
                # If fewer records than batch size, we're done
                if count < batch_size:
                    break
        
        # Print summary
        self.stdout.write(self.style.SUCCESS(f'Successfully cleaned up {total_deleted} expired records')) 