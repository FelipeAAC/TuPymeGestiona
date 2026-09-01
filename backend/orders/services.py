from django.db import transaction

from organizations.models import Company

from .models import Order, OrderItem, OrderNumberSequence


class OrderNotEditableError(Exception):
    pass


def _create_items(*, order, items):
    for item in items:
        OrderItem.objects.create(
            order=order,
            variant=item["variant"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
        )


@transaction.atomic
def create_draft_order(
    *,
    company,
    branch,
    warehouse,
    customer,
    notes,
    items,
    created_by,
):
    locked_company = (
        Company.objects.select_for_update().get(
            pk=company.pk,
        )
    )

    sequence, _ = OrderNumberSequence.objects.get_or_create(
        company=locked_company,
        defaults={
            "next_number": 1,
        },
    )

    number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=("next_number",))

    order = Order.objects.create(
        company=locked_company,
        branch=branch,
        warehouse=warehouse,
        customer=customer,
        number=number,
        status=Order.Status.DRAFT,
        notes=notes,
        created_by=created_by,
    )

    _create_items(
        order=order,
        items=items,
    )

    return order


@transaction.atomic
def update_draft_order(
    *,
    order,
    validated_data,
    replace_items,
):
    locked_order = (
        Order.objects.select_for_update()
        .select_related(
            "company",
            "branch",
            "warehouse",
            "customer",
        )
        .get(pk=order.pk)
    )

    if locked_order.status != Order.Status.DRAFT:
        raise OrderNotEditableError

    items = validated_data.pop("items", None)

    for field, value in validated_data.items():
        setattr(locked_order, field, value)

    locked_order.save()

    if replace_items:
        locked_order.items.all().delete()
        _create_items(
            order=locked_order,
            items=items or [],
        )

    return locked_order
