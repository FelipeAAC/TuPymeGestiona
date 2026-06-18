from django.test import TestCase, Client
from decimal import Decimal
import json

from .models import Product, Order, Customer, Message


class OrderAndMessageTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(name='Prueba', sku='PRU1', stock=10, price=Decimal('15000'))

    def test_quick_order_with_cart_reduces_stock(self):
        cart = [{"product_id": self.product.id, "qty": 3}]
        resp = self.client.post('/order/', {'customer': 'Cliente Test', 'cart_items': json.dumps(cart)})
        self.assertEqual(resp.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)
        orders = Order.objects.filter(product=self.product)
        self.assertEqual(orders.count(), 1)
        self.assertEqual(orders.first().qty, 3)

    def test_quick_message_creates_message(self):
        resp = self.client.post('/message/', {'customer': 'Miguel', 'text': 'Hola prueba'})
        self.assertEqual(resp.status_code, 302)
        c = Customer.objects.filter(name__iexact='Miguel').first()
        self.assertIsNotNone(c)
        msgs = Message.objects.filter(customer=c)
        self.assertTrue(msgs.exists())
        self.assertEqual(msgs.first().text, 'Hola prueba')
from django.test import TestCase

# Create your tests here.
