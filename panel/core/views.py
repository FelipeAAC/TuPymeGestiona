import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.db import transaction
from django.db.models import F, Sum, Count
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib import messages

from .models import Product, Order, Customer, Message, ActivityLog


def log(action, message, **meta):
    ActivityLog.objects.create(action=action, message=message, meta=meta)


def _safe_int(value, default=0, min_value=0):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(number, min_value)


def _safe_decimal(value, default=Decimal("0.00"), min_value=Decimal("0.00")):
    try:
        number = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return default
    if number < min_value:
        return min_value
    return number


def _generate_order_number():
    return f"PED-{uuid4().hex[:8].upper()}"


def dashboard(request):
    products = Product.objects.order_by("name")[:50]
    orders = (
        Order.objects
        .select_related("customer", "product")
        .order_by("-created_at")[:20]
    )
    customer_messages = (
        Message.objects
        .select_related("customer")
        .order_by("-created_at")[:50]
    )

    # Agrupar mensajes por cliente para mostrar hilo de conversación
    messages_grouped = []
    seen_customers = set()
    for m in customer_messages:
        cid = m.customer_id
        if cid in seen_customers:
            continue
        seen_customers.add(cid)
        msgs = list(Message.objects.filter(customer_id=cid).order_by('created_at')[:50])
        last_order = (
            Order.objects.filter(customer_id=cid).select_related('product').order_by('-created_at').first()
        )
        messages_grouped.append({
            'customer': m.customer,
            'messages': msgs,
            'last_order': last_order,
        })

    order_groups = []
    grouped = {}
    for order in orders:
        key = order.order_number or f"OC{order.id}"
        if key not in grouped:
            grouped[key] = {
                'order_number': key,
                'customer': order.customer,
                'created_at': order.created_at,
                'items': [],
                'payment_method': order.payment_method or 'Pendiente',
                'delivery_zone': order.delivery_zone or 'No definida',
                'delivery_address': order.delivery_address or 'No definida',
                'total': Decimal('0.00'),
            }
        grouped[key]['items'].append(order)
        grouped[key]['total'] += order.line_total
    order_groups = list(grouped.values())

    # Build conversations per order (order_number) so chats are exclusive per purchase
    messages_grouped_by_order = []
    for og in order_groups:
        msgs = list(Message.objects.filter(order_number=og['order_number']).order_by('created_at'))
        # if no messages exist, we may still want to show the order as a conversation
        messages_grouped_by_order.append({
            'order_number': og['order_number'],
            'customer': og['customer'],
            'created_at': og['created_at'],
            'items': og['items'],
            'total': og['total'],
            'messages': msgs,
        })

    selected_order_number = request.GET.get("selected_order")
    selected_order = None
    if selected_order_number:
        for g in messages_grouped_by_order:
            if g['order_number'] == selected_order_number:
                selected_order = g
                break
    if selected_order is None and messages_grouped_by_order:
        selected_order = messages_grouped_by_order[0]

    active_tab = 'messages' if selected_order else 'inventory'

    low_stock = Product.objects.filter(stock__lte=5, stock__gt=0).count()
    out_stock = Product.objects.filter(stock=0).count()
    total_products = Product.objects.count()
    total_units = Product.objects.aggregate(total=Sum("stock"))["total"] or 0
    inventory_value = Product.objects.aggregate(
        total=Sum(F("stock") * F("price"))
    )["total"] or 0
    top_low = Product.objects.order_by("stock", "name")[:5]
    oos_products = Product.objects.filter(stock=0).order_by("name")
    all_products = Product.objects.order_by("name")

    ticker = ActivityLog.objects.order_by("-created_at")[:3]
    timeline = ActivityLog.objects.order_by("-created_at")[:20]

    sales_by_month = (
        Order.objects
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total_sales=Sum(F('qty') * F('product__price')),
                  total_items=Sum('qty'),
                  order_count=Count('id'))
        .order_by('-month')[:6]
    )
    sales_by_month = [
        {
            'month': s['month'],
            'sales': s['total_sales'] or Decimal('0.00'),
            'items': s['total_items'] or 0,
            'orders': s['order_count'] or 0,
        }
        for s in sales_by_month
    ][::-1]

    now = timezone.localtime(timezone.now())

    return render(request, "dashboard.html", {
        "products": products,
        "orders": orders,
        "order_groups": order_groups,
        "customer_messages": customer_messages,
        "messages_grouped": messages_grouped_by_order,
        "selected_order": selected_order,
        "selected_order_number": selected_order and selected_order.get('order_number') or None,
        "active_tab": active_tab,
        "low_stock": low_stock,
        "out_stock": out_stock,
        "total_products": total_products,
        "total_units": total_units,
        "inventory_value": inventory_value,
        "top_low": top_low,
        "out_of_stock_products": oos_products,
        "all_products": all_products,
        "ticker": ticker,
        "timeline": timeline,
        "sales_by_month": sales_by_month,
        "now": now,
    })


@require_POST
def quick_add_product(request):
    name = (request.POST.get("name") or "").strip()
    sku = (request.POST.get("sku") or "").strip()
    stock_str = (request.POST.get("stock") or "0").strip()
    price_str = (request.POST.get("price") or "0").strip()

    if not name or not sku:
        messages.error(request, "El nombre y el SKU son obligatorios.")
        return redirect("dashboard")

    if Product.objects.filter(sku__iexact=sku).exists():
        messages.error(request, f"El SKU '{sku}' ya existe.")
        return redirect("dashboard")

    stock = _safe_int(stock_str)
    price = _safe_decimal(price_str)

    if stock < 0 or price < 0:
        messages.error(request, "Stock y precio deben ser números válidos.")
        return redirect("dashboard")

    p = Product.objects.create(name=name, sku=sku, stock=stock, price=price)
    messages.success(request, f"Producto '{name}' agregado con éxito.")
    log(
        ActivityLog.PRODUCT_ADD,
        f"Alta de producto '{p.name}'",
        sku=p.sku,
        stock=p.stock,
        price=str(p.price),
    )

    if p.stock == 0:
        log(ActivityLog.OUT_OF_STOCK, f"'{p.name}' quedó sin stock", sku=p.sku)

    return redirect("dashboard")


def _get_or_create_customer(name):
    name = (name or "").strip()
    if not name:
        return None
    customer = Customer.objects.filter(name__iexact=name).first()
    if customer is None:
        customer = Customer.objects.create(name=name)
    return customer


@require_POST
def quick_order(request):
    customer_name = (request.POST.get("customer") or "").strip()
    payment_method = (request.POST.get("payment_method") or "").strip()
    delivery_zone = (request.POST.get("delivery_zone") or "").strip()
    delivery_address = (request.POST.get("delivery_address") or "").strip()
    product_id = request.POST.get("product_id")
    qty_str = request.POST.get("qty") or "1"
    cart_payload = (request.POST.get("cart_items") or "").strip()

    cart_items = []
    if cart_payload:
        try:
            parsed = json.loads(cart_payload)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and item.get("product_id") and item.get("qty"):
                        cart_items.append({
                            "product_id": str(item.get("product_id")),
                            "qty": str(item.get("qty")),
                        })
        except json.JSONDecodeError:
            cart_items = []

    if not customer_name:
        messages.error(request, "Debes indicar el cliente.")
        return redirect("dashboard")

    order_number = _generate_order_number()

    if cart_items:
        items = cart_items
    else:
        if not product_id:
            messages.error(request, "Debes seleccionar un producto.")
            return redirect("dashboard")
        items = [{"product_id": product_id, "qty": qty_str}]

    try:
        with transaction.atomic():
            customer = _get_or_create_customer(customer_name)
            total_qty = 0
            total_items = []
            for item in items:
                qty = _safe_int(item["qty"], default=0, min_value=1)
                if qty < 1:
                    messages.error(request, "Las cantidades deben ser números válidos.")
                    return redirect("dashboard")

                try:
                    product = get_object_or_404(Product, pk=int(item["product_id"]))
                except (TypeError, ValueError):
                    messages.error(request, "Producto inválido.")
                    return redirect("dashboard")

                product.refresh_from_db()
                if product.stock < qty:
                    messages.error(
                        request,
                        f"Stock insuficiente para '{product.name}'. Disponible: {product.stock}."
                    )
                    return redirect("dashboard")

                Order.objects.create(
                    customer=customer,
                    product=product,
                    qty=qty,
                    order_number=order_number,
                    payment_method=payment_method,
                    delivery_zone=delivery_zone,
                    delivery_address=delivery_address,
                )
                Product.objects.filter(pk=product.pk).update(stock=F("stock") - qty, updated_at=timezone.now())
                total_qty += qty
                total_items.append(f"{qty}×{product.name}")

            message_text = ", ".join(total_items)
            messages.success(request, f"Pedido registrado: {total_qty} items.")
            log(
                ActivityLog.ORDER,
                f"Pedido {order_number} a {customer_name}: {message_text}",
                order_number=order_number,
                qty=total_qty,
                payment_method=payment_method,
            )

            # create an initial admin-only message summarizing the order (linked by order_number)
            Message.objects.create(
                customer=customer,
                text=f"Resumen de pedido {order_number}: {message_text}",
                sender=Message.SENDER_ADMIN,
                order_number=order_number,
            )

            for item in items:
                product = Product.objects.get(pk=int(item["product_id"]))
                if product.stock == 0:
                    log(ActivityLog.OUT_OF_STOCK, f"'{product.name}' quedó sin stock", sku=product.sku)

    except Exception:
        messages.error(request, "No se pudo registrar la venta. Intenta nuevamente.")
        return redirect("dashboard")

    return redirect("dashboard")


@require_POST
def quick_message(request):
    customer_id = request.POST.get("customer_id")
    customer_name = (request.POST.get("customer") or "").strip()
    text = (request.POST.get("text") or "").strip()
    sender = request.POST.get("sender") or Message.SENDER_ADMIN
    order_number = (request.POST.get("order_number") or "").strip()

    if not text or (not customer_id and not customer_name):
        messages.error(request, "Cliente y mensaje son obligatorios.")
        return redirect("dashboard")

    customer = None
    if customer_id:
        try:
            customer = Customer.objects.get(pk=int(customer_id))
        except (Customer.DoesNotExist, ValueError, TypeError):
            customer = None
    if customer is None:
        customer = _get_or_create_customer(customer_name)

    if sender not in dict(Message.SENDER_CHOICES):
        sender = Message.SENDER_ADMIN

    Message.objects.create(customer=customer, text=text, sender=sender, order_number=order_number or None)
    messages.success(request, f"Mensaje enviado a '{customer.name}'.")
    log(ActivityLog.MESSAGE, f"Mensaje a {customer.name}", preview=text[:80], sender=sender)

    # redirect to messages tab for the specific order if provided
    if order_number:
        return redirect(f"/?selected_order={order_number}#messages")
    return redirect(f"/?selected_order={customer.id}#messages")


@require_POST
def restock(request):
    product_id = request.POST.get("product_id")
    qty = _safe_int(request.POST.get("qty") or "0", default=0, min_value=1)

    if qty < 1:
        messages.error(request, "Cantidad de reposición inválida.")
        return redirect("dashboard")

    try:
        p = get_object_or_404(Product, pk=int(product_id))
    except (TypeError, ValueError):
        messages.error(request, "Producto inválido.")
        return redirect("dashboard")

    Product.objects.filter(pk=p.pk).update(stock=F("stock") + qty, updated_at=timezone.now())
    p.refresh_from_db()

    messages.success(request, f"Se repusieron {qty} unid. de '{p.name}'. Stock actual: {p.stock}.")
    log(
        ActivityLog.RESTOCK,
        f"Reposición {qty} unid. de '{p.name}'",
        sku=p.sku,
        new_stock=p.stock,
    )

    return redirect("dashboard")
