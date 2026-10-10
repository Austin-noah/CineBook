from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import MovieReview, SeatBooking


class UsernameOrEmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your username or email",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
            }
        ),
    )


class SeatBookingForm(forms.ModelForm):
    class Meta:
        model = SeatBooking
        fields = ["customer_name", "customer_email", "customer_phone"]
        widgets = {
            "customer_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter your name",
                }
            ),
            "customer_email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter your email",
                }
            ),
            "customer_phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional phone number",
                    "autocomplete": "tel",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_name"].label = "Your name"
        self.fields["customer_email"].label = "Email address"
        self.fields["customer_phone"].label = "Phone number (optional)"


class MovieReviewForm(forms.ModelForm):
    class Meta:
        model = MovieReview
        fields = ["reviewer_name", "rating", "comment"]
        widgets = {
            "reviewer_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Your name"}
            ),
            "rating": forms.RadioSelect(
                attrs={"data-star-rating": "true"}
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Write your review",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rating_choices = [
            (rating, f"{rating} star{'s' if rating != 1 else ''}")
            for rating in range(5, 0, -1)
        ]
        self.fields["rating"].choices = rating_choices
        self.fields["rating"].widget.choices = rating_choices


class MovieFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search movies",
        widget=forms.SearchInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search by movie title",
            }
        ),
    )
    genre = forms.ChoiceField(
        required=False,
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    language = forms.ChoiceField(
        required=False,
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    min_rating = forms.ChoiceField(
        required=False,
        label="Catalogue rating",
        choices=(
            ("", "Any rating"),
            ("6", "6+ / 10"),
            ("7", "7+ / 10"),
            ("8", "8+ / 10"),
        ),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sort = forms.ChoiceField(
        required=False,
        choices=(
            ("", "Title A–Z"),
            ("rating", "Highest community rating"),
            ("newest", "Recently added"),
        ),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, genres=(), languages=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["genre"].choices = [("", "All genres")] + [
            (genre, genre) for genre in genres
        ]
        self.fields["language"].choices = [("", "All languages")] + [
            (language, language) for language in languages
        ]
