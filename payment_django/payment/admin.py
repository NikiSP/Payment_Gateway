from django.contrib import admin

from payment.models.banks import Bank


class BankAdmin(admin.ModelAdmin):
    fields = [
        "pk",
        "status",
        "tracking_code",
        "amount",
        "game_id",
        "reference_number",
        "response_result",
        "callback_url",
        "extra_information",
        "created_at",
        "update_at",
    ]
    list_display = [
        "pk",
        "status",
        "tracking_code",
        "amount",
        "game_id",
        "reference_number",
        "response_result",
        "callback_url",
        "extra_information",
        "created_at",
        "update_at",
    ]
    list_filter = [
        "status",
        "created_at",
        "update_at",
    ]
    search_fields = [
        "status",
        "tracking_code",
        "amount",
        "game_id",
        "reference_number",
        "response_result",
        "callback_url",
        "extra_information",
        "created_at",
        "update_at",
    ]
    exclude = []
    dynamic_raw_id_fields = []
    readonly_fields = [
        "pk",
        "status",
        "tracking_code",
        "amount",
        "game_id",
        "reference_number",
        "response_result",
        "callback_url",
        "extra_information",
        "created_at",
        "update_at",
    ]


admin.site.register(Bank, BankAdmin)