from django.template.loader import get_template
import traceback

try:
    get_template('base.html')
    print('TEMPLATE OK')
except Exception:
    traceback.print_exc()
