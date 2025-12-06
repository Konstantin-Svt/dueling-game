from __future__ import annotations

from random import randrange

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.urls import reverse


class Player(AbstractUser):
    max_characters = models.PositiveIntegerField(default=6)

    class Meta:
        ordering = ["username"]
        verbose_name = "player"
        verbose_name_plural = "players"

    def __str__(self):
        return self.username


class Race(models.Model):
    name = models.CharField(max_length=63, unique=True)
    description = models.TextField()
    damage_modifier = models.FloatField()
    protection_modifier = models.FloatField()
    health_modifier = models.FloatField()
    allowed_professions = models.ManyToManyField(
        "Profession", related_name="allowed_races"
    )

    def __str__(self):
        return self.name


class Profession(models.Model):
    name = models.CharField(max_length=63, unique=True)
    description = models.TextField()
    damage_base = models.PositiveIntegerField()
    protection_base = models.PositiveIntegerField()
    health_base = models.PositiveIntegerField()

    def __str__(self):
        return self.name


class Item(models.Model):
    ITEM_SLOTS = {
        "weapon": "Weapon",
        "armor": "Armor",
        "accessory": "Accessory",
    }
    ITEM_TYPES = {
        "sword": "Sword",
        "mace": "Mace",
        "dagger": "Dagger",
        "axe": "Axe",
        "staff": "Staff",
        "magic_sword": "Magic Sword",
        "bow": "Bow",
        "crossbow": "Crossbow",
        "heavy_armor": "Heavy Armor",
        "medium_armor": "Medium Armor",
        "light_armor": "Light Armor",
        "accessory": "Accessory",
    }

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

    class Meta:
        ordering = (
            "slot",
            "type",
            "level_required",
            "name",
        )

    @property
    def sell_price(self) -> int:
        return self.price // 2

    def __str__(self):
        return self.name


name_validator = RegexValidator(
    regex=r"^[a-zA-Z]{2,12}$",
    message="Name must contain only 2-12 latin letters.",
)


class Character(models.Model):
    name = models.CharField(
        max_length=12,
        unique=True,
        validators=[
            name_validator,
        ],
    )
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
        Item,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"slot": "weapon"},
        related_name="characters_with_weapon",
        default=1,
    )
    equipped_armor = models.ForeignKey(
        Item,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"slot": "armor"},
        related_name="characters_with_armor",
    )
    equipped_accessory = models.ForeignKey(
        Item,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"slot": "accessory"},
        related_name="characters_with_accessory",
    )
    inventory = models.ManyToManyField(
        Item, related_name="characters", blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["level"]),
        ]

    def clean(self):
        super().clean()
        if self._state.adding:
            profession = getattr(self, "profession", None)
            if (
                profession
                and profession not in self.race.allowed_professions.all()
            ):
                raise ValidationError(
                    f"{profession.name} profession is not"
                    f" allowed for {self.race.name} race."
                )
            owner = getattr(self, "owner", None)
            if owner and owner.max_characters <= owner.characters.count():
                raise ValidationError(
                    f"You cannot have more than "
                    f"{self.owner.max_characters} characters."
                )

    def recalculate_stats(self) -> None:
        damage = self.profession.damage_base + self.level * 0.5
        protection = self.profession.protection_base + self.level * 0.2
        health = self.profession.health_base + self.level * 5

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
        self.full_clean()
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
            raise ValidationError(
                "You don't have that item in your inventory."
            )
        with transaction.atomic():
            self.inventory.remove(item)
            self.gold += item.sell_price
            self.save()

    def get_absolute_url(self):
        return reverse(
            "game:character-detail", kwargs={"char_name": self.name}
        )

    def __str__(self):
        return f"{self.name} ({self.level} lvl)"


class Battle(models.Model):
    attacker = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        related_name="battles_as_attacker",
    )
    defender = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        related_name="battles_as_defender",
    )
    winner = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        related_name="battles_as_winner",
    )
    loser = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        related_name="battles_as_loser",
    )
    gold_reward = models.PositiveIntegerField(default=0)
    exp_reward = models.PositiveIntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def clean(self):
        super().clean()
        if self._state.adding:
            if self.attacker == self.defender:
                raise ValidationError("You can't battle yourself.")
            if self.winner not in (
                self.attacker,
                self.defender,
            ) or self.loser not in (self.attacker, self.defender):
                raise ValidationError(
                    "Winner/loser must be either attacker or defender."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def calculate_winner(self) -> None:
        if self.attacker and self.defender:
            battlers_list = [self.attacker, self.defender]
            winner_index = randrange(0, 2)
            with transaction.atomic():
                self.winner = battlers_list[winner_index]
                self.loser = loser = battlers_list[1 - winner_index]
                self.gold_reward = round(loser.level * 1.4) + 2
                self.winner.gold += self.gold_reward
                self.exp_reward += loser.level * 7 + 5
                self.winner.add_exp(self.exp_reward)
                self.winner.save()
                self.save()
        else:
            raise ValidationError("You need 2 participants.")

    def get_absolute_url(self):
        return reverse("game:battle-detail", kwargs={"pk": self.pk})
