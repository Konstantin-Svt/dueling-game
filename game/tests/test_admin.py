from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from game.models import Character, Race, Profession, Item


class TestAdmin(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = get_user_model().objects.create_superuser(
            username="TestAdmin", password="TestPassword"
        )
        cls.profession = Profession.objects.create(
            name="Profession 1",
            damage_base=0,
            protection_base=0,
            health_base=0,
        )
        cls.race = Race.objects.create(
            name="Race 1",
            damage_modifier=0,
            protection_modifier=0,
            health_modifier=0,
        )
        cls.race.allowed_professions.add(cls.profession)
        Item.objects.create(pk=1, name="name", price=10, slot="weapon")

    def setUp(self):
        self.client.force_login(TestAdmin.admin_user)

    def test_player_max_char_list_display(self):
        get_user_model().objects.create_user(
            username="TestUser", password="TestPassword", max_characters=32289
        )
        url = reverse("admin:game_player_changelist")
        response = self.client.get(url)
        self.assertContains(response, "32289")
        self.assertContains(response, "Max characters")

    def test_player_max_char_add_display(self):
        url = reverse("admin:game_player_add")
        response = self.client.get(url)
        self.assertContains(response, "Max characters")
        self.assertContains(response, "Game info")

    def test_player_max_char_change(self):
        player = get_user_model().objects.create_user(
            username="TestUser", password="TestPassword", max_characters=131
        )
        url = reverse("admin:game_player_change", args=[player.id])
        response = self.client.get(url)
        self.assertContains(response, "Max characters")
        self.assertContains(response, "Game info")
        self.assertContains(response, "131")

    def test_character_search_by_name(self):
        player = get_user_model().objects.create_user(
            username="TestUser", password="TestPassword"
        )
        Character.objects.create(
            owner=player,
            name="TestedChart",
            profession=TestAdmin.profession,
            race=TestAdmin.race,
        )
        Character.objects.create(
            owner=player,
            name="FakeChart",
            profession=TestAdmin.profession,
            race=TestAdmin.race,
        )
        url = reverse("admin:game_character_changelist")
        response = self.client.get(url, data={"q": "TestedChart"})
        self.assertContains(response, "TestedChart")
        self.assertNotContains(response, "FakeChart")
