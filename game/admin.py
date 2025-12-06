from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from game import models


admin.site.unregister(Group)


@admin.register(get_user_model())
class PlayerAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ("max_characters",)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Game info", {"fields": ("max_characters",)}),
    )
    fieldsets = UserAdmin.fieldsets + (
        ("Game info", {"fields": ("max_characters",)}),
    )


@admin.register(models.Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "race",
        "profession",
        "level",
        "damage",
        "protection",
        "health",
    )
    search_fields = ("name",)


@admin.register(models.Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "damage_modifier",
        "protection_modifier",
        "health_modifier",
    )
    search_fields = ("name",)


@admin.register(models.Profession)
class ProfessionAdmin(admin.ModelAdmin):
    list_display = ("name", "damage_base", "protection_base", "health_base")
    search_fields = ("name",)


@admin.register(models.Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slot",
        "type",
        "price",
        "level_required",
        "bonus_damage",
        "bonus_protection",
    )
    search_fields = ("name",)
    list_filter = (
        "slot",
        "type",
    )


@admin.register(models.Battle)
class BattleAdmin(admin.ModelAdmin):
    list_display = ("date", "attacker", "defender", "winner")
    search_fields = (
        "attacker__name",
        "defender__name",
    )
