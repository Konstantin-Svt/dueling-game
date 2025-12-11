from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from game.models import Race, Profession, Item, Character, Battle


class TestView(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = get_user_model().objects.create_user(
            username="TestUser", password="TestPassword"
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
        self.client.force_login(TestView.user)

    def test_login_required(self):
        self.client.logout()
        url = reverse("game:my-character-list")
        response = self.client.get(url, follow=True)
        self.assertEqual(response.redirect_chain[0][1], 302)
        self.assertContains(response, "Please login to see this page")

    def test_character_inventory_view_owner_only(self):
        other_user = get_user_model().objects.create_user(
            username="TestUser2", password="TestPassword2"
        )
        other_character = Character.objects.create(
            owner=other_user,
            name="charzxcd",
            profession=TestView.profession,
            race=TestView.race,
        )
        url = reverse(
            "game:character-inventory",
            kwargs={"char_name": other_character.name},
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(response.redirect_chain[0][1], 302)
        self.assertContains(
            response, "cannot perform actions on characters not owned by you"
        )

    def test_character_deletion_owner_only(self):
        other_user = get_user_model().objects.create_user(
            username="TestUser2", password="TestPassword2"
        )
        other_character = Character.objects.create(
            owner=other_user,
            name="charzxcd",
            profession=TestView.profession,
            race=TestView.race,
        )
        url = reverse(
            "game:character-delete", kwargs={"char_name": other_character.name}
        )

        response_get = self.client.get(url, follow=True)
        self.assertEqual(response_get.redirect_chain[0][1], 302)
        self.assertContains(
            response_get,
            "cannot perform actions on characters not owned by you",
        )

        response_post = self.client.post(url, follow=True)
        self.assertEqual(response_post.redirect_chain[0][1], 302)
        self.assertContains(
            response_post,
            "cannot perform actions on characters not owned by you",
        )

    def test_character_item_sell_buy_owner_only(self):
        other_user = get_user_model().objects.create_user(
            username="TestUser2", password="TestPassword2"
        )
        other_character = Character.objects.create(
            owner=other_user,
            name="charzxcd",
            profession=TestView.profession,
            race=TestView.race,
        )
        other_item = Item.objects.create(name="big", price=10, slot="weapon")
        other_character.inventory.add(other_item)

        url_sell = reverse(
            "game:confirm-deal",
            kwargs={
                "char_name": other_character.name,
                "action": "sell",
                "item_name": other_item.name,
            },
        )
        response_get = self.client.get(url_sell)
        self.assertEqual(response_get.status_code, 404)
        response_post = self.client.post(url_sell)
        self.assertEqual(response_post.status_code, 404)

        url_buy = reverse(
            "game:confirm-deal",
            kwargs={
                "char_name": other_character.name,
                "action": "buy",
                "item_name": other_item.name,
            },
        )
        response_get = self.client.get(url_buy)
        self.assertEqual(response_get.status_code, 404)
        response_post = self.client.post(url_buy)
        self.assertEqual(response_post.status_code, 404)

    def test_character_create(self):
        url = reverse("game:character-create")
        response = self.client.post(
            url,
            data={
                "name": "charzxcd",
                "profession": TestView.profession.pk,
                "race": TestView.race.pk,
            },
            follow=True,
        )
        self.assertRedirects(
            response,
            reverse("game:character-detail", kwargs={"char_name": "charzxcd"}),
        )
        self.assertContains(response, "charzxcd")

    def test_item_name_search(self):
        searched_item = Item.objects.create(
            name="ABOBA", price=10, slot="weapon"
        )
        Item.objects.create(
            name="ANTIBO", price=10, slot="weapon"
        )
        url = reverse("game:item-list")
        response = self.client.get(
            url, query_params={"searched_name": searched_item.name}
        )
        self.assertContains(response, "ABOBA")
        self.assertNotContains(response, "ANTIBO")

    def test_item_slot_filter_select(self):
        searched_item = Item.objects.create(
            name="ABOBA", price=10, slot="weapon"
        )
        Item.objects.create(
            name="ANTIBO", price=10, slot="armor"
        )
        url = reverse("game:item-list")
        response = self.client.get(
            url, query_params={"slot": searched_item.slot}
        )
        self.assertContains(response, "ABOBA")
        self.assertNotContains(response, "ANTIBO")

    def test_item_type_filter_select(self):
        searched_item = Item.objects.create(
            name="ABOBA", price=10, type="axe", slot="weapon"
        )
        Item.objects.create(
            name="ANTIBO", price=10, type="sword"
        )
        url = reverse("game:item-list")
        response = self.client.get(
            url, query_params={"type": searched_item.type}
        )
        self.assertContains(response, "ABOBA")
        self.assertNotContains(response, "ANTIBO")

    def test_buy_item(self):
        item = Item.objects.create(
            name="ABOBA", price=10, type="axe", slot="weapon"
        )
        item.allowed_professions.add(TestView.profession)
        character = Character.objects.create(
            owner=TestView.user,
            name="charzxc",
            profession=TestView.profession,
            race=TestView.race,
            gold=10,
        )
        url = reverse(
            "game:confirm-deal",
            kwargs={
                "char_name": character.name,
                "action": "buy",
                "item_name": item.name,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertRedirects(
            response,
            reverse(
                "game:character-inventory",
                kwargs={"char_name": character.name},
            ),
        )
        self.assertContains(response, "charzxc")
        self.assertContains(response, "ABOBA")

    def test_sell_item(self):
        item = Item.objects.create(
            name="ABOBA", price=10, type="axe", slot="weapon"
        )
        item.allowed_professions.add(TestView.profession)
        character = Character.objects.create(
            owner=TestView.user,
            name="charzxc",
            profession=TestView.profession,
            race=TestView.race,
            gold=0,
        )
        character.inventory.add(item)
        url = reverse(
            "game:confirm-deal",
            kwargs={
                "char_name": character.name,
                "action": "sell",
                "item_name": item.name,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertRedirects(
            response,
            reverse(
                "game:character-inventory",
                kwargs={"char_name": character.name},
            ),
        )
        self.assertContains(response, "charzxc")
        self.assertContains(response, "ABOBA has been sold")

        refreshed_response = self.client.get(
            reverse(
                "game:character-inventory",
                kwargs={"char_name": character.name},
            )
        )
        self.assertNotContains(refreshed_response, "ABOBA")

    def test_character_ladder_name_search(self):
        character = Character.objects.create(
            owner=TestView.user,
            name="charzxc",
            profession=TestView.profession,
            race=TestView.race,
            level=50,
        )
        Character.objects.create(
            owner=TestView.user,
            name="antichar",
            profession=TestView.profession,
            race=TestView.race,
            level=51,
        )
        url = reverse("game:character-list")
        response = self.client.get(
            url, query_params={"searched_name": character.name}
        )
        self.assertContains(response, "charzxc")
        self.assertNotContains(response, "antichar")

    def test_battle_create_view(self):
        Character.objects.create(
            owner=TestView.user,
            name="charzxc",
            profession=TestView.profession,
            race=TestView.race,
            level=50,
        )
        user_two = get_user_model().objects.create_user(
            username="TestUserTwo", password="TestPassword2"
        )
        character_two = Character.objects.create(
            owner=user_two,
            name="antichar",
            profession=TestView.profession,
            race=TestView.race,
            level=51,
        )
        self.client.post(
            reverse("game:character-detail", kwargs={"char_name": "charzxc"}),
            data={"join_battle": True},
            follow=True,
        )
        response = self.client.post(
            reverse("game:battle-create", kwargs={"char_name": "charzxc"}),
            data={"defender": character_two.pk},
            follow=True,
        )
        self.assertRedirects(
            response, reverse("game:battle-detail", kwargs={"pk": "1"})
        )
        self.assertContains(response, "charzxc vs antichar")

    def test_battle_create_from_character_page_only(self):
        Character.objects.create(
            owner=TestView.user,
            name="charzxc",
            profession=TestView.profession,
            race=TestView.race,
            level=50,
        )
        url = reverse("game:battle-create", kwargs={"char_name": "charzxc"})
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("game:my-character-list"))
        self.assertContains(response, "Join the battle from Character page")

    def test_battle_opponent_must_be_matched(self):
        Character.objects.create(
            owner=TestView.user,
            name="charzxc",
            profession=TestView.profession,
            race=TestView.race,
            level=9999,
        )
        user_two = get_user_model().objects.create_user(
            username="TestUserTwo", password="TestPassword2"
        )
        character_two = Character.objects.create(
            owner=user_two,
            name="antichar",
            profession=TestView.profession,
            race=TestView.race,
            level=1,
        )
        self.client.post(
            reverse("game:character-detail", kwargs={"char_name": "charzxc"}),
            data={"join_battle": True},
            follow=True,
        )
        response = self.client.post(
            reverse("game:battle-create", kwargs={"char_name": "charzxc"}),
            data={"defender": character_two.pk},
            follow=True,
        )
        self.assertRedirects(
            response,
            reverse("game:character-detail", kwargs={"char_name": "charzxc"}),
        )
        self.assertContains(response, "Opponent must be from a provided list")

    def test_battle_list_search_by_character_name(self):
        character = Character.objects.create(
            owner=TestView.user,
            name="charzxc",
            profession=TestView.profession,
            race=TestView.race,
            level=1,
        )
        user_two = get_user_model().objects.create_user(
            username="TestUserTwo", password="TestPassword2"
        )
        character_two = Character.objects.create(
            owner=user_two,
            name="antichar",
            profession=TestView.profession,
            race=TestView.race,
            level=1,
        )
        character_three = Character.objects.create(
            owner=user_two,
            name="antiman",
            profession=TestView.profession,
            race=TestView.race,
            level=1,
        )
        Battle.objects.create(
            attacker=character,
            defender=character_two,
            winner=character,
            loser=character_two,
        )
        Battle.objects.create(
            attacker=character,
            defender=character_three,
            winner=character,
            loser=character_three,
        )
        url = reverse("game:battle-list")
        response = self.client.get(
            url, query_params={"searched_name": character_two.name}
        )
        self.assertContains(response, "antichar")
        self.assertNotContains(response, "antiman")
