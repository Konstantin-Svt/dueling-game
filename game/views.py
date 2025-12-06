from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Exists, F, Q
from django.db.models.functions import Abs
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import generic
from django.views.decorators.cache import never_cache

from game.forms import (
    ItemNameSearchForm,
    CharacterCreateForm,
    ChooseBattleOpponentForm,
    CharacterNameSearchForm,
)
from game.models import Character, Item, Race, Battle


def index(request):
    if request.user.is_authenticated:
        return redirect(reverse("game:my-character-list"))
    return redirect(reverse("login"))


class ElidedPaginationMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if context.get("is_paginated"):
            paginator = context.get("paginator")
            page_obj = context.get("page_obj")
            context["page_range"] = paginator.get_elided_page_range(
                number=page_obj.number, on_each_side=2
            )
        return context


class CharacterDispatchMixin:
    def dispatch(self, request, *args, **kwargs):
        if char_name := kwargs.get("char_name"):
            self.character = get_object_or_404(
                Character.objects.select_related(
                    "profession", "race", "owner"
                ),
                name=char_name,
            )
        return super().dispatch(request, *args, **kwargs)


class CharacterOwnerCheckMixin(UserPassesTestMixin):
    def test_func(self):
        character = getattr(self, "character", None) or self.get_object()
        return character.owner == self.request.user

    def handle_no_permission(self):
        messages.error(
            self.request,
            "You cannot perform actions on characters not owned by you.",
        )
        return redirect(reverse("game:my-character-list"))


class PlayerCharacterListView(
    LoginRequiredMixin, ElidedPaginationMixin, generic.ListView
):
    model = Character
    paginate_by = 10
    template_name = "game/my_character_list.html"

    def get_queryset(self):
        return Character.objects.filter(
            owner=self.request.user
        ).select_related("race", "profession")


class LadderListView(ElidedPaginationMixin, generic.ListView):
    model = Character
    paginate_by = 50
    template_name = "game/ladder.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        searched_name = self.request.GET.get("searched_name", "")
        context["searched_name"] = searched_name
        search_form = CharacterNameSearchForm(
            initial={"searched_name": searched_name}
        )
        context["search_form"] = search_form
        return context

    def get_queryset(self):
        if searched_name := self.request.GET.get("searched_name"):
            return Character.objects.filter(name__icontains=searched_name)
        return Character.objects.order_by("-level")[:100].select_related(
            "race", "profession"
        )


class CharacterDetailView(CharacterDispatchMixin, generic.DetailView):
    model = Character
    slug_field = "name"
    slug_url_kwarg = "char_name"

    def get_object(self, queryset=None):
        return self.character

    def get_context_data(self, **kwargs):
        obj = Character.objects.select_related(
            "equipped_weapon", "equipped_armor", "equipped_accessory"
        ).get(pk=self.character.pk)
        context = super().get_context_data(**kwargs)
        context["equipment"] = {
            "weapon": obj.equipped_weapon,
            "armor": obj.equipped_armor,
            "accessory": obj.equipped_accessory,
        }
        context["exp_percent"] = int(obj.current_exp * 100 / obj.exp_for_level)
        return context

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if request.user != obj.owner:
            messages.error(
                request,
                "You cannot perform actions on characters not owned by you.",
            )
            return redirect(reverse("game:my-character-list"))

        if item_id := request.POST.get("item_unequip"):
            item = get_object_or_404(Item, pk=item_id)
            try:
                obj.unequip_item(item)
                messages.success(request, f"{item.name} has been unequipped")
            except ValidationError as e:
                for msg in e.messages:
                    messages.error(request, msg)
            return redirect(obj.get_absolute_url())

        if request.POST.get("join_battle"):
            request.session["battle_create_allowed"] = True
            return redirect("game:battle-create", char_name=obj.name)


class InventoryView(
    LoginRequiredMixin,
    CharacterDispatchMixin,
    CharacterOwnerCheckMixin,
    ElidedPaginationMixin,
    generic.ListView,
):
    paginate_by = 12
    template_name = "game/character_inventory.html"
    context_object_name = "items"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["character"] = self.character
        searched_name = self.request.GET.get("searched_name", "")
        context["search_form"] = ItemNameSearchForm(
            initial={"searched_name": searched_name}
        )
        context["slots"] = Item.ITEM_SLOTS
        selected_slot = self.request.GET.get("slot")
        change_slot = self.kwargs.get("change_slot")

        if change_slot:
            selected_slot = change_slot
            context["change_slot"] = change_slot
        if selected_slot:
            context["selected_slot"] = selected_slot
            types_of_slot = (
                self.character.inventory.order_by("type")
                .filter(slot=selected_slot)
                .values_list("type", flat=True)
                .distinct()
            )
            context["types"] = {
                type_name: Item.ITEM_TYPES[type_name]
                for type_name in types_of_slot
            }
        else:
            context["types"] = Item.ITEM_TYPES

        selected_type = self.request.GET.get("type")
        context["selected_type"] = selected_type
        return context

    def get_queryset(self):
        qs = self.character.inventory.prefetch_related("allowed_professions")

        if change_slot := self.kwargs.get("change_slot"):
            qs = qs.filter(slot=change_slot)

        elif slot_name := self.request.GET.get("slot"):
            qs = qs.filter(slot=slot_name)

        type_name = self.request.GET.get("type")
        if type_name and qs.filter(type=type_name).exists():
            qs = qs.filter(type=type_name)

        searched_name = self.request.GET.get("searched_name")
        if searched_name:
            qs = qs.filter(name__icontains=searched_name)

        return qs

    def post(self, request, *args, **kwargs):

        if item_id := request.POST.get("item_equip"):
            item = get_object_or_404(Item, pk=item_id)
            try:
                self.character.equip_item(item)
                messages.success(request, f"{item.name} has been equipped")
            except ValidationError as e:
                for msg in e.messages:
                    messages.error(request, msg)

        return redirect(self.character.get_absolute_url())


def confirm_deal_view(request, *args, **kwargs):
    obj = get_object_or_404(
        Character, name=kwargs["char_name"], owner=request.user
    )
    item = get_object_or_404(Item, name=kwargs["item_name"])
    next_url = request.GET.get("next") or reverse_lazy(
        "game:character-inventory", kwargs={"char_name": obj.name}
    )
    action = kwargs.get("action")
    context = {
        "character": obj,
        "item": item,
        "next": next_url,
        "action": action,
    }

    if request.method == "POST":
        if action == "sell":
            try:
                obj.sell_item(item)
                messages.success(request, f"{item.name} has been sold")
            except ValidationError as e:
                for msg in e.messages:
                    messages.error(request, msg)

        elif action == "buy":
            try:
                obj.buy_item(item)
                messages.success(request, f"{item.name} has been bought")
            except ValidationError as e:
                for msg in e.messages:
                    messages.error(request, msg)

        return redirect(next_url)

    return render(request, "game/confirm_deal.html", context)


class ShopItemListView(
    LoginRequiredMixin,
    CharacterDispatchMixin,
    CharacterOwnerCheckMixin,
    ElidedPaginationMixin,
    generic.ListView,
):
    model = Item
    paginate_by = 12

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["character"] = self.character
        searched_name = self.request.GET.get("searched_name", "")
        context["search_form"] = ItemNameSearchForm(
            initial={"searched_name": searched_name}
        )
        context["slots"] = Item.ITEM_SLOTS
        selected_slot = self.request.GET.get("slot")
        selected_type = self.request.GET.get("type")
        if selected_slot:
            context["selected_slot"] = selected_slot
            types_of_slot = (
                Item.objects.order_by("type")
                .filter(slot=selected_slot)
                .values_list("type", flat=True)
                .distinct()
            )
            context["types"] = {
                type_name: Item.ITEM_TYPES[type_name]
                for type_name in types_of_slot
            }
        else:
            context["types"] = Item.ITEM_TYPES
        context["selected_type"] = selected_type
        return context

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("allowed_professions")
        owned_items = self.character.inventory.filter(name=OuterRef("name"))
        qs = qs.annotate(is_owned=Exists(owned_items))

        if slot_name := self.request.GET.get("slot"):
            qs = qs.filter(slot=slot_name)

        type_name = self.request.GET.get("type")
        if qs.filter(type=type_name).exists():
            qs = qs.filter(type=type_name)

        searched_name = self.request.GET.get("searched_name")
        if searched_name:
            qs = qs.filter(name__icontains=searched_name)

        return qs


class ItemListView(ElidedPaginationMixin, generic.ListView):
    model = Item
    paginate_by = 12

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        searched_name = self.request.GET.get("searched_name", "")
        context["search_form"] = ItemNameSearchForm(
            initial={"searched_name": searched_name}
        )
        context["slots"] = Item.ITEM_SLOTS
        selected_slot = self.request.GET.get("slot")
        selected_type = self.request.GET.get("type")
        if selected_slot:
            context["selected_slot"] = selected_slot
            types_of_slot = (
                Item.objects.order_by("type")
                .filter(slot=selected_slot)
                .values_list("type", flat=True)
                .distinct()
            )
            context["types"] = {
                type_name: Item.ITEM_TYPES.get(type_name)
                for type_name in types_of_slot
            }
        else:
            context["types"] = Item.ITEM_TYPES
        context["selected_type"] = selected_type
        return context

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("allowed_professions")

        if slot_name := self.request.GET.get("slot"):
            qs = qs.filter(slot=slot_name)

        type_name = self.request.GET.get("type")
        if qs.filter(type=type_name).exists():
            qs = qs.filter(type=type_name)

        searched_name = self.request.GET.get("searched_name")
        if searched_name:
            qs = qs.filter(name__icontains=searched_name)

        return qs


class CharacterCreateView(LoginRequiredMixin, generic.CreateView):
    model = Character
    form_class = CharacterCreateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["races"] = Race.objects.all()
        chosen_race = self.request.GET.get("chosen_race")
        if chosen_race:
            try:
                context["chosen_race"] = Race.objects.get(pk=chosen_race)
            except Race.DoesNotExist:
                context["chosen_race"] = None
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        form.instance.owner = request.user
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)


class CharacterDeleteView(
    LoginRequiredMixin, CharacterOwnerCheckMixin, generic.DeleteView
):
    model = Character
    slug_field = "name"
    slug_url_kwarg = "char_name"
    queryset = Character.objects.select_related("profession", "race", "owner")

    def get_success_url(self):
        messages.success(
            self.request, "Character has been successfully deleted."
        )
        return reverse("game:my-character-list")


class BattleDetailView(generic.DetailView):
    model = Battle

    def get_queryset(self):
        qs = Battle.objects.select_related(
            "attacker",
            "defender",
            "winner__race",
            "winner__profession",
            "loser__race",
            "loser__profession",
        )
        return qs


@method_decorator(never_cache, name="dispatch")
class BattleCreateView(
    LoginRequiredMixin,
    CharacterDispatchMixin,
    CharacterOwnerCheckMixin,
    generic.CreateView,
):
    model = Battle
    form_class = ChooseBattleOpponentForm

    def dispatch(self, request, *args, **kwargs):
        if request.method == "GET" and not request.session.pop(
            "battle_create_allowed", False
        ):
            messages.error(request, "Join the battle from Character page.")
            return redirect("game:my-character-list")
        return super().dispatch(request, *args, **kwargs)

    def get_opponents(self, request) -> list:
        candidates = list(
            Character.objects.filter(
                level__range=(
                    self.character.level - 25,
                    self.character.level + 25,
                )
            )
            .exclude(owner=request.user)
            .annotate(diff=Abs(F("level") - self.character.level))
            .order_by("diff", "level")[:10]
            .select_related("race", "profession")
        )

        if not candidates:
            return []

        diff = 0
        opponents = [
            opponent for opponent in candidates if opponent.diff == diff
        ]
        while len(opponents) < 3 and len(opponents) < len(candidates):
            diff += 1
            opponents.extend(
                [opponent for opponent in candidates if opponent.diff == diff]
            )
        return opponents

    def get(self, request, *args, **kwargs):
        self.opponents = self.get_opponents(request)
        request.session[f"opponents_for_{self.character.id}"] = [
            opponent.id for opponent in self.opponents
        ]
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)
        opponent_id = form.cleaned_data["defender"].id
        if opponent_id and opponent_id in request.session.get(
            f"opponents_for_{self.character.id}", []
        ):
            form.instance.attacker = self.character
        else:
            messages.error(request, "Opponent must be from a provided list.")
            return redirect(self.character.get_absolute_url())
        request.session.pop(f"opponents_for_{self.character.id}", None)
        return self.form_valid(form)

    def form_valid(self, form):
        battle = form.save(commit=False)
        battle.calculate_winner()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["character"] = self.character
        context["opponents"] = self.opponents
        return context


class BattleListView(
    ElidedPaginationMixin, CharacterDispatchMixin, generic.ListView
):
    model = Battle
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        character = getattr(self, "character", None)
        context["character"] = character
        if not character:
            searched_name = self.request.GET.get("searched_name", "")
            context["searched_name"] = searched_name
            search_form = CharacterNameSearchForm(
                initial={"searched_name": searched_name}
            )
            context["search_form"] = search_form
        return context

    def get_queryset(self, *args, **kwargs):
        qs = Battle.objects.order_by("-date").select_related(
            "attacker",
            "defender",
            "winner",
            "attacker__race",
            "attacker__profession",
            "defender__race",
            "defender__profession",
        )
        if character := getattr(self, "character", None):
            return qs.filter(Q(attacker=character) | Q(defender=character))
        if searched_name := self.request.GET.get("searched_name"):
            return qs.filter(
                Q(attacker__name__contains=searched_name)
                | Q(defender__name__contains=searched_name)
            )[:100]
        return qs[:100]
