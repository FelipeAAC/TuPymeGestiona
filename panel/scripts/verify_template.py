#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'panel.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.template.loader import get_template

try:
    template = get_template('dashboard.html')
    print("✓ TEMPLATE OK - dashboard.html compiles successfully")
except Exception as e:
    print(f"✗ ERROR: {e}")
    sys.exit(1)
