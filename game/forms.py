from django import forms

from game.models import Character, Battle


class CharacterCreateForm(forms.ModelForm):
    class Meta:
        model = Character
        fields = ["name", "race", "profession"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
        }


class CharacterNameSearchForm(forms.Form):
    searched_name = forms.CharField(
        max_length=12,
        required=False,
        label="",
        widget=forms.TextInput(attrs={"placeholder": "Search Character"}),
    )


class ItemNameSearchForm(forms.Form):
    searched_name = forms.CharField(
        max_length=100,
        required=False,
        label="",
        widget=forms.TextInput(attrs={"placeholder": "Search Item"}),
    )


class ChooseBattleOpponentForm(forms.ModelForm):
    class Meta:
        model = Battle
        fields = [
            "defender",
        ]
