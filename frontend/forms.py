from django import forms
from django.contrib.auth.models import User
from attendance.models import Lecturer, Student, Course


class LecturerForm(forms.ModelForm):
    """Form for creating and editing lecturers"""
    username = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    
    class Meta:
        model = Lecturer
        fields = ['staff_id', 'name', 'department', 'phone_number', 'latitude', 'longitude']
        widgets = {
            'latitude': forms.NumberInput(attrs={'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'step': 'any'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        # Validate coordinates are within valid ranges
        lat = cleaned_data.get('latitude')
        lon = cleaned_data.get('longitude')
        
        if lat is not None and (lat < -90 or lat > 90):
            raise forms.ValidationError({'latitude': 'Latitude must be between -90 and 90'})
        
        if lon is not None and (lon < -180 or lon > 180):
            raise forms.ValidationError({'longitude': 'Longitude must be between -180 and 180'})
        
        return cleaned_data


class StudentForm(forms.ModelForm):
    """Form for creating and editing students"""
    username = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    
    class Meta:
        model = Student
        fields = ['student_id', 'name', 'programme_of_study', 'year', 'phone_number', 
                 'notification_preference', 'is_notifications_enabled']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make notification fields optional
        self.fields['notification_preference'].required = False
        self.fields['is_notifications_enabled'].required = False
        
        # Set default values if not provided
        if not self.instance.pk:  # New instance
            self.fields['notification_preference'].initial = 'both'
            self.fields['is_notifications_enabled'].initial = True
    
    def clean_year(self):
        year = self.cleaned_data.get('year')
        if year:
            try:
                if int(year) < 1:
                    raise forms.ValidationError('Year must be at least 1')
            except ValueError:
                raise forms.ValidationError('Year must be a number')
        return year


class CourseForm(forms.ModelForm):
    """Form for creating and editing courses"""
    class Meta:
        model = Course
        fields = ['name', 'course_code', 'lecturer', 'is_active']
    
    def clean_course_code(self):
        code = self.cleaned_data.get('course_code')
        if code:
            # Remove whitespace and convert to uppercase
            return code.upper().strip()
        return code


class StudentUploadForm(forms.Form):
    """Form for bulk uploading students via CSV"""
    file = forms.FileField(label="Upload CSV File")
