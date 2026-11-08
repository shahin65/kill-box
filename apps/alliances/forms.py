from django import forms

from apps.alliances.models import Alliance
from apps.core.ranks import RANKS


RANK_CHOICES = tuple((row['level'], f'{row["level"]} · {row["title"]}') for row in RANKS)


class AllianceCreateForm(forms.Form):
    name = forms.CharField(label='نام اتحاد', min_length=3, max_length=32)
    description = forms.CharField(
        label='توضیحات',
        max_length=280,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    join_policy = forms.ChoiceField(label='سیاست عضویت', choices=Alliance.JOIN_CHOICES, initial=Alliance.REQUEST)
    min_rank = forms.TypedChoiceField(
        label='حداقل رنک',
        choices=RANK_CHOICES,
        coerce=int,
        initial=0,
    )
    is_discoverable = forms.BooleanField(label='نمایش در جست‌وجو', required=False, initial=True)
    is_private = forms.BooleanField(label='خصوصی', required=False, initial=False)
    logo = forms.ImageField(label='لوگو', required=False)
    banner = forms.ImageField(label='بنر', required=False)


class AllianceSettingsForm(AllianceCreateForm):
    pass
