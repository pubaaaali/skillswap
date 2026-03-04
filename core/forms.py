"""
Forms for SkillSwap: registration, profile editing, skill CRUD,
service requests, bidding, and reviews.
"""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import UserProfile, Skill, ServiceRequest, Bid, Review, Message


class RegistrationForm(forms.ModelForm):
    """User sign-up form with password confirmation."""
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose a password',
            'autocomplete': 'new-password',
        })
    )
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repeat password',
            'autocomplete': 'new-password',
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1', '')
        p2 = self.cleaned_data.get('password2', '')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        if len(p1) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Styled login form."""
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Username', 'autofocus': True,
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Password',
    }))


class UserProfileForm(forms.ModelForm):
    """Edit profile bio and avatar."""
    class Meta:
        model = UserProfile
        fields = ['bio', 'avatar']
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Tell the community about yourself…',
                'maxlength': 500,
            }),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class UserEditForm(forms.ModelForm):
    """Edit basic User fields (name, email)."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class SkillForm(forms.ModelForm):
    """Add or edit a skill offered by the user."""
    class Meta:
        model = Skill
        fields = ['title', 'description', 'level', 'duration_hours', 'is_available']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Linear Algebra tutoring'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Describe what you can teach or help with…',
                'maxlength': 500,
            }),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'duration_hours': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.5', 'min': '0.5', 'max': '8',
            }),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_duration_hours(self):
        hours = self.cleaned_data.get('duration_hours')
        if hours is not None and hours <= 0:
            raise forms.ValidationError('Duration must be greater than 0.')
        return hours


class ServiceRequestForm(forms.ModelForm):
    """Create or edit a service request."""
    class Meta:
        model = ServiceRequest
        fields = ['title', 'skill_category', 'description', 'hours_required', 'preferred_schedule']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Help with Eigenvalues'}),
            'skill_category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mathematics, Guitar, Coding…'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Describe what you need help with…',
                'maxlength': 1000,
            }),
            'hours_required': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.5', 'min': '0.5', 'max': '20',
            }),
            'preferred_schedule': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Tuesday evenings, weekends…',
            }),
        }

    def clean_hours_required(self):
        hours = self.cleaned_data.get('hours_required')
        if hours is not None and hours <= 0:
            raise forms.ValidationError('Hours must be greater than 0.')
        return hours


class BidForm(forms.ModelForm):
    """Submit a bid on a service request."""
    class Meta:
        model = Bid
        fields = ['proposed_hours', 'message']
        widgets = {
            'proposed_hours': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.5', 'min': '0.5', 'max': '20',
                'placeholder': '1.0',
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Introduce yourself and explain how you can help…',
                'maxlength': 500,
            }),
        }

    def clean_proposed_hours(self):
        hours = self.cleaned_data.get('proposed_hours')
        if hours is not None and hours <= 0:
            raise forms.ValidationError('Proposed hours must be greater than 0.')
        return hours


class ReviewForm(forms.ModelForm):
    """Leave a review after an exchange is completed."""
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(i, f'{i} star{"s" if i > 1 else ""}') for i in range(1, 6)],
                attrs={'class': 'form-select'},
            ),
            'comment': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Share your experience…',
                'maxlength': 500,
            }),
        }


class MessageForm(forms.ModelForm):
    """Post a message in a request thread."""
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Write a message…',
                'maxlength': 1000,
            }),
        }
