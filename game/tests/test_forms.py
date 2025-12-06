from django.contrib.auth import get_user_model
from django.test import TestCase

from game.forms import CharacterCreateForm, ChooseBattleOpponentForm
from game.models import Race, Profession, Item, Character


class TestForm(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.profession = Profession.objects.create(
            name="TestProfession",
            damage_base=1,
            protection_base=1,
            health_base=1,
        )
        cls.race = Race.objects.create(
            name="TestRace",
            damage_modifier=1,
            protection_modifier=1,
            health_modifier=1,
        )
        cls.race.allowed_professions.add(cls.profession)
        Item.objects.create(
            pk=1, name="defaultweapon", price=10, slot="weapon"
        )

    def setUp(self):
        self.player = get_user_model().objects.create_user(
            pk=1, username="Test", password="Test"
        )

    def test_character_create_form(self):
        form_data = {
            "name": "Testchar",
            "race": 1,
            "profession": 1,
        }
        form = CharacterCreateForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_character_owner_cannot_assign_inside_formdata(self):
        form_data = {
            "owner": 1,
            "name": "Testchar",
            "race": 1,
            "profession": 1,
        }
        form = CharacterCreateForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertNotIn("owner", form.cleaned_data)

    def test_battle_create_form(self):
        Character.objects.create(
            owner=self.player,
            name="Testchar",
            race=TestForm.race,
            profession=TestForm.profession,
        )
        form_data = {
            "defender": 1,
        }
        form = ChooseBattleOpponentForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_battle_attacker_winner_loser_reward_cannot_assign_inside_formdata(
        self,
    ):
        Character.objects.create(
            owner=self.player,
            name="Testchar",
            race=TestForm.race,
            profession=TestForm.profession,
        )
        form_data = {
            "defender": 1,
            "attacker": 1,
            "winner": 1,
            "loser": 1,
            "gold_reward": 1,
            "exp_reward": 1,
        }
        form = ChooseBattleOpponentForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertNotIn("attacker", form.cleaned_data)
        self.assertNotIn("winner", form.cleaned_data)
        self.assertNotIn("loser", form.cleaned_data)
        self.assertNotIn("gold_reward", form.cleaned_data)
        self.assertNotIn("exp_reward", form.cleaned_data)
