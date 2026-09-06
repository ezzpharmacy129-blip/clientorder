"""Central order workflow rules used by the PostgreSQL data layer."""

STATUS_PICKED_UP = "تم الاستلام"
STATUS_CONTACTED = "تم التواصل - بانتظار الاستلام"
STATUS_NOT_PICKED = "لم يستلم"
CONTACT_ACCEPTED = "العميل موافق"

def active_items(order, items):
    """Return items that remain part of the order after customer rejections."""
    return [
        item for item in (items or [])
        if str(item.get("Customer_Decision") or "").strip() != "rejected"
    ]

def validate_pickup(order, items):
    """Return an Arabic error message when pickup is not a valid transition."""
    current = str(order.get("Status") or "").strip()
    if current not in {STATUS_CONTACTED, STATUS_NOT_PICKED}:
        return f"لا يمكن تسجيل الاستلام والحالة الحالية هي: {current or 'غير معروفة'}"

    active = active_items(order, items)
    if not active:
        return "لا يمكن تسجيل الاستلام لأنه لا توجد منتجات فعالة في الطلب"

    pending = [
        item.get("Product_Name") or "منتج"
        for item in active
        if str(item.get("Availability_Status") or "").strip() != "متوفر"
    ]
    if pending:
        return "لا يمكن تسجيل الاستلام قبل توفر جميع المنتجات المطلوبة: " + "، ".join(pending)

    if str(order.get("Contact_Status") or "").strip() != CONTACT_ACCEPTED:
        return "لا يمكن تسجيل الاستلام قبل تأكيد موافقة العميل"

    return None

def validate_status_override(current_status, requested_status):
    """Direct status edits are forbidden; workflow actions own state transitions."""
    if requested_status is None:
        return None
    return (
        "تغيير حالة الطلب مباشرة غير مسموح. استخدم إجراء الحالة المناسب "
        "حتى يتم التحقق من قواعد سير الطلب."
    )

def validate_not_picked(order, items):
    current = str(order.get("Status") or "").strip()
    if current != STATUS_PICKED_UP:
        return f"يمكن تسجيل «لم يستلم» فقط بعد تسجيل الاستلام، والحالة الحالية هي: {current or 'غير معروفة'}"
    active = active_items(order, items)
    if not active:
        return "لا يمكن تصحيح الاستلام لطلب لا يحتوي على منتجات فعالة"
    return None
