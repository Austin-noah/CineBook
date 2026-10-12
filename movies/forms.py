from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import MovieReview, SeatBooking


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        label="Email address",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "you@example.com",
                "autocomplete": "email",
            }
        ),
    )
    first_name = forms.CharField(
        label="First name",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "First name",
                "autocomplete": "given-name",
            }
        ),
    )
    last_name = forms.CharField(
        label="Last name",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Last name",
                "autocomplete": "family-name",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "username" in self.fields:
            self.fields["username"].widget.attrs.update(
                {
                    "class": "form-control",
                    "placeholder": "Choose a username",
                    "autocomplete": "username",
                }
            )
            self.fields["username"].help_text = (
                "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
            )
        if "password1" in self.fields:
            self.fields["password1"].widget.attrs.update(
                {
                    "class": "form-control",
                    "placeholder": "Create a strong password",
                    "autocomplete": "new-password",
                }
            )
        if "password2" in self.fields:
            self.fields["password2"].widget.attrs.update(
                {
                    "class": "form-control",
                    "placeholder": "Repeat your password",
                    "autocomplete": "new-password",
                }
            )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise forms.ValidationError("Please provide a valid email address.")
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists. Please log in.")
        return email


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


class AdminLoginForm(AuthenticationForm):
    """Login form for admin users. Reuses standard Django auth but restricts to staff."""

    username = forms.CharField(
        label="Admin username",
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "Admin username",
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
                "class": "form-control form-control-lg",
                "placeholder": "Admin password",
                "autocomplete": "current-password",
            }
        ),
    )

    def confirm_login_allowed(self, user):
        """Override: only staff or superuser accounts may use the admin login."""
        super().confirm_login_allowed(user)
        if not (user.is_staff or user.is_superuser):
            raise forms.ValidationError(
                "This account does not have administrator access.",
                code="not_admin",
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
