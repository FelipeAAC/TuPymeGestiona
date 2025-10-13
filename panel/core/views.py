from django.db import transaction
from django.db.models import F, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages

from .models import Product, Order, Customer, Message, ActivityLog


def log(action, message, **meta):
    ActivityLog.objects.create(action=action, message=message, meta=meta)


def dashboard(request):
    products = Product.objects.order_by("name")[:50]
    orders = (
        Order.objects
        .select_related("customer", "product")
        .order_by("-created_at")[:10]
    )
    messages_list = (
        Message.objects
        .select_related("customer")
        .order_by("-created_at")[:5]
    )

    low_stock = Product.objects.filter(stock__lte=5, stock__gt=0).count()
    out_stock = Product.objects.filter(stock=0).count()
    total_products = Product.objects.count()
    total_units = Product.objects.aggregate(total=Sum("stock"))["total"] or 0
    inventory_value = Product.objects.aggregate(
        total=Sum(F("stock") * F("price"))
    )["total"] or 0
    top_low = Product.objects.order_by("stock", "name")[:5]
    oos_products = Product.objects.filter(stock=0).order_by("name")

    ticker = ActivityLog.objects.order_by("-created_at")[:3]
    timeline = ActivityLog.objects.order_by("-created_at")[:20]

    customer_ids = [m.customer_id for m in messages_list]
    last_orders_qs = (
        Order.objects
        .filter(customer_id__in=customer_ids)
        .select_related("product", "customer")
        .order_by("-created_at")
    )
    last_by_customer = {}
    for o in last_orders_qs:
        if o.customer_id not in last_by_customer:
            last_by_customer[o.customer_id] = o
    for m in messages_list:
        m.last_order = last_by_customer.get(m.customer_id)

    now = timezone.localtime(timezone.now())
    page_title = "Panel Único Pyme — Dashboard"
    og_title = "Panel Único Pyme"
    og_description = "Administra tu inventario, ventas y clientes desde un solo panel."
    og_image = "img/preview.png"

    return render(request, "dashboard.html", {
        "products": products,
        "orders": orders,
        "messages": messages_list,
        "low_stock": low_stock,
        "out_stock": out_stock,
        "total_products": total_products,
        "total_units": total_units,
        "inventory_value": inventory_value,
        "top_low": top_low,
        "out_of_stock_products": oos_products,
        "ticker": ticker,
        "timeline": timeline,
        "now": now,
        "page_title": "Panel Único Pyme — Dashboard",
        "og_title": "Panel Único Pyme",
        "og_description": "Administra tu inventario, ventas y clientes desde un solo panel.",
        "og_image": "img/preview.png",
    })


def quick_add_product(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        sku = (request.POST.get("sku") or "").strip()
        stock_str = (request.POST.get("stock") or "0").strip()
        price_str = (request.POST.get("price") or "0").strip()

        if not name or not sku:
            messages.error(request, "El nombre y el SKU son obligatorios.")
            return redirect("dashboard")

        if Product.objects.filter(sku=sku).exists():
            messages.error(request, f"El SKU '{sku}' ya existe.")
            return redirect("dashboard")

        try:
            stock = max(0, int(stock_str))
            price = float(price_str)
        except ValueError:
            messages.error(request, "Stock y precio deben ser números válidos.")
            return redirect("dashboard")

        p = Product.objects.create(name=name, sku=sku, stock=stock, price=price)
        messages.success(request, f"Producto '{name}' agregado con éxito.")
        log(ActivityLog.PRODUCT_ADD, f"Alta de producto '{p.name}'",
            sku=p.sku, stock=p.stock, price=float(p.price))

        if p.stock == 0:
            log(ActivityLog.OUT_OF_STOCK, f"'{p.name}' quedó sin stock", sku=p.sku)

    return redirect("dashboard")


def quick_order(request):
    if request.method == "POST":
        customer_name = (request.POST.get("customer") or "").strip()
        product_id = request.POST.get("product_id")
        qty_str = request.POST.get("qty") or "1"

        if not customer_name or not product_id:
            messages.error(request, "Debes seleccionar un producto e indicar el cliente.")
            return redirect("dashboard")

        try:
            qty = int(qty_str)
            if qty < 1:
                raise ValueError
        except ValueError:
            messages.error(request, "La cantidad debe ser un número válido (≥ 1).")
            return redirect("dashboard")

        product = get_object_or_404(Product, pk=product_id)

        try:
            with transaction.atomic():
                product.refresh_from_db()
                if product.stock < qty:
                    messages.error(
                        request,
                        f"Stock insuficiente para '{product.name}'. Disponible: {product.stock}."
                    )
                    return redirect("dashboard")

                customer, _ = Customer.objects.get_or_create(name=customer_name)
                Order.objects.create(customer=customer, product=product, qty=qty)
                Product.objects.filter(pk=product.pk).update(stock=F("stock") - qty)

            messages.success(request, f"Venta registrada: {qty} × '{product.name}'.")
            log(ActivityLog.ORDER, f"Venta {qty} × '{product.name}' a {customer_name}",
                sku=product.sku, qty=qty)

            product.refresh_from_db()
            if product.stock == 0:
                log(ActivityLog.OUT_OF_STOCK, f"'{product.name}' quedó sin stock", sku=product.sku)

        except Exception:
            messages.error(request, "No se pudo registrar la venta. Intenta nuevamente.")

    return redirect("dashboard")


def quick_message(request):
    if request.method == "POST":
        customer_name = (request.POST.get("customer") or "").strip()
        text = (request.POST.get("text") or "").strip()

        if not customer_name or not text:
            messages.error(request, "Cliente y mensaje son obligatorios.")
            return redirect("dashboard")

        customer, _ = Customer.objects.get_or_create(name=customer_name)
        Message.objects.create(customer=customer, text=text)
        messages.success(request, f"Mensaje enviado a '{customer_name}'.")
        log(ActivityLog.MESSAGE, f"Mensaje a {customer_name}", preview=text[:80])

    return redirect("dashboard")


def restock(request):
    if request.method == "POST":
        product_id = request.POST.get("product_id")
        qty_str = request.POST.get("qty") or "0"

        try:
            qty = int(qty_str)
            if qty < 1:
                raise ValueError
        except ValueError:
            messages.error(request, "Cantidad de reposición inválida.")
            return redirect("dashboard")

        p = get_object_or_404(Product, pk=product_id)
        Product.objects.filter(pk=p.pk).update(stock=F("stock") + qty)
        p.refresh_from_db()

        messages.success(request, f"Se repusieron {qty} unid. de '{p.name}'. Stock actual: {p.stock}.")
        log(ActivityLog.RESTOCK, f"Reposición {qty} unid. de '{p.name}'",
            sku=p.sku, new_stock=p.stock)

    return redirect("dashboard")
