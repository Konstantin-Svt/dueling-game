from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from game.models import Race, Profession, Item, Character, Battle


class TestModel(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = get_user_model().objects.create_user(
            username="TestUser", password="TestPassword", max_characters=4
        )
        cls.profession = Profession.objects.create(
            name="Profession 1",
            damage_base=100,
            protection_base=100,
            health_base=100,
        )
        cls.race = Race.objects.create(
            name="Race 1",
            damage_modifier=1,
            protection_modifier=1,
            health_modifier=1,
        )
        cls.race.allowed_professions.add(cls.profession)
        Item.objects.create(pk=1, name="name", price=10, slot="weapon")

    def setUp(self):
        self.client.force_login(TestModel.user)

    def test_race_allowed_professions_validation(self):
        not_allowed_profession = Profession.objects.create(
            name="not allowed profession",
            damage_base=1,
            protection_base=1,
            health_base=1,
        )
        character = Character(
            owner=TestModel.user,
            name="charzxc",
            profession=not_allowed_profession,
            race=TestModel.race,
        )
        self.assertRaises(ValidationError, character.save)

    def test_player_max_characters_validation(self):
        for index in range(TestModel.user.max_characters):
            Character.objects.create(
                owner=TestModel.user,
                name=f"char{chr(65 + index)}",
                profession=TestModel.profession,
                race=TestModel.race,
            )
        character = Character(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        self.assertRaises(ValidationError, character.save)

    def test_character_name_regex_validation(self):
        test_cases = ["F", "Fa123", "azaz_@", "faaaaaaaaaaaang", "12345"]
        for char_name in test_cases:
            with self.subTest(char_name=char_name):
                self.assertRaises(
                    ValidationError,
                    Character.objects.create,
                    owner=TestModel.user,
                    name=char_name,
                    profession=TestModel.profession,
                    race=TestModel.race,
                )

    def test_character_stat_calculation(self):
        test_weapon = Item.objects.create(
            name="test_weapon", price=10, bonus_damage=222, slot="weapon"
        )
        test_armor = Item.objects.create(
            name="test_armor", price=10, bonus_protection=238, slot="armor"
        )
        test_accessory = Item.objects.create(
            name="test_accessory", price=10, bonus_health=264, slot="accessory"
        )
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
            level=10,
            equipped_weapon=test_weapon,
            equipped_armor=test_armor,
            equipped_accessory=test_accessory,
        )
        self.assertEqual(character.damage, 327)
        self.assertEqual(character.protection, 340)
        self.assertEqual(character.health, 414)

    def test_character_add_exp(self):
        character = Character(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
            level=1,
        )
        character.add_exp(15450)
        character.save()
        self.assertEqual(character.level, 11)

    def test_character_equip_item(self):
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
            level=1,
        )
        weapon = Item.objects.create(
            name="TestWeapon", price=10, slot="weapon"
        )
        weapon.allowed_professions.add(character.profession)
        character.inventory.add(weapon)

        armor = Item.objects.create(name="TestArmor", price=10, slot="armor")
        armor.allowed_professions.add(character.profession)
        character.inventory.add(armor)

        accessory = Item.objects.create(
            name="TestAccessory", price=10, slot="accessory"
        )
        accessory.allowed_professions.add(character.profession)
        character.inventory.add(accessory)

        character.equip_item(weapon)
        character.equip_item(armor)
        character.equip_item(accessory)
        self.assertEqual(character.equipped_weapon, weapon)
        self.assertEqual(character.equipped_armor, armor)
        self.assertEqual(character.equipped_accessory, accessory)

    def test_character_equip_item_validation(self):
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
            level=1,
        )
        not_inventory_item = Item.objects.create(
            name="TestArmor", price=10, slot="armor"
        )
        not_inventory_item.allowed_professions.add(character.profession)

        not_allowed_prof_item = Item.objects.create(
            name="TestAccessory", price=10, slot="accessory"
        )
        character.inventory.add(not_allowed_prof_item)

        high_lvl_item = Item.objects.create(
            name="TestHighLvl", price=10, level_required=30, slot="accessory"
        )
        high_lvl_item.allowed_professions.add(character.profession)
        character.inventory.add(high_lvl_item)

        self.assertRaises(
            ValidationError, character.equip_item, not_inventory_item
        )
        self.assertRaises(
            ValidationError, character.equip_item, not_allowed_prof_item
        )
        self.assertRaises(ValidationError, character.equip_item, high_lvl_item)

    def test_character_unequip_item(self):
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        weapon = Item.objects.create(
            name="TestWeapon", price=10, slot="weapon"
        )
        weapon.allowed_professions.add(character.profession)
        character.equipped_weapon = weapon
        character.save()

        character.unequip_item(weapon)
        self.assertIn(weapon, character.inventory.all())

    def test_character_unequip_item_validation(self):
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        weapon = Item.objects.create(
            name="TestWeapon", price=10, slot="weapon"
        )
        weapon.allowed_professions.add(character.profession)
        self.assertRaises(ValidationError, character.unequip_item, weapon)

    def test_character_buy_item(self):
        item = Item.objects.create(name="TestWeapon", price=10, slot="weapon")
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
            gold=item.price,
        )
        item.allowed_professions.add(character.profession)
        character.buy_item(item)
        self.assertIn(item, character.inventory.all())

    def test_character_buy_item_validation(self):
        equipped_item = Item.objects.create(
            name="TestWeapon", price=10, slot="weapon"
        )
        equipped_item.allowed_professions.add(TestModel.profession)
        costly_item = Item.objects.create(
            name="TestArmor", price=999, slot="armor"
        )
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
            gold=costly_item.price - 1,
            equipped_weapon=equipped_item,
        )
        self.assertRaises(ValidationError, character.buy_item, costly_item)
        self.assertRaises(ValidationError, character.buy_item, equipped_item)

    def test_character_sell_item(self):
        item = Item.objects.create(name="TestWeapon", price=10, slot="weapon")
        item.allowed_professions.add(TestModel.profession)
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
            gold=0,
        )
        character.inventory.add(item)
        character.sell_item(item)
        self.assertNotIn(item, character.inventory.all())
        self.assertEqual(character.gold, item.sell_price)

    def test_character_sell_item_validation(self):
        equipped_item = Item.objects.create(
            name="TestWeapon", price=10, slot="weapon"
        )
        equipped_item.allowed_professions.add(TestModel.profession)
        not_inventory_item = Item.objects.create(
            name="TestArmor", price=10, slot="armor"
        )
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
            equipped_weapon=equipped_item,
        )
        self.assertRaises(
            ValidationError, character.sell_item, not_inventory_item
        )
        self.assertRaises(ValidationError, character.sell_item, equipped_item)

    def test_battle_calculate_winner(self):
        character_attacker = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        user_two = get_user_model().objects.create_user(
            username="TestUserTwo", password="TestPassword2"
        )
        character_defender = Character.objects.create(
            owner=user_two,
            name="charzxcd",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        battle = Battle(
            attacker=character_attacker, defender=character_defender
        )
        battle.calculate_winner()

        self.assertIn(battle.winner, [character_attacker, character_defender])
        self.assertIn(battle.loser, [character_attacker, character_defender])
        self.assertNotEqual(battle.winner, battle.loser)

    def test_battle_cant_attack_yourself(self):
        character = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        battle = Battle(attacker=character, defender=character)
        self.assertRaises(ValidationError, battle.save)

    def test_battle_two_participants_validation(self):
        character_attacker = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        battle = Battle(attacker=character_attacker, defender=None)
        self.assertRaises(ValidationError, battle.calculate_winner)

    def test_battle_winner_and_looser_from_participants_only(self):
        character_attacker = Character.objects.create(
            owner=TestModel.user,
            name="charzxc",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        user_two = get_user_model().objects.create_user(
            username="TestUserTwo", password="TestPassword2"
        )
        character_defender = Character.objects.create(
            owner=user_two,
            name="charzxcd",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        character_winner = Character.objects.create(
            owner=TestModel.user,
            name="winner",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        character_loser = Character.objects.create(
            owner=user_two,
            name="loser",
            profession=TestModel.profession,
            race=TestModel.race,
        )
        battle = Battle(
            attacker=character_attacker,
            defender=character_defender,
            winner=character_winner,
            loser=character_loser,
        )
        self.assertRaises(ValidationError, battle.save)
