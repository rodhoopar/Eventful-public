from __future__ import absolute_import
from django import forms
from .models import Event, Volunteer, Task 
from django.utils import timezone
from django.forms import ValidationError
from django.conf import settings
from random import randint
from twilio.rest import Client
from django.db.models import F
from django.contrib import messages
import re
import csv
import codecs

# Twilio Client
account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
auth_token = getattr(settings, "TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)

# Creates and saves events
class EventCreationForm(forms.ModelForm): 
    class Meta: 
        model = Event
        fields = ('name', 'end')

    def __init__(self, *args, **kwargs): 
        self.request = kwargs.pop('request', None)
        return super(EventCreationForm, self).__init__(*args, **kwargs)

    def clean_end(self):
        end = self.cleaned_data.get('end')
        t = timezone.now() 
        midnight_delta = t - t.replace(hour=0, minute=0, second=0, microsecond=0)
        t = t - midnight_delta
        if end < t: 
            raise forms.ValidationError("Invalid end time")
        if end >= t + timezone.timedelta(days=8): 
            raise forms.ValidationError("End Date must be within 1 week.")
        return end
        
    def save(self, commit=True): 
        event = super(EventCreationForm, self).save(commit=False)
        if self.request:
            event.organizer = self.request.user
        event.save()

# Creates and saves volunteers
class VolunteerCreationForm(forms.ModelForm): 
    class Meta: 
        model = Volunteer
        fields = ('name', 'phone', 'category')

    def __init__(self, *args, **kwargs): 
        self.request = kwargs.pop('request', None)
        return super(VolunteerCreationForm, self).__init__(*args, **kwargs)

    def clean_name(self): 
        name = self.cleaned_data.get('name')
        if Volunteer.objects.filter(organizer=self.request.user, name=name): 
            raise forms.ValidationError('You already have a volunteer with this name; please enumerate the new one.')
        return name

    def clean_phone(self): 
        phone = self.cleaned_data.get('phone')
        if phone: 
            phone = re.sub('\+1', '', phone)
            phone = re.sub('[-\ ()]', '', phone)
            if len(phone) != 10 or not phone.isdigit(): 
                raise forms.ValidationError("Invalid Phone Number")
        if Volunteer.objects.filter(phone=phone): 
            raise forms.ValidationError('This volunteer\'s phone is already in use for another event.')
        name = self.cleaned_data.get('name')
        if Volunteer.objects.filter(organizer=self.request.user, name=name): 
            raise forms.ValidationError('You already have a volunteer with this name; please enumerate the new one.')
        to = phone
        from_ = settings.TWILIO_NUMBER
        body = 'You\'ve been added as a volunteer to the event "' + Event.objects.get(organizer=self.request.user).name + '"\nIf at any time you\'re unavailable during this event, reply "unavailable" to let your organizer know.'
        try:
            client.messages.create(to=to, from_=from_, body=body)
        except Exception, e:
            if 'blacklist' in str(e):
                raise forms.ValidationError("This volunteer's phone number is unsubscribed from Eventful. Contact them individually to resolve the issue.")
            elif 'invalid' in str(e):
                raise forms.ValidationError("Phone Number Does Not Exist or is Not Active")
            elif 'balance' in str(e) or 'money' in str(e):
                raise forms.ValidationError("No money in the Twilio Account. Sorry.")
            else:
                raise forms.ValidationError("There was a problem adding this phone number. The Twilio account may be out of money.")
        return phone

    def save(self, commit=True): 
        volunteer = super(VolunteerCreationForm, self).save(commit=False)
        if self.request:
            volunteer.organizer = self.request.user
        volunteer.save() 

# Creates and saves tasks
class TaskCreationForm(forms.ModelForm): 
    volunteer = forms.ModelChoiceField(queryset=None, empty_label="Random")

    class Meta: 
        model = Task
        fields = ('description', 'priority', 'volunteer')

    def __init__(self, *args, **kwargs): 
        self.request = kwargs.pop('request', None)
        super(TaskCreationForm, self).__init__(*args, **kwargs)
        self.fields['volunteer'].required = False

    def save(self, commit=True): 
        task = super(TaskCreationForm, self).save(commit=False)
        if self.request:
            task.organizer = self.request.user

        if task.volunteer is None: 
            volunteers = Volunteer.objects.filter(organizer=task.organizer, status='Free')
            new_volunteer = volunteers[randint(0, len(volunteers)-1)]
            task.volunteer = new_volunteer 

        to = task.volunteer.phone
        from_ = settings.TWILIO_NUMBER
        body = 'From your organizer: "' + task.description + '"\nReply "yes" if you can do the task!'
        if not task.volunteer.unsubscribed:
            client.messages.create(to=to, from_=from_, body=body)
            task.save()
            volun = task.volunteer
            volun.status = "Pending"
            volun.latest_assignment = timezone.now()
            if volun.num_assigned < settings.PSIF_MAX: 
                volun.num_assigned += 1
            volun.save()             
            event = Event.objects.get(organizer=task.organizer)
            if event.total_assigned < settings.PSIF_MAX: 
                event.total_assigned += 1
                event.save()
            messages.success(self.request, 'Task assigned.')
        else:
            messages.warning(self.request, "This volunteer's phone number is unsubscribed from Eventful. Please contact them directly to resolve the issue.")

# Creates and saves volunteers from CSV upload
def validate_file_extension(value):
        if not value.name.endswith('.csv'):
            raise forms.ValidationError("Only .csv files are accepted")
class CSVForm(forms.Form):
    docfile = forms.FileField(label='Select a file',validators=[validate_file_extension])
    
    def clean_docfile(self):
        docfile = self.cleaned_data.get('docfile')
        try:
            dialect = csv.Sniffer().sniff(codecs.EncodedFile(docfile, "utf-8").read(1024))
        except UnicodeDecodeError:
            messages.success(self.request, 'There was an error with your file. See below for details.')
            raise forms.ValidationError("There is an issue with your file's unicode encoding (not UTF-8). You may have used Excel to create it. Try copy and pasting the contents of the csv file into Google Sheets, downloading it, and reuploading the resulting csv file.")
            return
        docfile.open()
        num_in_use = []
        name_in_use = []
        invalid_num = []
        dne_num = []
        wrong_num_fields = []
        i = 1
        duplicates = 0
        num_added = 0
        reader = csv.reader(codecs.EncodedFile(docfile, "utf-8"), delimiter=',', dialect=dialect)
        
        for row in reader:
            new_row  = []
            for element in row:
                if element != '': 
                    new_row.append(element)
            row = new_row
            true_len = len(row)
            error = False
            if true_len == 0: continue
            elif true_len == 3 or true_len == 2:
                # Exact duplicate
                if Volunteer.objects.filter(phone=row[1]) and Volunteer.objects.filter(organizer= self.request.user, name=row[0]):
                    duplicates+=1
                    continue
                # Check if phone number in use
                if Volunteer.objects.filter(phone=row[1]):
                    num_in_use.append(i)
                    error = True
                # Check if name in use in this event
                if Volunteer.objects.filter(organizer= self.request.user, name=row[0]): 
                    name_in_use.append(i)
                    error = True
                # Check if phone number is valid
                if row[1]: 
                    row[1] = re.sub('\+1', '', row[1])
                    row[1] = re.sub('[-\ ()]', '', row[1])
                    if len(row[1]) != 10 or not row[1].isdigit():
                        invalid_num.append(i)
                        error = True
                    if not error:
                        to = row[1]
                        from_ = settings.TWILIO_NUMBER
                        body = 'You\'ve been added as a volunteer to the event "' + Event.objects.get(organizer=self.request.user).name + '"\nIf at any time you\'re unavailable during this event, reply "unavailable" to let your organizer know.'
                        try:
                            client.messages.create(to=to, from_=from_, body=body)
                        except Exception, e:
                            dne_num.append(i)
                            error = True
                
                if not error:
                    if true_len == 3:
                        v = Volunteer(organizer = self.request.user, name = row[0], phone=row[1], category = row[2])
                    elif true_len == 2:
                        v = Volunteer(organizer = self.request.user, name = row[0], phone=row[1])
                    v.save()
                    num_added+=1
            else:
                wrong_num_fields.append(i)
            i+=1
        
        error_types= [invalid_num, dne_num, name_in_use, num_in_use, wrong_num_fields]
        error_messages= ["The following rows contained an invalid phone number:",
        "The following rows contained a phone number that does not exist or is not active:", 
        "The following rows contained a volunteer name that is already in use:", 
        "The following rows contained a phone number that is already in use:",
        "The following rows contained missing or extra fields:"]
        num_errors = 0
        error_str = ''
        
        for i in range(len(error_types)):
            arr = error_types[i]
            if  not len(arr) == 0:
                error_str+='\n'
                error_str+= error_messages[i]
                num_errors+= len(arr)
                for j in range(len(arr)):
                    row = arr[j]
                    error_str += " " + str(row)
                    if (j != len(arr) - 1):
                        error_str += ","
        
        message_str = ''
        if num_added>0:
            message_str += 'Successfully added ' + str(num_added) + ' volunteer(s). ' 
        if duplicates>0:
            message_str+= str(duplicates) + ' duplicate(s) skipped.'
        if not num_errors == 0: 
            message_str += ' ' + str(num_errors) +   " errors detected. See below for details"
        if message_str != '': messages.success(self.request, message_str)
        if not len(error_str) == 0: 
            raise forms.ValidationError("The file contained the following issues:" + error_str)

    def __init__(self, *args, **kwargs): 
        self.request = kwargs.pop('request', None)
        super(CSVForm, self).__init__(*args, **kwargs)
    
    def save(self):
        docfile = self.cleaned_data.get('docfile')