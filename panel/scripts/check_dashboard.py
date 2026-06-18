import os
import sys
import django
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'panel.settings')

django.setup()

from django.template.loader import get_template

try:
    get_template('dashboard.html')
    print('TEMPLATE OK')
except Exception:
    traceback.print_exc()
