from django.urls import path

from game.views import (
    index,
    PlayerCharacterListView,
    LadderListView,
    CharacterDetailView,
    InventoryView,
    confirm_deal_view,
    ShopItemListView,
    ItemListView,
    CharacterCreateView,
    CharacterDeleteView,
    BattleCreateView,
    BattleDetailView,
    BattleListView,
)

urlpatterns = [
    path("", index, name="index"),
    path(
        "ladder/",
        LadderListView.as_view(),
        name="character-list",
    ),
    path(
        "characters/",
        PlayerCharacterListView.as_view(),
        name="my-character-list",
    ),
    path(
        "characters/<str:char_name>/",
        CharacterDetailView.as_view(),
        name="character-detail",
    ),
    path(
        "characters/<str:char_name>/inventory/",
        InventoryView.as_view(),
        name="character-inventory",
    ),
    path(
        "characters/<str:char_name>/change/<str:change_slot>/",
        InventoryView.as_view(),
        name="character-change",
    ),
    path(
        "characters/<str:char_name>/<str:action>/<str:item_name>/",
        confirm_deal_view,
        name="confirm-deal",
    ),
    path(
        "characters/<str:char_name>/delete/",
        CharacterDeleteView.as_view(),
        name="character-delete",
    ),
    path(
        "characters/<str:char_name>/shop/",
        ShopItemListView.as_view(),
        name="character-shop",
    ),
    path("items/", ItemListView.as_view(), name="item-list"),
    path(
        "character-create/",
        CharacterCreateView.as_view(),
        name="character-create",
    ),
    path(
        "characters/<str:char_name>/battle-create/",
        BattleCreateView.as_view(),
        name="battle-create",
    ),
    path(
        "battles/<int:pk>/",
        BattleDetailView.as_view(),
        name="battle-detail",
    ),
    path(
        "characters/<str:char_name>/battles/",
        BattleListView.as_view(),
        name="character-battle-list",
    ),
    path(
        "battles/",
        BattleListView.as_view(),
        name="battle-list",
    ),
]

app_name = "game"
