from __future__ import annotations

from random import randrange

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models, transaction


class Player(AbstractUser):
    max_characters = models.PositiveIntegerField(default=6)

    class Meta:
        ordering = ["username"]
        verbose_name = "player"
        verbose_name_plural = "players"


class Race(models.Model):
    name = models.CharField(max_length=63, unique=True)
    description = models.TextField()
    damage_modifier = models.FloatField()
    protection_modifier = models.FloatField()
    health_modifier = models.FloatField()
    allowed_professions = models.ManyToManyField(
        "Profession", related_name="allowed_races"
    )


class Profession(models.Model):
    name = models.CharField(max_length=63, unique=True)
    description = models.TextField()
    damage_base = models.PositiveIntegerField()
    protection_base = models.PositiveIntegerField()
    health_base = models.PositiveIntegerField()


class Character(models.Model):
    name = models.CharField(max_length=63, unique=True)
    owner = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="characters"
    )
    race = models.ForeignKey(
        Race, on_delete=models.CASCADE, related_name="characters"
    )
    profession = models.ForeignKey(
        Profession, on_delete=models.CASCADE, related_name="characters"
    )
    level = models.PositiveIntegerField(default=1)
    current_exp = models.PositiveIntegerField(default=0)
    gold = models.PositiveIntegerField(default=0)

    damage = models.PositiveIntegerField(default=1)
    health = models.PositiveIntegerField(default=100)
    protection = models.PositiveIntegerField(default=1)

    equipped_weapon = models.ForeignKey(
        "Item",
        null=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"slot": "weapon"},
        related_name="characters_with_weapon",
    )
    equipped_armor = models.ForeignKey(
        "Item",
        null=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"slot": "armor"},
        related_name="characters_with_armor",
    )
    equipped_accessory = models.ForeignKey(
        "Item",
        null=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"slot": "accessory"},
        related_name="characters_with_accessory",
    )
    inventory = models.ManyToManyField("Item", related_name="characters")

    class Meta:
        indexes = [
            models.Index(fields=["level"]),
        ]

    def clean(self):
        super().clean()
        if self.profession not in self.race.allowed_professions.all():
            raise ValidationError(
                f"{self.profession.name} profession is not allowed for {self.race.name} race."
            )

    def recalculate_stats(self) -> None:
        damage = self.profession.damage_base + self.level * 0.5
        protection = self.profession.protection_base + self.level * 0.2
        health = self.profession.health_base + self.level * 10

        for item in [
            self.equipped_weapon,
            self.equipped_armor,
            self.equipped_accessory,
        ]:
            if item is not None:
                damage += item.bonus_damage
                protection += item.bonus_protection
                health += item.bonus_health

        self.damage = round(damage * self.race.damage_modifier)
        self.protection = round(protection * self.race.protection_modifier)
        self.health = round(health * self.race.health_modifier)

    def save(self, *args, **kwargs):
        self.recalculate_stats()
        super().save(*args, **kwargs)

    @property
    def exp_for_level(self) -> int:
        return self.level**2 * 40

    def add_exp(self, exp: int) -> None:
        """Call this instead of adding exp directly to a character object."""
        self.current_exp += exp
        while self.current_exp >= self.exp_for_level:
            self.current_exp -= self.exp_for_level
            self.level += 1

    def equip_item(self, item: Item) -> None:
        if item not in self.inventory.all():
            raise ValidationError("You don't own this item.")
        if self.profession not in item.allowed_professions.all():
            raise ValidationError("This item doesn't match your profession.")
        if item.level_required > self.level:
            raise ValidationError("Your level is not high enough.")
        equipped_item = getattr(self, f"equipped_{item.slot}")
        with transaction.atomic():
            if equipped_item is not None:
                self.inventory.add(equipped_item)
            self.inventory.remove(item)
            setattr(self, f"equipped_{item.slot}", item)
            self.save()

    def unequip_item(self, item: Item) -> None:
        if item != getattr(self, f"equipped_{item.slot}"):
            raise ValidationError("Item is not equipped.")
        with transaction.atomic():
            self.inventory.add(item)
            setattr(self, f"equipped_{item.slot}", None)
            self.save()

    def buy_item(self, item: Item) -> None:
        if (
            item == getattr(self, f"equipped_{item.slot}")
            or item in self.inventory.all()
        ):
            raise ValidationError("You already have that item.")
        if item.price > self.gold:
            raise ValidationError("You don't have enough gold.")
        with transaction.atomic():
            self.inventory.add(item)
            self.gold -= item.price
            self.save()

    def sell_item(self, item: Item) -> None:
        if item not in self.inventory.all():
            raise ValidationError("You don't have that item.")
        with transaction.atomic():
            self.inventory.remove(item)
            self.gold += item.price // 2
            self.save()


class Item(models.Model):
    ITEM_SLOTS = [
        ("weapon", "Weapon"),
        ("armor", "Armor"),
        ("accessory", "Accessory"),
    ]
    ITEM_TYPES = [
        ("sword", "Sword"),
        ("axe", "Axe"),
        ("staff", "Staff"),
        ("magic_sword", "Magic Sword"),
        ("bow", "Bow"),
        ("crossbow", "Crossbow"),
        ("heavy_armor", "Heavy Armor"),
        ("medium_armor", "Medium Armor"),
        ("light_armor", "Light Armor"),
        ("accessory", "Accessory"),
    ]

    name = models.CharField(max_length=100, unique=True)
    price = models.PositiveIntegerField()
    level_required = models.PositiveIntegerField(default=1)

    slot = models.CharField(max_length=63, choices=ITEM_SLOTS)
    type = models.CharField(max_length=63, choices=ITEM_TYPES)
    allowed_professions = models.ManyToManyField(
        Profession, related_name="allowed_items"
    )

    bonus_damage = models.PositiveIntegerField(default=0)
    bonus_protection = models.PositiveIntegerField(default=0)
    bonus_health = models.PositiveIntegerField(default=0)


class Battle(models.Model):
    challenger = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        related_name="battles_as_challenger",
    )
    duelist = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        related_name="battles_as_duelist",
    )
    winner = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        related_name="battles_as_winner",
    )
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def clean(self):
        super().clean()
        if self.challenger == self.duelist:
            raise ValidationError("You can't battle yourself.")

    def calculate_winner(self) -> None:
        if self.challenger and self.duelist:
            battlers_list = [self.challenger, self.duelist]
            with transaction.atomic():
                winner = randrange(0, 1)
                self.winner = battlers_list[winner]
                loser = battlers_list[1 - winner]
                self.winner.gold += loser.level * 2
                self.winner.add_exp(loser.level * 10)
                self.winner.save()
                self.save()
        else:
            raise ValidationError("You need 2 participants.")
