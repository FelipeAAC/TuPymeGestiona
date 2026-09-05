import hashlib
import json
import uuid
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q

from customers.models import Customer
from inventory.models import InventoryStock
from orders.services import confirm_order, create_draft_order
from organizations.models import Warehouse

from .models import CustomerPortalAccount, PortalOrderRequest

User = get_user_model()


class PortalConflictError(Exception):
    pass


class PortalStockError(Exception):
    pass


def canonical_order_hash(
    *,
    company_id,
    branch_id,
    items,
    delivery_address,
    delivery_commune,
    delivery_city,
    notes,
):
    payload = {
        "company": company_id,
        "branch": branch_id,
        "delivery_address": delivery_address.strip(),
        "delivery_commune": delivery_commune.strip(),
        "delivery_city": delivery_city.strip(),
        "notes": notes.strip(),
        "items": sorted(
            [
                {
                    "variant": item["variant"].id,
                    "quantity": format(item["quantity"], "f"),
                }
                for item in items
            ],
            key=lambda item: item["variant"],
        ),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@transaction.atomic
def register_portal_customer(
    *,
    email,
    password,
    first_name,
    last_name,
    company=None,
    phone="",
    address="",
    commune="",
    city="",
):
    normalized_email = email.strip().lower()
    if User.objects.filter(email__iexact=normalized_email).exists():
        raise PortalConflictError("Ya existe una cuenta con ese correo electrónico.")

    username_base = normalized_email[:140] or f"cliente-{uuid.uuid4().hex[:8]}"
    username = username_base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{username_base[:140-len(str(suffix))-1]}-{suffix}"

    user = User.objects.create_user(
        username=username,
        email=normalized_email,
        password=password,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )
    if company is None:
        return user, None

    code = _next_customer_code(company=company)
    customer = Customer.objects.create(
        company=company,
        code=code,
        name=" ".join(part for part in [first_name.strip(), last_name.strip()] if part),
        email=normalized_email,
        phone=phone.strip(),
        address=address.strip(),
        commune=commune.strip(),
        city=city.strip(),
        status=Customer.Status.ACTIVE,
    )
    account = CustomerPortalAccount.objects.create(
        user=user,
        company=company,
        customer=customer,
        status=CustomerPortalAccount.Status.ACTIVE,
    )
    return user, account


def _next_customer_code(*, company):
    code = f"WEB-{uuid.uuid4().hex[:10].upper()}"
    while Customer.objects.filter(company=company, code=code).exists():
        code = f"WEB-{uuid.uuid4().hex[:10].upper()}"
    return code


def get_active_portal_account(*, user, company):
    return (
        CustomerPortalAccount.objects.filter(
            user=user,
            company=company,
            status=CustomerPortalAccount.Status.ACTIVE,
            customer__status=Customer.Status.ACTIVE,
        )
        .select_related("company", "customer")
        .first()
    )


def ensure_portal_account_for_order(
    *,
    user,
    company,
    delivery_address,
    delivery_commune,
    delivery_city,
):
    account = get_active_portal_account(user=user, company=company)
    if account is not None:
        return account

    existing = (
        CustomerPortalAccount.objects.filter(user=user, company=company)
        .select_related("customer")
        .first()
    )
    if existing is not None:
        raise PortalConflictError("Tu relación con esta tienda está suspendida.")

    customer = (
        Customer.objects.filter(
            company=company,
            email__iexact=user.email,
            status=Customer.Status.ACTIVE,
            portal_account__isnull=True,
        )
        .order_by("id")
        .first()
    )
    if customer is None:
        customer = Customer.objects.create(
            company=company,
            code=_next_customer_code(company=company),
            name=" ".join(
                part for part in [user.first_name.strip(), user.last_name.strip()] if part
            )
            or user.email,
            email=user.email.strip().lower(),
            phone="",
            address=delivery_address.strip(),
            commune=delivery_commune.strip(),
            city=delivery_city.strip(),
            status=Customer.Status.ACTIVE,
        )

    return CustomerPortalAccount.objects.create(
        user=user,
        company=company,
        customer=customer,
        status=CustomerPortalAccount.Status.ACTIVE,
    )


def _candidate_warehouses(*, company, branch):
    return Warehouse.objects.filter(company=company).filter(
        Q(branch=branch) | Q(branch__isnull=True)
    ).order_by("branch_id", "name", "id")


def select_warehouse_with_stock(*, company, branch, items):
    warehouses = list(_candidate_warehouses(company=company, branch=branch))
    if not warehouses:
        return None

    required = {item["variant"].id: item["quantity"] for item in items}
    quantities: dict[int, dict[int, Decimal]] = defaultdict(dict)
    rows = InventoryStock.objects.filter(
        warehouse__in=warehouses,
        variant_id__in=required,
    ).values_list("warehouse_id", "variant_id", "quantity")
    for warehouse_id, variant_id, quantity in rows:
        quantities[warehouse_id][variant_id] = quantity

    for warehouse in warehouses:
        stock = quantities[warehouse.id]
        if all(stock.get(variant_id, Decimal("0")) >= quantity for variant_id, quantity in required.items()):
            return warehouse
    return None


@transaction.atomic
def create_portal_order(
    *,
    user,
    company,
    branch,
    items,
    delivery_address,
    delivery_commune,
    delivery_city,
    notes,
    idempotency_key,
):
    account = ensure_portal_account_for_order(
        user=user,
        company=company,
        delivery_address=delivery_address,
        delivery_commune=delivery_commune,
        delivery_city=delivery_city,
    )

    request_hash = canonical_order_hash(
        company_id=company.id,
        branch_id=branch.id,
        items=items,
        delivery_address=delivery_address,
        delivery_commune=delivery_commune,
        delivery_city=delivery_city,
        notes=notes,
    )

    existing = (
        PortalOrderRequest.objects.select_for_update()
        .filter(user=user, company=company, idempotency_key=idempotency_key)
        .select_related("order")
        .first()
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise PortalConflictError("La clave idempotente ya fue utilizada con datos diferentes.")
        return existing.order, False

    warehouse = select_warehouse_with_stock(company=company, branch=branch, items=items)
    if warehouse is None:
        raise PortalStockError("No hay stock suficiente en una bodega disponible para esta sucursal.")

    order_items = [
        {
            "variant": item["variant"],
            "quantity": item["quantity"],
            "unit_price": item["variant"].base_price,
        }
        for item in items
    ]

    order = create_draft_order(
        company=company,
        branch=branch,
        warehouse=warehouse,
        customer=account.customer,
        notes=notes.strip(),
        items=order_items,
        created_by=user,
    )
    order.delivery_address = delivery_address.strip()
    order.delivery_commune = delivery_commune.strip()
    order.delivery_city = delivery_city.strip()
    order.save(
        update_fields=(
            "delivery_address",
            "delivery_commune",
            "delivery_city",
            "updated_at",
        )
    )

    try:
        order = confirm_order(order=order, performed_by=user)
    except ValidationError as exc:
        raise PortalStockError("El stock cambió antes de confirmar el pedido.") from exc

    try:
        PortalOrderRequest.objects.create(
            user=user,
            company=company,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            order=order,
        )
    except IntegrityError as exc:
        raise PortalConflictError("No fue posible estabilizar la solicitud idempotente.") from exc

    return order, True
