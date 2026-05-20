from django import forms

from .models import Topic


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        if data in self.empty_values:
            return []

        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)]


class ForumThreadCreateForm(forms.Form):
    tags = forms.ModelMultipleChoiceField(
        queryset=Topic.objects.none(),
        required=True,
        label="Topics",
        widget=forms.CheckboxSelectMultiple(),
        help_text="Select one or more topics that fit this thread.",
    )
    title = forms.CharField(
        max_length=220,
        widget=forms.TextInput(
            attrs={
                "class": "forum-input",
                "placeholder": "Start a discussion title",
                "autocomplete": "off",
            }
        ),
    )
    body = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "forum-textarea",
                "rows": 6,
                "placeholder": "Share a question, insight, or resource about this topic.",
            }
        ),
    )
    images = MultipleImageField(
        required=False,
        label="Pictures",
        widget=MultipleImageInput(
            attrs={
                "class": "forum-file-input",
                "accept": "image/*",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        topic_queryset = Topic.objects.order_by("order", "title")
        self.fields["tags"].queryset = topic_queryset


class ForumReplyForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "forum-textarea forum-reply-textarea",
                "rows": 5,
                "placeholder": "Write a thoughtful reply to keep the discussion going.",
            }
        ),
    )
    images = MultipleImageField(
        required=False,
        label="Pictures",
        widget=MultipleImageInput(
            attrs={
                "class": "forum-file-input",
                "accept": "image/*",
            }
        ),
    )
